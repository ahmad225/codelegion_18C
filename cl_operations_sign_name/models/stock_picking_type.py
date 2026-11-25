# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    cl_sign_block = fields.Boolean(
        string='Sign-off Block on Printout',
        help="Print three boxes to fill in by hand - name, date and time, "
             "signature - at the end of the Picking Operations and Batch "
             "Transfer documents of this operation type.")
