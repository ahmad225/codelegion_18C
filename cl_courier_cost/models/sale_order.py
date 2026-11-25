# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .cl_courier_cost import USER_GROUP


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_company_currency_id = fields.Many2one(related='company_id.currency_id', string='Company Currency')
    cl_has_courier_formula = fields.Boolean(compute='_compute_cl_courier_cost', groups=USER_GROUP)
    cl_courier_cost_expected = fields.Monetary(
        string='Expected Courier Cost', compute='_compute_cl_courier_cost',
        currency_field='cl_company_currency_id', groups=USER_GROUP,
        help="Internal estimate from the delivery method's courier cost formula, in company currency. "
             "It is not charged to the customer.")
    cl_courier_cost_message = fields.Char(compute='_compute_cl_courier_cost', groups=USER_GROUP)

    @api.depends('carrier_id', 'shipping_weight', 'order_line.product_id', 'order_line.product_uom_qty',
                 'order_line.product_uom', 'order_line.price_subtotal')
    def _compute_cl_courier_cost(self):
        for order in self:
            formula = order.carrier_id.sudo().cl_courier_formula_id
            cost, message = 0.0, False
            if formula and formula.state != 'validated':
                message = _("Formula %s is not validated.", formula.name)
            elif formula:
                try:
                    cost, _values = formula._cl_compute(order._cl_courier_source_values())
                except psycopg2.Error:
                    raise
                except Exception as exc:  # noqa: BLE001 - a preview must never break the order form
                    message = _("Cannot compute: %s", exc.args[0] if isinstance(exc, UserError) else exc)
            order.cl_has_courier_formula = bool(formula)
            order.cl_courier_cost_expected = cost
            order.cl_courier_cost_message = message

    def _cl_goods_lines(self):
        return self.order_line.filtered(
            lambda line: not line.is_delivery and not line.display_type and line.product_id
            and line.product_id.type == 'consu' and line.product_uom_qty > 0)

    def _cl_goods_untaxed_company(self):
        """Untaxed amount of the order without delivery lines, in company currency."""
        self.ensure_one()
        amount = sum(self.order_line.filtered(
            lambda line: not line.is_delivery and not line.display_type).mapped('price_subtotal'))
        company = self.company_id
        if self.currency_id and company and self.currency_id != company.currency_id:
            date = (self.date_order or fields.Datetime.now()).date()
            amount = self.currency_id._convert(amount, company.currency_id, company, date)
        return amount

    def _cl_courier_source_values(self):
        """Delivery values estimated from the order lines (quantities in product units)."""
        self.ensure_one()
        weight = volume = quantity = 0.0
        lines = self._cl_goods_lines()
        for line in lines:
            product = line.product_id
            qty = line.product_uom._compute_quantity(line.product_uom_qty, product.uom_id)
            quantity += qty
            weight += qty * product.weight
            volume += qty * product.volume
        return {
            'shipping_weight': self.shipping_weight or weight,
            'weight': weight,
            'volume': volume,
            'packages': 1.0 if lines else 0.0,
            'lines': float(len(lines)),
            'quantity': quantity,
            'untaxed': self._cl_goods_untaxed_company(),
        }
