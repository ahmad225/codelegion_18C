# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_artwork_block_sale = fields.Boolean(
        related='company_id.cl_artwork_block_sale', readonly=False)
    cl_artwork_block_production = fields.Boolean(
        related='company_id.cl_artwork_block_production', readonly=False)
    cl_artwork_attach_production = fields.Boolean(
        related='company_id.cl_artwork_attach_production', readonly=False)
