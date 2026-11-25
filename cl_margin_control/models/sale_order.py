# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

ACTIVITY_TYPE_XMLID = 'cl_margin_control.mail_activity_type_margin_approval'
# Margins are compared as percentages rounded to 2 decimals, so that an order
# exactly at a threshold is never flagged because of float noise.
MARGIN_DIGITS = 2


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_margin_approval_state = fields.Selection(
        selection=[
            ('none', 'Not Required'),
            ('to_approve', 'Pending Margin Approval'),
            ('approved', 'Margin Approved'),
        ],
        string='Margin Approval',
        default='none',
        copy=False,
        readonly=True,
        tracking=True,
    )
    cl_margin_approved_percent = fields.Float(
        string='Approved Margin (%)',
        copy=False,
        readonly=True,
        help="Margin of the order when it was approved. If the margin drops "
             "below this afterwards, the order needs a new approval.")
    cl_margin_order_low = fields.Boolean(
        string='Low Order Margin',
        compute='_compute_cl_margin_order_low')
    cl_margin_can_approve = fields.Boolean(
        string='Is Margin Approver',
        compute='_compute_cl_margin_can_approve')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    def _cl_margin_percent(self):
        """Order margin as a percentage (Odoo stores it as a ratio)."""
        self.ensure_one()
        return self.margin_percent * 100.0

    @api.depends('margin_percent', 'amount_untaxed',
                 'company_id.cl_margin_order_alert',
                 'company_id.cl_margin_order_alert_below')
    def _compute_cl_margin_order_low(self):
        for order in self:
            company = order.company_id or self.env.company
            order.cl_margin_order_low = bool(
                company.cl_margin_order_alert
                and order.amount_untaxed
                and float_compare(
                    order._cl_margin_percent(),
                    company.cl_margin_order_alert_below,
                    precision_digits=MARGIN_DIGITS) < 0)

    @api.depends_context('uid')
    @api.depends('company_id')
    def _compute_cl_margin_can_approve(self):
        for order in self:
            order.cl_margin_can_approve = order._cl_user_is_margin_approver()

    # ------------------------------------------------------------------
    # Who approves
    # ------------------------------------------------------------------
    def _cl_margin_approvers(self):
        """Users who approve this order's margin: the members of the company's
        Margin Approval Group or, when none is set, the Sales Administrators."""
        self.ensure_one()
        company = self.company_id or self.env.company
        group = (company.sudo().cl_margin_approver_group_id
                 or self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False))
        if not group:
            return self.env['res.users']
        return group.sudo().users.filtered(
            lambda user: user.active and not user.share and company in user.company_ids)

    def _cl_user_is_margin_approver(self):
        self.ensure_one()
        user = self.env.user
        return bool(self.env.su or user._is_admin() or user in self._cl_margin_approvers())

    def _cl_ensure_margin_approver(self):
        for order in self:
            if not order._cl_user_is_margin_approver():
                raise AccessError(_(
                    "Only a margin approver can approve or reject the margin of %s.",
                    order.display_name))

    # ------------------------------------------------------------------
    # Does the order need approval?
    # ------------------------------------------------------------------
    def _cl_margin_is_approved(self):
        """An approval covers the approved margin: it is void once the margin
        has dropped below the one that was approved."""
        self.ensure_one()
        return (
            self.cl_margin_approval_state == 'approved'
            and float_compare(
                self._cl_margin_percent(), self.cl_margin_approved_percent,
                precision_digits=MARGIN_DIGITS) >= 0)

    def _cl_needs_margin_approval(self):
        self.ensure_one()
        company = self.company_id
        return bool(
            company.cl_margin_floor_enabled
            and self.state in ('draft', 'sent')
            and self.amount_untaxed
            and float_compare(
                self._cl_margin_percent(), company.cl_margin_floor,
                precision_digits=MARGIN_DIGITS) < 0
            and not self._cl_margin_is_approved())

    # ------------------------------------------------------------------
    # Request / activities
    # ------------------------------------------------------------------
    def _cl_request_margin_approval(self):
        for order in self:
            if order.cl_margin_approval_state == 'to_approve':
                continue
            order.write({
                'cl_margin_approval_state': 'to_approve',
                'cl_margin_approved_percent': 0.0,
            })
            body = _(
                "Confirmation is blocked: the order margin %(margin).2f%% is below "
                "the margin floor of %(floor).2f%%. Margin approval has been "
                "requested.",
                margin=order._cl_margin_percent(),
                floor=order.company_id.cl_margin_floor,
            )
            # the approvers are told through their activity; this is a log note
            order._message_log(body=body)
            for user in order._cl_margin_approvers():
                order.activity_schedule(
                    ACTIVITY_TYPE_XMLID,
                    user_id=user.id,
                    summary=_("Margin approval: %s", order.name),
                    note=body)

    def _cl_close_margin_activities(self, feedback=False):
        """Close the margin approval activities of these orders, and only
        those: the current user's own is marked done with the feedback, the
        ones of the other approvers are removed."""
        activity_type = self.env.ref(ACTIVITY_TYPE_XMLID, raise_if_not_found=False)
        if not activity_type or not self:
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

    def _cl_drop_margin_requests(self):
        """Withdraw the requests still waiting on these orders (confirmed or
        cancelled in the meantime) so no approver is left with a task."""
        pending = self.filtered(lambda order: order.cl_margin_approval_state == 'to_approve')
        if pending:
            pending.write({'cl_margin_approval_state': 'none'})
            pending._cl_close_margin_activities()
        return pending

    def _cl_margin_notify_partners(self):
        """The salesperson, unless that is the user who decides."""
        self.ensure_one()
        return (self.user_id.partner_id - self.env.user.partner_id).ids

    # ------------------------------------------------------------------
    # Confirmation gate
    # ------------------------------------------------------------------
    def action_confirm(self):
        to_block = self.filtered(lambda order: order._cl_needs_margin_approval())
        if to_block and self.env.su:
            # Confirmed by the system (online payment, customer signature,
            # eCommerce, automation): nobody is in front of the screen to ask
            # for approval, and the customer has already committed.
            passed = to_block.filtered(lambda order: order.company_id.cl_margin_skip_automatic)
            for order in passed:
                order._message_log(body=_(
                    "Margin control: this order was confirmed automatically with a "
                    "margin of %(margin).2f%%, below the margin floor of "
                    "%(floor).2f%%. The margin approval was not enforced.",
                    margin=order._cl_margin_percent(),
                    floor=order.company_id.cl_margin_floor,
                ))
            to_block -= passed
        to_block._cl_request_margin_approval()
        remaining = self - to_block
        res = True
        if remaining:
            res = super(SaleOrder, remaining).action_confirm()
            # confirmed without a decision (the margin was fixed in the
            # meantime, or the confirmation was automatic): the request is void
            remaining._cl_drop_margin_requests()
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        self._cl_drop_margin_requests()
        return res

    def action_draft(self):
        # a cancelled order that becomes a quotation again starts from scratch
        cancelled = self.filtered(
            lambda order: order.state == 'cancel' and order.cl_margin_approval_state != 'none')
        res = super().action_draft()
        if cancelled:
            cancelled.write({
                'cl_margin_approval_state': 'none',
                'cl_margin_approved_percent': 0.0,
            })
        return res

    # ------------------------------------------------------------------
    # Approve / reject
    # ------------------------------------------------------------------
    def action_cl_margin_approve(self):
        self._cl_ensure_margin_approver()
        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError(_("%s is not a quotation any more.", order.display_name))
            order.write({
                'cl_margin_approval_state': 'approved',
                'cl_margin_approved_percent': order._cl_margin_percent(),
            })
            order._cl_close_margin_activities(
                _("Margin approved by %s.", self.env.user.display_name))
            order.message_post(
                body=_("Margin of %(margin).2f%% approved by %(user)s.",
                       margin=order._cl_margin_percent(),
                       user=self.env.user.display_name),
                partner_ids=order._cl_margin_notify_partners())
        # Normal confirmation, through every other module's checks. If one of
        # them raises, the approval above is rolled back with it.
        return self.action_confirm()

    def action_cl_margin_reject(self):
        self._cl_ensure_margin_approver()
        for order in self.filtered(lambda order: order.cl_margin_approval_state == 'to_approve'):
            order.write({
                'cl_margin_approval_state': 'none',
                'cl_margin_approved_percent': 0.0,
            })
            order._cl_close_margin_activities(
                _("Margin rejected by %s.", self.env.user.display_name))
            order.message_post(
                body=_("Margin rejected by %s. Adjust the order and confirm it again "
                       "to request a new approval.", self.env.user.display_name),
                partner_ids=order._cl_margin_notify_partners())
        return True

    # ------------------------------------------------------------------
    # The approval cannot be granted by writing the field directly
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        if not self.env.su:
            orders.filtered(
                lambda order: order.cl_margin_approval_state == 'approved'
            )._cl_ensure_margin_approver()
        return orders

    def write(self, vals):
        if vals.get('cl_margin_approval_state') == 'approved' and not self.env.su:
            self._cl_ensure_margin_approver()
        return super().write(vals)
