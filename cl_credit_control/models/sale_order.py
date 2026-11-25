# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, RedirectWarning, UserError

ACTIVITY_TYPE_XMLID = 'cl_credit_control.mail_activity_type_credit_approval'
MANAGER_GROUP_XMLID = 'cl_credit_control.group_cl_credit_manager'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # The order keeps its normal status (Quotation / Quotation Sent) while it
    # waits for approval; the credit approval has its own status field, so no
    # standard status, button or status bar is replaced.
    cl_credit_state = fields.Selection(
        selection=[
            ('to_approve', "Waiting Approval"),
            ('approved', "Approved"),
            ('rejected', "Rejected"),
        ],
        string="Credit Approval",
        copy=False, readonly=True, tracking=True,
    )
    cl_credit_requested_by_id = fields.Many2one(
        'res.users', string="Approval Requested By", copy=False, readonly=True)
    cl_credit_requested_on = fields.Datetime(
        string="Approval Requested On", copy=False, readonly=True)
    cl_credit_request_note = fields.Text(
        string="Request Note", copy=False, readonly=True)
    cl_credit_decided_by_id = fields.Many2one(
        'res.users', string="Decided By", copy=False, readonly=True)
    cl_credit_decided_on = fields.Datetime(
        string="Decided On", copy=False, readonly=True)
    cl_credit_approved_amount = fields.Monetary(
        string="Approved Amount", copy=False, readonly=True,
        help="Order total that was approved. If the total goes above this, "
             "the order needs a new approval.")
    cl_credit_reject_reason = fields.Text(
        string="Rejection Reason", copy=False, readonly=True)
    cl_credit_warning = fields.Text(
        string="Credit Block Reasons",
        compute='_compute_cl_credit_warning',
        help="Why this quotation cannot be confirmed without credit approval.",
    )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _cl_credit_amount_company_currency(self):
        """Order total converted to the company currency."""
        self.ensure_one()
        company = self.company_id
        if not self.currency_id or not company or self.currency_id == company.currency_id:
            return self.amount_total
        date = (self.date_order or fields.Datetime.now()).date()
        return self.currency_id._convert(self.amount_total, company.currency_id, company, date)

    def _cl_credit_issues(self):
        """Reasons why this order is blocked (empty list: not blocked)."""
        self.ensure_one()
        if not self.partner_id or not self.company_id:
            return []
        return self.partner_id._cl_credit_evaluate(
            self.company_id, extra_amount=self._cl_credit_amount_company_currency())

    def _cl_credit_is_approved(self):
        """An approval is valid for the approved amount only."""
        self.ensure_one()
        if self.cl_credit_state != 'approved':
            return False
        currency = self.currency_id or self.company_id.currency_id
        return currency.compare_amounts(self.amount_total, self.cl_credit_approved_amount) <= 0

    @api.depends('partner_id', 'company_id', 'amount_total', 'state',
                 'cl_credit_state', 'cl_credit_approved_amount')
    def _compute_cl_credit_warning(self):
        for order in self:
            warning = False
            if order.state in ('draft', 'sent') and order.partner_id and not order._cl_credit_is_approved():
                issues = order._cl_credit_issues()
                if issues:
                    warning = "\n".join(issue['message'] for issue in issues)
            order.cl_credit_warning = warning

    # ------------------------------------------------------------------
    # Confirmation gate
    # ------------------------------------------------------------------
    def _cl_credit_check(self):
        """Stop the confirmation of blocked quotations.

        Always raises instead of returning an action, so that a caller that
        is not a button click (online payment, signature, import, another
        module) can never believe the order was confirmed when it was not.
        """
        for order in self:
            if order.state not in ('draft', 'sent') or order._cl_credit_is_approved():
                continue
            issues = order._cl_credit_issues()
            if not issues:
                continue
            reasons = "\n".join("- %s" % issue['message'] for issue in issues)
            if order.env.su and order.company_id.cl_credit_skip_automatic:
                # a log note: nobody to notify, and it must never fail for a
                # public / portal user without an email address
                order._message_log(body=Markup("%s<br/>%s") % (
                    _("Credit control: this order was confirmed automatically, "
                      "so the credit check was not enforced."),
                    Markup("<br/>").join(issue['message'] for issue in issues),
                ))
                continue
            if order.cl_credit_state == 'to_approve' and not order._cl_credit_user_is_manager():
                raise UserError(_(
                    "%(order)s is waiting for credit approval and cannot be confirmed yet.\n\n%(reasons)s",
                    order=order.name, reasons=reasons))
            action = self.env.ref('cl_credit_control.action_cl_credit_approval_request')
            raise RedirectWarning(
                _("%(order)s cannot be confirmed without credit approval.\n\n%(reasons)s",
                  order=order.name, reasons=reasons),
                action.id,
                _("Review Credit Block"),
                {'default_order_id': order.id},
            )

    def action_confirm(self):
        self._cl_credit_check()
        res = super().action_confirm()
        # confirmed without a decision (the customer paid in the meantime, or
        # an automatic confirmation was let through): the request is void
        self._cl_credit_drop_pending_requests()
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        self._cl_credit_drop_pending_requests()
        return res

    def action_draft(self):
        # a cancelled order that becomes a quotation again starts from scratch:
        # an approval given before the cancellation does not carry over
        cancelled = self.filtered(lambda order: order.state == 'cancel' and order.cl_credit_state)
        res = super().action_draft()
        if cancelled:
            cancelled.write({'cl_credit_state': False, 'cl_credit_approved_amount': 0.0})
        return res

    def _cl_credit_drop_pending_requests(self):
        """Withdraw the requests still waiting on these orders and close the
        Credit Managers' activities, so nobody is asked to decide on an order
        that was confirmed or cancelled in the meantime."""
        pending = self.filtered(lambda order: order.cl_credit_state == 'to_approve')
        if pending:
            pending.write({'cl_credit_state': False})
            pending._cl_credit_close_activities()
        return pending

    def action_cl_credit_review(self):
        """Open the credit block dialog (reasons, overdue items, request / approve)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_credit_control.action_cl_credit_approval_request')
        action['context'] = {'default_order_id': self.id}
        return action

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------
    def _cl_credit_user_is_manager(self):
        return self.env.user.has_group(MANAGER_GROUP_XMLID)

    def _cl_credit_ensure_manager(self):
        if not self._cl_credit_user_is_manager():
            raise AccessError(_("Only a Credit Manager can approve or reject a credit request."))

    def _cl_credit_managers(self):
        """Credit Managers who can work in this order's company."""
        self.ensure_one()
        group = self.env.ref(MANAGER_GROUP_XMLID)
        return group.sudo().users.filtered(
            lambda user: user.active and not user.share and self.company_id in user.company_ids)

    def _cl_credit_close_activities(self, feedback=False):
        """Close the credit approval activities of these orders.

        The current user's own activity is marked done with the feedback; the
        ones assigned to the other managers are simply removed.
        """
        activity_type = self.env.ref(ACTIVITY_TYPE_XMLID, raise_if_not_found=False)
        if not activity_type:
            return
        activities = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'sale.order'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', activity_type.id),
        ])
        mine = activities.filtered(lambda activity: activity.user_id == self.env.user)
        if mine and feedback:
            mine.with_user(self.env.user).action_feedback(feedback=feedback)
            activities -= mine
        activities.unlink()

    def _cl_credit_reasons_html(self, issues):
        return Markup("<ul>%s</ul>") % Markup("").join(
            Markup("<li>%s</li>") % issue['message'] for issue in issues)

    def _cl_credit_request(self, note=False):
        """Ask the Credit Managers to approve this blocked quotation."""
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only quotations can be sent for credit approval."))
        issues = self._cl_credit_issues()
        if not issues:
            raise UserError(_("%s no longer needs credit approval. You can confirm it.", self.name))
        managers = self._cl_credit_managers()
        if not managers:
            raise UserError(_(
                "No Credit Manager is set up for %s. Ask an administrator to give "
                "the 'Credit Manager' access right to at least one user.",
                self.company_id.name))
        self.write({
            'cl_credit_state': 'to_approve',
            'cl_credit_requested_by_id': self.env.user.id,
            'cl_credit_requested_on': fields.Datetime.now(),
            'cl_credit_request_note': note or False,
            'cl_credit_decided_by_id': False,
            'cl_credit_decided_on': False,
            'cl_credit_approved_amount': 0.0,
            'cl_credit_reject_reason': False,
        })
        reasons_html = self._cl_credit_reasons_html(issues)
        body = Markup("<p>%s</p>%s") % (
            _("Credit approval requested by %s.", self.env.user.name), reasons_html)
        if note:
            body += Markup("<p>%s %s</p>") % (_("Note:"), note)
        # one open activity per manager, never duplicated
        self._cl_credit_close_activities()
        for manager in managers:
            self.activity_schedule(
                ACTIVITY_TYPE_XMLID,
                user_id=manager.id,
                summary=_("Credit approval: %s", self.name),
                note=reasons_html,
            )
        # the managers are told through their activity; this is only a log note
        self._message_log(body=body)
        return True

    def action_cl_credit_approve(self):
        """Approve the credit exception and confirm the quotation."""
        self._cl_credit_ensure_manager()
        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError(_("%s is not a quotation any more.", order.name))
            order.write({
                'cl_credit_state': 'approved',
                'cl_credit_decided_by_id': self.env.user.id,
                'cl_credit_decided_on': fields.Datetime.now(),
                'cl_credit_approved_amount': order.amount_total,
                'cl_credit_reject_reason': False,
            })
            order._cl_credit_close_activities(_("Approved by %s", self.env.user.name))
            order.message_post(
                body=_("Credit approved by %s.", self.env.user.name),
                partner_ids=order.cl_credit_requested_by_id.partner_id.ids,
            )
        # Normal confirmation, through every module's own checks. If it fails,
        # the error is shown and the approval above is rolled back with it.
        return self.action_confirm()

    def action_cl_credit_reject(self):
        """Open the wizard that asks for the rejection reason."""
        self.ensure_one()
        self._cl_credit_ensure_manager()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_credit_control.action_cl_credit_reject')
        action['context'] = {'default_order_id': self.id}
        return action

    def _cl_credit_reject(self, reason):
        self.ensure_one()
        self._cl_credit_ensure_manager()
        if self.state not in ('draft', 'sent'):
            raise UserError(_("%s is not a quotation any more.", self.name))
        self.write({
            'cl_credit_state': 'rejected',
            'cl_credit_decided_by_id': self.env.user.id,
            'cl_credit_decided_on': fields.Datetime.now(),
            'cl_credit_approved_amount': 0.0,
            'cl_credit_reject_reason': reason,
        })
        self._cl_credit_close_activities(_("Rejected by %s", self.env.user.name))
        self.message_post(
            body=Markup("<p>%s</p><p>%s %s</p>") % (
                _("Credit request rejected by %s.", self.env.user.name),
                _("Reason:"), reason),
            partner_ids=self.cl_credit_requested_by_id.partner_id.ids,
        )
        return True

    # ------------------------------------------------------------------
    # Keep the approval tied to the customer it was given for
    # ------------------------------------------------------------------
    def write(self, vals):
        res = super().write(vals)
        if 'partner_id' in vals:
            stale = self.filtered(
                lambda order: order.cl_credit_state and order.state in ('draft', 'sent'))
            if stale:
                super(SaleOrder, stale).write({
                    'cl_credit_state': False,
                    'cl_credit_approved_amount': 0.0,
                })
                stale._cl_credit_close_activities()
        return res
