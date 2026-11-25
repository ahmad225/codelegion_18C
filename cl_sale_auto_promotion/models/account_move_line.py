# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _cl_get_promotion_saving(self):
        """Saving carried by this invoice line, when it invoices a reward line."""
        self.ensure_one()
        line = self.sudo()
        if line.display_type != 'product':
            return 0.0
        reward = line.sale_line_ids.reward_id[:1]
        if not reward or reward.program_id.is_payment_program:
            return 0.0
        if reward.reward_type == 'discount':
            return abs(line.price_subtotal)
        if reward.reward_type == 'product':
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=line.currency_id,
                quantity=line.quantity,
                product=line.product_id,
                partner=line.partner_id,
            )
            return taxes['total_excluded']
        return 0.0
