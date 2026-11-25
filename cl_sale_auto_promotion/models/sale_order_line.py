# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cl_auto_applied = fields.Boolean(
        string='Added Automatically', copy=False, readonly=True,
        help="Reward line added by the automatic promotions. It is recomputed "
             "whenever the quotation lines change.")

    def _cl_get_promotion_saving(self):
        """Amount the customer saves thanks to this reward line (tax excluded).

        Discounts count for their own amount. A free product counts for the
        price it would have on this order (its pricelist price in the order
        currency, before the 100% discount). eWallet and gift card lines are a
        means of payment, not a saving, and are ignored.
        """
        self.ensure_one()
        line = self.sudo()
        reward = line.reward_id
        if not reward or reward.program_id.is_payment_program:
            return 0.0
        if reward.reward_type == 'discount':
            return abs(line.price_subtotal)
        if reward.reward_type == 'product':
            order = line.order_id
            taxes = line.tax_id.compute_all(
                line.price_unit,
                currency=order.currency_id,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=order.partner_shipping_id,
            )
            return taxes['total_excluded']
        return 0.0
