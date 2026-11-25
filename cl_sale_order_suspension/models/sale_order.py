# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

SUSPEND_GROUP = 'cl_sale_order_suspension.group_cl_sale_suspension'
FOLLOWUP_ACTIVITY = 'cl_sale_order_suspension.mail_act_cl_suspension_followup'
SUSPENSION_FIELDS = frozenset((
    'cl_is_suspended', 'cl_suspended_by_id', 'cl_suspended_date', 'cl_suspension_reason'))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_is_suspended = fields.Boolean(
        string='Suspended', copy=False, readonly=True, index=True, tracking=True)
    cl_suspended_by_id = fields.Many2one(
        'res.users', string='Suspended By', copy=False, readonly=True)
    cl_suspended_date = fields.Datetime(string='Suspended On', copy=False, readonly=True)
    cl_suspension_reason = fields.Text(string='Suspension Reason', copy=False, readonly=True)
    cl_other_suspended_order_ids = fields.Many2many(
        'sale.order', string='Other Suspended Quotations',
        compute='_compute_cl_other_suspended_order_ids',
        help='Suspended quotations of the same customer (any of its contacts) in the same company.')

    @api.depends('partner_id', 'company_id', 'cl_is_suspended')
    def _compute_cl_other_suspended_order_ids(self):
        # One search for the whole batch, then a lookup per order; the form
        # shows the result as links, like Odoo's own "might be a duplicate".
        customers = self.partner_id.commercial_partner_id
        on_hold = defaultdict(list)
        if customers:
            for held in self.search([
                ('cl_is_suspended', '=', True),
                ('partner_id.commercial_partner_id', 'in', customers.ids),
                ('company_id', 'in', self.company_id.ids),
            ]):
                on_hold[held.partner_id.commercial_partner_id.id, held.company_id.id].append(held.id)
        for order in self:
            key = (order.partner_id.commercial_partner_id.id, order.company_id.id)
            order.cl_other_suspended_order_ids = [
                fields.Command.set([oid for oid in on_hold.get(key, ()) if oid != order._origin.id])]

    def _cl_has_suspension_rights(self):
        return self.env.su or self.env.user.has_group(SUSPEND_GROUP)

    def _cl_check_suspension_rights(self):
        if not self._cl_has_suspension_rights():
            raise UserError(_("Only members of the 'Suspend Quotations' group can suspend or resume quotations."))

    def write(self, vals):
        # The suspension fields are read-only on screen; this keeps them
        # read-only over RPC and import too, so the flag cannot be cleared by
        # someone who is not allowed to resume.
        if SUSPENSION_FIELDS.intersection(vals) and not self._cl_has_suspension_rights():
            raise AccessError(_(
                "Only members of the 'Suspend Quotations' group can change the suspension of a quotation."))
        return super().write(vals)

    def action_cl_open_suspend_wizard(self):
        self._cl_check_suspension_rights()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Suspend Quotation'),
            'res_model': 'cl.sale.suspend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_ids': [(6, 0, self.ids)]},
        }

    def _cl_suspend(self, reason, follow_up_date=None):
        self._cl_check_suspension_rights()
        if not (reason or '').strip():
            raise UserError(_("Please give a reason for suspending the quotation."))
        not_quotation = self.filtered(lambda o: o.state not in ('draft', 'sent'))
        if not_quotation:
            raise UserError(_(
                "Only quotations can be suspended: %s", ', '.join(not_quotation.mapped('name'))))
        for order in self.filtered(lambda o: not o.cl_is_suspended):
            order.write({
                'cl_is_suspended': True,
                'cl_suspended_by_id': self.env.user.id,
                'cl_suspended_date': fields.Datetime.now(),
                'cl_suspension_reason': reason,
            })
            order.activity_schedule(
                FOLLOWUP_ACTIVITY,
                date_deadline=follow_up_date or fields.Date.context_today(order),
                summary=_('Follow up suspended quotation'),
                note=reason,
                user_id=self.env.user.id,
            )
            # A log note: nobody has to be notified and it also works for a
            # user without an email address.
            order._message_log(body=_("Quotation suspended. Reason: %s", reason))
        return True

    def action_cl_resume(self):
        self._cl_check_suspension_rights()
        for order in self.filtered('cl_is_suspended'):
            order._cl_clear_suspension(_('Quotation resumed.'))
        return True

    def _cl_clear_suspension(self, message):
        self.ensure_one()
        self.write({
            'cl_is_suspended': False,
            'cl_suspended_by_id': False,
            'cl_suspended_date': False,
            'cl_suspension_reason': False,
        })
        self.activity_feedback([FOLLOWUP_ACTIVITY], feedback=message)
        self._message_log(body=message)

    # ---- the flow a suspended quotation is kept out of ----

    def _confirmation_error_message(self):
        if self.cl_is_suspended:
            return _("%s is suspended. Resume it before confirming it.", self.name)
        return super()._confirmation_error_message()

    def action_quotation_send(self):
        suspended = self.filtered('cl_is_suspended')
        if suspended:
            raise UserError(_(
                "%s is suspended. Resume it before sending it.", ', '.join(suspended.mapped('name'))))
        return super().action_quotation_send()

    def _has_to_be_signed(self):
        # Keeps "Sign" off the customer portal: signing would try to confirm
        # the quotation and fail after the signature was already saved.
        return not self.cl_is_suspended and super()._has_to_be_signed()

    def _has_to_be_paid(self):
        # Keeps "Pay" off the customer portal: the payment would be taken and
        # the confirmation that follows it would then be refused.
        return not self.cl_is_suspended and super()._has_to_be_paid()

    def _action_cancel(self):
        suspended = self.filtered('cl_is_suspended')
        if suspended and not self._cl_has_suspension_rights():
            # Otherwise "Cancel" then "Set to Quotation" would be a way to
            # resume without the right to do so.
            raise UserError(_(
                "%s is suspended. Only members of the 'Suspend Quotations' group can cancel a "
                "suspended quotation.", ', '.join(suspended.mapped('name'))))
        for order in suspended:
            order._cl_clear_suspension(_('Suspension ended: the quotation was cancelled.'))
        return super()._action_cancel()
