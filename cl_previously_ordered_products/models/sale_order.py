# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import math

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _cl_reorder_line_counts(self, line, website):
        """Is this past order line something the customer can buy again here?"""
        product = line.product_id
        if line.display_type or not product or line.product_uom_qty <= 0:
            return False
        # shipping, down payments and loyalty rewards are not purchases
        if line.is_downpayment:
            return False
        if 'is_delivery' in line._fields and line.is_delivery:
            return False
        if 'is_reward_line' in line._fields and line.is_reward_line:
            return False
        # still sold on this website
        return bool(
            product.active and product.sale_ok and product.is_published
            and (not product.website_id or product.website_id == website))

    @api.model
    def _cl_reorder_history(self, partner, website, limit=None):
        """Products the customer bought before on ``website``, most recent first.

        The customer is the whole company (commercial entity): a buyer sees
        what colleagues ordered too. Only the latest ``limit`` confirmed
        orders are read (default: the website setting).

        :return: list of dicts with ``product``, ``quantity`` (last ordered
            quantity, in the product's own unit, as the shop sells it),
            ``uom``, ``date`` (of the latest order) and ``times`` (number of
            those orders the product is on)
        """
        if limit is None:
            limit = website.cl_reorder_orders_scanned
        if not partner or limit <= 0:
            return []
        orders = self.sudo().search([
            ('partner_id', 'child_of', partner.commercial_partner_id.id),
            ('state', '=', 'sale'),
            ('company_id', '=', website.company_id.id),
        ], order='date_order desc, id desc', limit=limit)

        history = {}
        for order in orders:
            seen_on_order = set()
            for line in order.order_line:
                if not self._cl_reorder_line_counts(line, website):
                    continue
                product = line.product_id
                entry = history.get(product.id)
                if entry is None:
                    # first time met = latest order: this is the "last" quantity
                    entry = history[product.id] = {
                        'product': product,
                        'quantity': 0.0,
                        'uom': product.uom_id,
                        'date': order.date_order,
                        'times': 0,
                        'latest_order_id': order.id,
                    }
                if entry['latest_order_id'] == order.id:
                    # the cart works in the product's unit: 2 Dozens are 24 Units
                    entry['quantity'] += line.product_uom._compute_quantity(
                        line.product_uom_qty, product.uom_id)
                if product.id not in seen_on_order:
                    seen_on_order.add(product.id)
                    entry['times'] += 1
        for entry in history.values():
            # the web cart takes whole quantities
            entry['cart_quantity'] = max(1, math.ceil(entry['quantity'] - 1e-9))
        return list(history.values())
