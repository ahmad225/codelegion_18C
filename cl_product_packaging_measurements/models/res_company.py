# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


def _uom_category_domain(model, category_xmlid):
    category = model.env.ref(category_xmlid, raise_if_not_found=False)
    return [('category_id', '=', category.id if category else False)]


def length_uom_domain(model):
    """Units a dimension can be expressed in (length category)."""
    return _uom_category_domain(model, 'uom.uom_categ_length')


def weight_uom_domain(model):
    """Units a gross weight can be expressed in (weight category)."""
    return _uom_category_domain(model, 'uom.product_uom_categ_kgm')


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_packaging_length_uom_id = fields.Many2one(
        'uom.uom', string='Packaging Dimension Unit', ondelete='restrict',
        domain=length_uom_domain,
        default=lambda self: self.env.ref('uom.product_uom_millimeter', raise_if_not_found=False),
        help="Unit of the length, width and height of product packagings.")
    cl_packaging_length_uom_free = fields.Boolean(
        string='Own Dimension Unit per Packaging',
        help="Let each packaging use another dimension unit than the one above. "
             "When off, every packaging uses the company unit.")
    cl_packaging_weight_uom_id = fields.Many2one(
        'uom.uom', string='Packaging Weight Unit', ondelete='restrict',
        domain=weight_uom_domain,
        default=lambda self: self.env.ref('uom.product_uom_kgm', raise_if_not_found=False),
        help="Unit of the gross weight of product packagings.")
    cl_packaging_weight_uom_free = fields.Boolean(
        string='Own Weight Unit per Packaging',
        help="Let each packaging use another weight unit than the one above. "
             "When off, every packaging uses the company unit.")

    def write(self, vals):
        result = super().write(vals)
        if vals.keys() & {
                'cl_packaging_length_uom_id', 'cl_packaging_length_uom_free',
                'cl_packaging_weight_uom_id', 'cl_packaging_weight_uom_free'}:
            self._cl_align_packaging_units()
        return result

    def _cl_align_packaging_units(self):
        """Apply the company units to the packagings that must follow them:
        those of the company, and shared ones of its (or shared) products."""
        Packaging = self.env['product.packaging'].sudo()
        for company in self:
            Packaging.search([
                '|', ('company_id', '=', company.id),
                '&', ('company_id', '=', False),
                     ('product_id.company_id', 'in', (company.id, False)),
            ])._cl_align_units(company)
