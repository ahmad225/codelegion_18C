# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models

_MIN_QTY_HELP = (
    "The product is reported as low when its stock falls below this quantity. "
    "Used when the Low Stock Alerts threshold is 'Minimum set on each product' "
    "(Inventory settings). Leave at 0 to never report this product."
)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cl_low_stock_min_qty = fields.Float(
        string='Low Stock Below', digits='Product Unit of Measure', help=_MIN_QTY_HELP)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Same idiom as barcode / weight in standard Odoo: the template shows the
    # value of its only variant and writes it back to that variant.
    cl_low_stock_min_qty = fields.Float(
        string='Low Stock Below', digits='Product Unit of Measure',
        compute='_compute_cl_low_stock_min_qty',
        inverse='_inverse_cl_low_stock_min_qty',
        store=True, help=_MIN_QTY_HELP)

    @api.depends('product_variant_ids.cl_low_stock_min_qty')
    def _compute_cl_low_stock_min_qty(self):
        self._compute_template_field_from_variant_field('cl_low_stock_min_qty', default=0.0)

    def _inverse_cl_low_stock_min_qty(self):
        self._set_product_variant_field('cl_low_stock_min_qty')

    def _get_related_fields_variant_template(self):
        # A value given when the template is created goes to its first variant.
        return super()._get_related_fields_variant_template() + ['cl_low_stock_min_qty']
