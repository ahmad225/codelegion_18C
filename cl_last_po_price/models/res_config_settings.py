# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_last_po_price = fields.Boolean(
        related='company_id.cl_last_po_price', readonly=False)
    cl_last_po_price_vendor = fields.Selection(
        related='company_id.cl_last_po_price_vendor', readonly=False, required=False)
    cl_last_po_price_products = fields.Selection(
        related='company_id.cl_last_po_price_products', readonly=False, required=False)
