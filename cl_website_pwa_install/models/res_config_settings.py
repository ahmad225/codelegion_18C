# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_pwa_enabled = fields.Boolean(
        related='website_id.cl_pwa_enabled', readonly=False)
    cl_pwa_name = fields.Char(
        related='website_id.cl_pwa_name', readonly=False)
    cl_pwa_short_name = fields.Char(
        related='website_id.cl_pwa_short_name', readonly=False)
    cl_pwa_theme_color = fields.Char(
        related='website_id.cl_pwa_theme_color', readonly=False)
    cl_pwa_background_color = fields.Char(
        related='website_id.cl_pwa_background_color', readonly=False)
    cl_pwa_icon = fields.Image(
        related='website_id.cl_pwa_icon', readonly=False)
