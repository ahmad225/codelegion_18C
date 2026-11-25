# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _is_cart_ready(self):
        # Used by the shop to enable the "Checkout" button and before paying.
        ready = super()._is_cart_ready()
        if ready:
            ready = not any(cart._cl_compatibility_mismatches() for cart in self.sudo())
        return ready

    def _check_cart_is_ready_to_be_paid(self):
        # Last server-side gate before a payment is created. It also covers
        # express checkout, which skips the checkout pages.
        for cart in self.sudo():
            messages = cart._cl_compatibility_messages(website=True)
            if messages:
                raise ValidationError(_(
                    "Some products in your cart do not fit together. "
                    "Please adjust your cart before paying.\n%s",
                    "\n".join(messages)))
        return super()._check_cart_is_ready_to_be_paid()
