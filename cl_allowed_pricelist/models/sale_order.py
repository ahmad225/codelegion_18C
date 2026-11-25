# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Domain of the Pricelist field on the form (the field's own company
    # domain, narrowed to the customer's allowed pricelists when it has any).
    cl_pricelist_domain = fields.Binary(
        string='Pricelist Domain', compute='_compute_cl_pricelist_domain')

    def _cl_allowed_pricelists(self):
        """Pricelists this order is limited to; empty when it is not limited."""
        self.ensure_one()
        none = self.env['product.pricelist']
        if not self.partner_id or not self.company_id:
            return none
        # eCommerce orders get their pricelist from the website
        if 'website_id' in self._fields and self.website_id:
            return none
        return self.partner_id._cl_order_pricelists(self.company_id)

    @api.depends('partner_id', 'company_id')
    def _compute_cl_pricelist_domain(self):
        for order in self:
            domain = [('company_id', 'in', [False, order.company_id.id])]
            allowed = order._cl_allowed_pricelists()
            if allowed:
                domain.append(('id', 'in', allowed.ids))
            order.cl_pricelist_domain = domain

    @api.depends('partner_id', 'company_id')
    def _compute_pricelist_id(self):
        # EXTENDS sale: a new quotation starts on a pricelist the customer is
        # allowed, also when it is created by an import or through the API.
        super()._compute_pricelist_id()
        for order in self:
            if order.state != 'draft':
                continue
            allowed = order._cl_allowed_pricelists()
            if allowed and order.pricelist_id not in allowed:
                order.pricelist_id = allowed[0]

    @api.constrains('partner_id', 'company_id', 'pricelist_id')
    def _check_cl_pricelist_allowed(self):
        # Not for the system itself (connectors, scheduled jobs) nor for code
        # that asks to skip it: the rule is about what a person may choose.
        if self.env.su or self.env.context.get('cl_skip_pricelist_check'):
            return
        for order in self:
            if order.state not in ('draft', 'sent') or not order.pricelist_id:
                continue
            allowed = order._cl_allowed_pricelists()
            if allowed and order.pricelist_id not in allowed:
                raise ValidationError(_(
                    "%(customer)s cannot be sold on the pricelist %(pricelist)s.\n"
                    "Allowed for this customer: %(allowed)s.",
                    customer=order.partner_id.commercial_partner_id.display_name,
                    pricelist=order.pricelist_id.display_name,
                    allowed=", ".join(allowed.mapped('display_name'))))
