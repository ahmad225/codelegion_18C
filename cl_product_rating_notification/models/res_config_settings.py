# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Stored on the company of the website being configured: reviews posted
    # on that website notify that company's team.
    cl_rating_template_id = fields.Many2one(
        related='website_id.company_id.cl_rating_template_id', readonly=False)
    cl_rating_partner_ids = fields.Many2many(
        related='website_id.company_id.cl_rating_partner_ids', readonly=False)
