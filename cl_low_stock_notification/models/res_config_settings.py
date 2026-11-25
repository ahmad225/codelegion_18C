# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_low_stock_alert = fields.Boolean(
        related='company_id.cl_low_stock_alert', readonly=False)
    cl_low_stock_source = fields.Selection(
        related='company_id.cl_low_stock_source', readonly=False)
    cl_low_stock_min_qty = fields.Float(
        related='company_id.cl_low_stock_min_qty', readonly=False)
    cl_low_stock_basis = fields.Selection(
        related='company_id.cl_low_stock_basis', readonly=False)
    cl_low_stock_location_ids = fields.Many2many(
        related='company_id.cl_low_stock_location_ids', readonly=False)
    cl_low_stock_user_ids = fields.Many2many(
        related='company_id.cl_low_stock_user_ids', readonly=False)
    cl_low_stock_tz = fields.Selection(
        related='company_id.cl_low_stock_tz', readonly=False)
