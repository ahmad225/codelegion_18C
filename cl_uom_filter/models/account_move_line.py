# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    cl_allowed_uom_ids = fields.Many2many(
        comodel_name='uom.uom',
        string="Allowed Units",
        compute='_compute_cl_allowed_uom_ids',
        help="Units selected on the product. Only these can be chosen on this line.",
    )
    # Only the filter of the standard field is changed.
    product_uom_id = fields.Many2one(domain="[('id', 'in', cl_allowed_uom_ids)]")

    @api.depends('product_id', 'product_id.product_uom_ids', 'product_id.uom_id')
    def _compute_cl_allowed_uom_ids(self):
        for line in self:
            line.cl_allowed_uom_ids = line.product_id._cl_get_allowed_uoms()
