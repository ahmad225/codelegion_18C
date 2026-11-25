# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.osv import expression

from odoo.addons.website_sale.controllers import main


class WebsiteSale(main.WebsiteSale):

    def _add_search_subdomains_hook(self, search):
        # The shop list itself is searched through product.template
        # ._search_get_detail(); this hook only feeds the domain used to work
        # out the bounds of the price filter. ``search`` is one typed word.
        domain = super()._add_search_subdomains_hook(search)
        by_keyword = [('cl_keyword_search_text', 'ilike', search)]
        return expression.OR([domain, by_keyword]) if domain else by_keyword
