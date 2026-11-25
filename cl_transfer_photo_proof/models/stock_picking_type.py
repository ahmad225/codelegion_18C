# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    cl_require_photo_proof = fields.Boolean(
        string='Require Photo Proof per Product',
        help="Every product line processed in a transfer of this type needs at least one "
             "photo or PDF before the transfer can be validated. Lines left at zero for a "
             "backorder do not need one.")
