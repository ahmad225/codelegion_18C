# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

APPROVER_GROUP = 'cl_quotation_inactivity_approval.group_cl_quotation_approver'
APPROVAL_ACTIVITY = 'cl_quotation_inactivity_approval.mail_act_cl_quotation_approval'

# Changing any of these is "working on the quotation".
ACTIVITY_FIELDS = {
    'order_line', 'partner_id', 'partner_invoice_id', 'partner_shipping_id',
    'pricelist_id', 'payment_term_id', 'fiscal_position_id', 'currency_id',
    'validity_date', 'commitment_date', 'note', 'client_order_ref',
}
# Set by this module only; never by hand, import or API.
PROTECTED_FIELDS = {'cl_last_activity_date', 'cl_approval_state'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_last_activity_date = fields.Datetime(
        string='Last Activity', default=fields.Datetime.now, copy=False, readonly=True,
        help='Last change to the quotation, message to/from the customer or approval. '
             'Internal notes and automatic tracking do not count.')
    cl_approval_state = fields.Selection(
        [('none', 'Not Needed'), ('pending', 'Pending Approval'), ('approved', 'Approved')],
        string='Inactivity Approval', default='none', required=True, copy=False,
        readonly=True, index=True, tracking=True)

    # ---- helpers ----

    def _cl_is_approver(self):
        return self.env.su or self.env.user.has_group(APPROVER_GROUP)

    def _cl_check_pending_edit(self):
        if self._cl_is_approver():
            return
        pending = self.filtered(
            lambda o: o.cl_approval_state == 'pending' and o.state in ('draft', 'sent'))
        if pending:
            raise UserError(_(
                "%s is waiting for approval because it was inactive for too long. "
                "Only approvers can change it until it is approved.",
                ', '.join(pending.mapped('name'))))

    def _cl_touch_activity(self):
        quotations = self.filtered(lambda o: o.state in ('draft', 'sent'))
        if quotations:
            quotations.sudo().write({'cl_last_activity_date': fields.Datetime.now()})

    def _cl_needs_inactivity_approval(self):
        self.ensure_one()
        days = self.company_id.cl_quotation_inactivity_days
        if days <= 0 or self.state not in ('draft', 'sent'):
            return False
        if self.cl_approval_state == 'pending':
            return True
        # An approval counts as activity (see action_cl_approve), so an
        # approved quotation that is left alone again needs a new approval.
        last = self.cl_last_activity_date or self.create_date
        return bool(last) and last < fields.Datetime.now() - timedelta(days=days)

    def _cl_approvers(self):
        self.ensure_one()
        group = self.env.ref(APPROVER_GROUP)
        return group.sudo().users.filtered(
            lambda u: self.company_id in u.company_ids and not u.share)

    def _cl_log(self, body, partner_ids=None):
        """ Note in the chatter. People in ``partner_ids`` are notified when the
        current user is able to send messages; a user without an email address
        only logs the note, so the workflow never stops on that. """
        self.ensure_one()
        if partner_ids and (self.env.su or self.env.user.email_formatted):
            self.message_post(body=body, partner_ids=partner_ids, subtype_xmlid='mail.mt_note')
        else:
            self._message_log(body=body)

    # ---- tracking activity ----

    @api.model_create_multi
    def create(self, vals_list):
        if not self._cl_is_approver():
            # Explicit values, so neither the caller nor a default_* context key
            # can start a quotation with a clock set in the future.
            now = fields.Datetime.now()
            vals_list = [
                dict(vals, cl_last_activity_date=now, cl_approval_state='none')
                for vals in vals_list
            ]
        return super().create(vals_list)

    def write(self, vals):
        if PROTECTED_FIELDS.intersection(vals) and not self._cl_is_approver():
            raise AccessError(_(
                "The inactivity approval of a quotation can only be changed with the "
                "Approve and Reject buttons, by an approver."))
        if ACTIVITY_FIELDS.intersection(vals):
            self._cl_check_pending_edit()
            vals = dict(vals, cl_last_activity_date=fields.Datetime.now())
        return super().write(vals)

    def _message_post_after_hook(self, message, msg_values):
        res = super()._message_post_after_hook(message, msg_values)
        # A message to or from the customer is activity; internal notes and tracking are not.
        if (message.message_type in ('comment', 'email') and message.subtype_id
                and not message.subtype_id.internal):
            self._cl_touch_activity()
        return res

    # ---- confirmation ----

    def action_confirm(self):
        # Customer acceptance / payment (sudo, portal) and system flows are never blocked.
        # Approvers confirm directly: they are the reviewers.
        if (self.env.context.get('cl_skip_inactivity_check') or self._cl_is_approver()
                or not self.env.user._is_internal()):
            res = super().action_confirm()
            self._cl_close_approval_after_confirm()
            return res
        stale = self.filtered(lambda o: o._cl_needs_inactivity_approval())
        if not stale:
            return super().action_confirm()
        for order in stale:
            # Do not bother approvers with a quotation that cannot be confirmed anyway.
            error_msg = order._confirmation_error_message()
            if error_msg:
                raise UserError(error_msg)
        stale._cl_request_approval()
        rest = self - stale
        res = super(SaleOrder, rest).action_confirm() if rest else True
        if isinstance(res, dict):
            return res
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approval needed'),
                'message': _(
                    "%s was inactive for too long and has been sent for approval.",
                    ', '.join(stale.mapped('name'))),
                'type': 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _cl_close_approval_after_confirm(self):
        """ A pending quotation that was confirmed by an approver, or accepted
        by the customer online, is no longer waiting for anybody. """
        pending = self.filtered(lambda o: o.cl_approval_state == 'pending' and o.state == 'sale')
        if not pending:
            return
        by_approver = not self.env.su and self.env.user.has_group(APPROVER_GROUP)
        pending = pending.sudo()
        pending.write({'cl_approval_state': 'approved' if by_approver else 'none'})
        pending.activity_unlink([APPROVAL_ACTIVITY])
        for order in pending:
            order._message_log(body=_("Approval request closed: the quotation was confirmed."))

    def _cl_request_approval(self):
        for order in self.filtered(lambda o: o.cl_approval_state != 'pending'):
            days = order.company_id.cl_quotation_inactivity_days
            approvers = order._cl_approvers()
            if not approvers:
                raise UserError(_(
                    "%(order)s was inactive for more than %(days)s day(s) and needs approval, but "
                    "%(company)s has no user in the 'Approve Inactive Quotations' group. "
                    "Ask an administrator to add one.",
                    order=order.name, days=days, company=order.company_id.name))
            order.sudo().write({'cl_approval_state': 'pending'})
            order._cl_log(_(
                "Sent for approval: no activity for more than %(days)s day(s). "
                "Requested by %(user)s.", days=days, user=self.env.user.name))
            for approver in approvers:
                # sudo: assigning an activity notifies the assignee, which core
                # refuses when the requesting user has no email address.
                order.sudo().activity_schedule(
                    APPROVAL_ACTIVITY,
                    summary=_('Approve inactive quotation'),
                    note=_("No activity for more than %s day(s). Review prices and terms, "
                           "then approve or reject.", days),
                    user_id=approver.id,
                )

    def _cl_close_approval_activities(self, feedback):
        """ The approver's own activity is marked done; the copies scheduled for
        the other approvers are removed (one chatter line, not one per approver). """
        self.ensure_one()
        self.activity_feedback([APPROVAL_ACTIVITY], user_id=self.env.uid, feedback=feedback)
        self.activity_unlink([APPROVAL_ACTIVITY])

    def action_cl_approve(self):
        if not self._cl_is_approver():
            raise UserError(_("Only quotation approvers can approve inactive quotations."))
        for order in self.filtered(lambda o: o.cl_approval_state == 'pending'):
            # The review is activity: the clock starts again from the approval.
            order.write({
                'cl_approval_state': 'approved',
                'cl_last_activity_date': fields.Datetime.now(),
            })
            order._cl_close_approval_activities(_('Approved'))
            order._cl_log(
                _("Approved by %s. The quotation can now be confirmed.", self.env.user.name),
                partner_ids=order.user_id.partner_id.ids)
        return True

    def action_cl_reject(self):
        if not self._cl_is_approver():
            raise UserError(_("Only quotation approvers can reject inactive quotations."))
        for order in self.filtered(lambda o: o.cl_approval_state == 'pending'):
            order.write({'cl_approval_state': 'none'})
            order._cl_close_approval_activities(_('Rejected'))
            order._cl_log(
                _("Rejected by %s: review and update the quotation before confirming it.",
                  self.env.user.name),
                partner_ids=order.user_id.partner_id.ids)
        return True

    def _action_cancel(self):
        pending = self.filtered(lambda o: o.cl_approval_state == 'pending')
        if pending:
            pending.sudo().write({'cl_approval_state': 'none'})
            pending.activity_unlink([APPROVAL_ACTIVITY])
        return super()._action_cancel()
