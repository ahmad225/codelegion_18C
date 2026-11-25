# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReorderHistory(TransactionCase):
    """What the Previously Ordered page lists.

    Run with:  odoo-bin -d <db> -i cl_previously_ordered_products
               --test-tags /cl_previously_ordered_products
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.SO = cls.env['sale.order']
        cls.website = cls.env['website'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        if not cls.website:
            cls.website = cls.env['website'].create(
                {'name': 'Reorder Test Shop', 'company_id': cls.env.company.id})
        cls.acme = cls.env['res.partner'].create({'name': 'Acme Corp', 'is_company': True})
        cls.buyer = cls.env['res.partner'].create({'name': 'Buyer', 'parent_id': cls.acme.id})
        cls.colleague = cls.env['res.partner'].create(
            {'name': 'Colleague', 'parent_id': cls.acme.id})
        cls.stranger = cls.env['res.partner'].create({'name': 'Somebody Else'})

        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.uom_dozen = cls.env.ref('uom.product_uom_dozen')
        cls.product = cls._product('Reorderable')
        cls.other = cls._product('Reorderable Too')

    @classmethod
    def _product(cls, name, **vals):
        return cls.env['product.product'].create(dict({
            'name': name, 'type': 'consu', 'sale_ok': True, 'is_published': True,
            'list_price': 10.0,
            'uom_id': cls.uom_unit.id,
        }, **vals))

    def _order(self, partner, lines, confirm=True, days_ago=0):
        """lines: list of (product, quantity) or (product, quantity, uom)."""
        order = self.SO.create({
            'partner_id': partner.id,
            'order_line': [Command.create(dict(
                {'product_id': line[0].id, 'product_uom_qty': line[1]},
                **({'product_uom': line[2].id} if len(line) > 2 else {})
            )) for line in lines],
        })
        if confirm:
            order.action_confirm()
            if days_ago:
                order.date_order = fields.Datetime.now() - timedelta(days=days_ago)
        return order

    def _history(self, partner, **kwargs):
        return self.SO._cl_reorder_history(partner, self.website, **kwargs)

    def _entry(self, partner, product, **kwargs):
        return next((e for e in self._history(partner, **kwargs) if e['product'] == product), None)

    # ------------------------------------------------------------------
    def test_own_order_is_listed_with_its_quantity(self):
        self._order(self.buyer, [(self.product, 3)])
        entry = self._entry(self.buyer, self.product)
        self.assertTrue(entry)
        self.assertEqual(entry['quantity'], 3)
        self.assertEqual(entry['cart_quantity'], 3)
        self.assertEqual(entry['times'], 1)
        self.assertEqual(entry['uom'], self.uom_unit)

    def test_orders_of_the_whole_company_are_listed(self):
        self._order(self.acme, [(self.product, 1)])
        self._order(self.colleague, [(self.other, 1)])
        products = [e['product'] for e in self._history(self.buyer)]
        self.assertIn(self.product, products)
        self.assertIn(self.other, products)

    def test_other_customers_orders_are_not_listed(self):
        self._order(self.stranger, [(self.product, 1)])
        self.assertFalse(self._history(self.buyer))

    def test_quotations_and_cancelled_orders_are_not_listed(self):
        self._order(self.buyer, [(self.product, 1)], confirm=False)
        cancelled = self._order(self.buyer, [(self.other, 1)])
        cancelled._action_cancel()
        self.assertFalse(self._history(self.buyer))

    def test_latest_order_gives_the_quantity_and_all_orders_are_counted(self):
        self._order(self.buyer, [(self.product, 9)], days_ago=30)
        self._order(self.buyer, [(self.product, 2)])
        entry = self._entry(self.buyer, self.product)
        self.assertEqual(entry['quantity'], 2)
        self.assertEqual(entry['times'], 2)

    def test_quantity_is_given_in_the_unit_the_shop_sells(self):
        """Two dozens ordered in the back office are 24 units in the cart."""
        self._order(self.buyer, [(self.product, 2, self.uom_dozen)])
        entry = self._entry(self.buyer, self.product)
        self.assertEqual(entry['quantity'], 24)
        self.assertEqual(entry['cart_quantity'], 24)

    def test_fractional_quantity_is_rounded_up_for_the_cart(self):
        self._order(self.buyer, [(self.product, 0.5)])
        entry = self._entry(self.buyer, self.product)
        self.assertEqual(entry['quantity'], 0.5)
        self.assertEqual(entry['cart_quantity'], 1)

    def test_products_no_longer_sold_online_are_left_out(self):
        unpublished = self._product('Not Online Any More')
        archived = self._product('Discontinued')
        self._order(self.buyer, [(unpublished, 1), (archived, 1), (self.product, 1)])
        unpublished.is_published = False
        archived.active = False
        products = [e['product'] for e in self._history(self.buyer)]
        self.assertEqual(products, [self.product])

    def test_setting_limits_the_orders_looked_at(self):
        self._order(self.buyer, [(self.other, 1)], days_ago=10)
        self._order(self.buyer, [(self.product, 1)])
        self.website.cl_reorder_orders_scanned = 1
        self.assertEqual([e['product'] for e in self._history(self.buyer)], [self.product])
        self.website.cl_reorder_orders_scanned = 0
        self.assertFalse(self._history(self.buyer))
        # an explicit limit wins over the setting
        self.assertEqual(len(self._history(self.buyer, limit=5)), 2)
