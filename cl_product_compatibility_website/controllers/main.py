# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleCompatibility(WebsiteSale):

    def _check_cart(self, order_sudo):
        # Standard checks first (empty cart, public order rules, ...).
        redirection = super()._check_cart(order_sudo)
        if redirection:
            return redirection
        # Then keep the customer on the cart page while it has mismatches; the
        # cart template explains why.
        if order_sudo._cl_compatibility_mismatches():
            return request.redirect('/shop/cart')
