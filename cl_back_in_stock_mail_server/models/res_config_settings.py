# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Stored on the company of the website being configured, so the screen
    # shows and saves the value that website's emails really use.
    cl_back_in_stock_mail_server_id = fields.Many2one(
        related='website_id.company_id.cl_back_in_stock_mail_server_id', readonly=False)
