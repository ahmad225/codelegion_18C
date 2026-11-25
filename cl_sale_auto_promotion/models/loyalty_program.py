# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def _cl_is_automatic_promotion(self):
        """Whether rewards of this program may be claimed without the salesperson.

        Only programs that trigger on their own and are used up on the current
        order qualify. Loyalty cards and eWallets (nominative), gift cards and
        eWallets (payment programs), coupons and discount codes (need a code)
        and next-order coupons (future orders) are left to the salesperson.
        """
        self.ensure_one()
        return bool(
            self.trigger == 'auto'
            and self.applies_on == 'current'
            and not self.is_nominative
            and not self.is_payment_program
            and any(rule.mode == 'auto' for rule in self.rule_ids)
        )
