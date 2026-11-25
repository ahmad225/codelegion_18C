# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models

from .res_partner import ORDER_REVIEW_ACTIVITY


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_customer_approval_warning = fields.Char(compute='_compute_cl_customer_approval_warning')

    @api.depends('partner_id.commercial_partner_id.cl_approval_state', 'company_id', 'state')
    def _compute_cl_customer_approval_warning(self):
        for order in self:
            warning = False
            if order._cl_customer_not_approved():
                customer = order.partner_id.commercial_partner_id.display_name
                if order.state in ('draft', 'sent'):
                    warning = _("%s is not an approved customer yet: this order cannot be confirmed "
                                "until the customer is approved.", customer)
                elif order.state == 'sale':
                    warning = _("%s is not an approved customer yet: this order was confirmed online "
                                "and is waiting for the customer's approval.", customer)
            order.cl_customer_approval_warning = warning

    def _cl_customer_not_approved(self):
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        company = (self.company_id or self.env.company).sudo()
        return bool(partner) and company.cl_contact_approval_enabled and partner.sudo().cl_approval_state != 'approved'

    def _cl_is_online_confirmation(self):
        """Signature and payment flows of the portal and web shop run as superuser
        (or as the portal/public user); the back office runs as an internal user."""
        return self.env.su or not self.env.user._is_internal()

    def _confirmation_error_message(self):
        error = super()._confirmation_error_message()
        if error or self._cl_is_online_confirmation() or not self._cl_customer_not_approved():
            return error
        return _("%(order)s cannot be confirmed: %(customer)s is not an approved customer yet. "
                 "Send the customer for approval from its contact form.",
                 order=self.name, customer=self.partner_id.commercial_partner_id.display_name)

    def action_confirm(self):
        to_review = self.browse()
        if self._cl_is_online_confirmation():
            to_review = self.filtered(lambda o: o.state in ('draft', 'sent') and o._cl_customer_not_approved())
        res = super().action_confirm()
        for order in to_review.filtered(lambda o: o.state == 'sale'):
            order._cl_flag_unapproved_customer_order()
        return res

    def _cl_flag_unapproved_customer_order(self):
        self.ensure_one()
        order = self.sudo()
        customer = order.partner_id.commercial_partner_id
        message = _("Confirmed online for %s, who is not an approved customer yet. "
                    "Please review the customer.", customer.display_name)
        # Runs in the customer's (possibly public) session: _message_log needs no email address.
        order._message_log(body=message)
        self.env['res.partner']._cl_schedule_approver_activities(
            order, ORDER_REVIEW_ACTIVITY, order.company_id,
            summary=_('Review unapproved customer'), note=message)
