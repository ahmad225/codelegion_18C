# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.tools import float_compare

from .sale_order import MARGIN_DIGITS


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Like Odoo's own margin fields, these are for internal users only: they
    # give the cost away, and portal customers can read their order lines.
    cl_margin_pct = fields.Float(
        string='Line Margin (%)',
        compute='_compute_cl_margin_pct',
        groups='base.group_user')
    cl_margin_low = fields.Boolean(
        string='Low Margin',
        compute='_compute_cl_margin_low',
        groups='base.group_user')

    @api.depends('margin_percent')
    def _compute_cl_margin_pct(self):
        # Odoo's standard line margin (a ratio), shown as a percentage
        for line in self:
            line.cl_margin_pct = line.margin_percent * 100.0

    @api.depends('cl_margin_pct', 'display_type', 'price_subtotal',
                 'company_id.cl_margin_line_alert',
                 'company_id.cl_margin_line_alert_below')
    def _compute_cl_margin_low(self):
        for line in self:
            company = line.company_id or line.order_id.company_id or self.env.company
            line.cl_margin_low = bool(
                company.cl_margin_line_alert
                and not line.display_type
                and line.price_subtotal
                and float_compare(
                    line.cl_margin_pct,
                    company.cl_margin_line_alert_below,
                    precision_digits=MARGIN_DIGITS) < 0)
