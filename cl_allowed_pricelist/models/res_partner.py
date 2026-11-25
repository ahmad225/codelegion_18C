# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cl_order_pricelist_ids = fields.Many2many(
        'product.pricelist',
        'cl_res_partner_order_pricelist_rel', 'partner_id', 'pricelist_id',
        string='Allowed Pricelists',
        help="Sales orders for this customer can only use one of these "
             "pricelists (and the pricelist set on the customer itself). "
             "Leave empty to allow any pricelist.",
    )

    def _cl_order_pricelists(self, company):
        """Pricelists this customer may be sold on in ``company``.

        The list is kept on the commercial entity, so it holds for every
        contact of a company. An empty result means: no restriction.
        """
        self.ensure_one()
        commercial = self.commercial_partner_id.with_company(company)
        allowed = commercial.cl_order_pricelist_ids.filtered(
            lambda pricelist: not pricelist.company_id or pricelist.company_id == company)
        if not allowed:
            return allowed
        # The pricelist somebody chose on the customer form always stays
        # usable. Odoo's computed fallback (first pricelist of the country or
        # of the company) is not a choice made for this customer: it is not
        # added.
        own = commercial.specific_property_product_pricelist
        if own.active and (not own.company_id or own.company_id == company):
            allowed |= own
        return allowed
