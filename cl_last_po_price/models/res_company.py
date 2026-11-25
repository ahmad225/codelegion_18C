# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_last_po_price = fields.Boolean(
        string='Use Last Purchase Price',
        help="Start new purchase order lines from the price (and discount) of "
             "the product's most recently confirmed purchase order.",
    )
    cl_last_po_price_vendor = fields.Selection(
        selection=[
            ('same', 'The same vendor only'),
            ('any', 'Any vendor'),
        ],
        string='Last Price Taken From',
        default='same',
        required=True,
        help="Which earlier purchase orders count when looking for the last price.",
    )
    cl_last_po_price_products = fields.Selection(
        selection=[
            ('all', 'All products'),
            ('variants', 'Products with variants only'),
        ],
        string='Last Price Applies To',
        default='all',
        required=True,
        help="Limit the last purchase price to products that have variants.",
    )
