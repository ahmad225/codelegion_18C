# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_margin_line_alert = fields.Boolean(
        related='company_id.cl_margin_line_alert', readonly=False)
    cl_margin_line_alert_below = fields.Float(
        related='company_id.cl_margin_line_alert_below', readonly=False)
    cl_margin_order_alert = fields.Boolean(
        related='company_id.cl_margin_order_alert', readonly=False)
    cl_margin_order_alert_below = fields.Float(
        related='company_id.cl_margin_order_alert_below', readonly=False)
    cl_margin_floor_enabled = fields.Boolean(
        related='company_id.cl_margin_floor_enabled', readonly=False)
    cl_margin_floor = fields.Float(
        related='company_id.cl_margin_floor', readonly=False)
    cl_margin_approver_group_id = fields.Many2one(
        related='company_id.cl_margin_approver_group_id', readonly=False)
    cl_margin_skip_automatic = fields.Boolean(
        related='company_id.cl_margin_skip_automatic', readonly=False)
