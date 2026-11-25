# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env['sale.order'].browse(
            {vals['order_id'] for vals in vals_list if vals.get('order_id')})
        orders._cl_check_pending_edit()
        lines = super().create(vals_list)
        lines.order_id._cl_touch_activity()
        return lines

    def write(self, vals):
        self.order_id._cl_check_pending_edit()
        res = super().write(vals)
        self.order_id._cl_touch_activity()
        return res

    def unlink(self):
        orders = self.order_id
        orders._cl_check_pending_edit()
        res = super().unlink()
        orders.exists()._cl_touch_activity()
        return res
