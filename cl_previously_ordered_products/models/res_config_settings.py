# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Edited for the website selected at the top of the Website settings
    cl_reorder_orders_scanned = fields.Integer(
        related='website_id.cl_reorder_orders_scanned', readonly=False)
    cl_reorder_add_all = fields.Boolean(
        related='website_id.cl_reorder_add_all', readonly=False)
