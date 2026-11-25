# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import math

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

PAGE_URL = '/my/previously-ordered'


class ReorderPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _cl_reorder_entries(self):
        return request.env['sale.order']._cl_reorder_history(
            request.env.user.partner_id, request.website)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'cl_reorder_count' in counters:
            values['cl_reorder_count'] = len(self._cl_reorder_entries())
        return values

    # ------------------------------------------------------------------
    # Page
    # ------------------------------------------------------------------
    @http.route(PAGE_URL, type='http', auth='user', website=True, sitemap=False)
    def cl_reorder_page(self, search=None, skipped=None, **kwargs):
        entries = self._cl_reorder_entries()
        total = len(entries)
        search = (search or '').strip()
        if search:
            needle = search.lower()
            entries = [
                entry for entry in entries
                if needle in (entry['product'].name or '').lower()
                or needle in (entry['product'].default_code or '').lower()
            ]
        try:
            skipped = max(int(skipped or 0), 0)
        except ValueError:
            skipped = 0
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'cl_reorder',
            'entries': entries,
            'total': total,
            'search': search,
            'skipped': skipped,
            'add_all': request.website.cl_reorder_add_all,
            'page_url': PAGE_URL,
        })
        return request.render('cl_previously_ordered_products.portal_reorder_page', values)

    # ------------------------------------------------------------------
    # Add to cart
    # ------------------------------------------------------------------
    @staticmethod
    def _cl_reorder_quantity(value):
        """Whole, positive quantity from a form value; 0 when it is not one."""
        try:
            quantity = float(value)
        except (TypeError, ValueError):
            return 0
        if not math.isfinite(quantity) or quantity <= 0:
            return 0
        return max(1, math.ceil(quantity - 1e-9))

    def _cl_reorder_add(self, wanted):
        """Put ``wanted`` ({product id: quantity}) in the visitor's cart through
        the shop's own cart method, so prices, taxes, stock rules and
        promotions apply as usual. Returns (number added, number skipped)."""
        website = request.website
        cart = website.sale_get_order(force_create=True)
        if cart.state != 'draft':
            # the session still points at an order that was confirmed meanwhile
            request.session['sale_order_id'] = None
            cart = website.sale_get_order(force_create=True)
        added = skipped = 0
        for product_id, quantity in wanted.items():
            try:
                with request.env.cr.savepoint():
                    cart._cart_update(product_id=product_id, add_qty=quantity)
                added += 1
            except UserError:
                # not sold any more: leave it out, keep the rest
                skipped += 1
        request.session['website_sale_cart_quantity'] = cart.cart_quantity
        return added, skipped

    @http.route(PAGE_URL + '/add', type='http', auth='user', methods=['POST'],
                website=True, sitemap=False)
    def cl_reorder_add(self, only=None, **post):
        """One form serves the whole page: ``qty_<product id>`` fields hold
        the quantities; ``only`` is set by a row's own button, and absent when
        "Add all to cart" was used."""
        # Only products of the customer's own history can be added from here.
        history = {entry['product'].id for entry in self._cl_reorder_entries()}
        quantities = {}
        for key, value in post.items():
            if not key.startswith('qty_'):
                continue
            try:
                product_id = int(key[4:])
            except ValueError:
                continue
            quantity = self._cl_reorder_quantity(value)
            if product_id in history and quantity:
                quantities[product_id] = quantity

        if only:
            try:
                only = int(only)
            except ValueError:
                only = 0
            wanted = {only: quantities[only]} if only in quantities else {}
        elif request.website.cl_reorder_add_all:
            wanted = quantities
        else:
            wanted = {}

        if not wanted:
            return request.redirect(PAGE_URL)
        added, skipped = self._cl_reorder_add(wanted)
        if not added:
            return request.redirect('%s?skipped=%s' % (PAGE_URL, skipped))
        return request.redirect('/shop/cart')
