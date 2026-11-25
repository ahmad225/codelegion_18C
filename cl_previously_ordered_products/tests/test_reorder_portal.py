# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.http import Request
from odoo.tests import HttpCase, new_test_user, tagged

from ..controllers.main import ReorderPortal


@tagged('post_install', '-at_install')
class TestReorderPortal(HttpCase):
    """The portal page and its add-to-cart form, as a portal customer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.website = cls.env['website'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.portal_user = new_test_user(
            cls.env, login='cl_reorder_portal', groups='base.group_portal')
        cls.partner = cls.portal_user.partner_id
        cls.bought = cls.env['product.product'].create({
            'name': 'CL Bought Before', 'type': 'consu', 'sale_ok': True,
            'is_published': True, 'list_price': 10.0})
        cls.bought_too = cls.env['product.product'].create({
            'name': 'CL Bought Before Too', 'type': 'consu', 'sale_ok': True,
            'is_published': True, 'list_price': 20.0})
        cls.never_bought = cls.env['product.product'].create({
            'name': 'CL Never Bought', 'type': 'consu', 'sale_ok': True,
            'is_published': True, 'list_price': 30.0})
        order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [
                Command.create({'product_id': cls.bought.id, 'product_uom_qty': 3}),
                Command.create({'product_id': cls.bought_too.id, 'product_uom_qty': 1}),
            ],
        })
        order.action_confirm()

    def setUp(self):
        super().setUp()
        if not self.website:
            self.skipTest("No website for the current company")
        self.authenticate('cl_reorder_portal', 'cl_reorder_portal')

    def _cart(self):
        self.env.invalidate_all()
        return self.env['sale.order'].search([
            ('partner_id', '=', self.partner.id),
            ('state', '=', 'draft'),
            ('website_id', '!=', False),
        ])

    def _post(self, **data):
        return self.url_open(
            '/my/previously-ordered/add',
            data=dict(data, csrf_token=Request.csrf_token(self)),
            allow_redirects=False)

    # ------------------------------------------------------------------
    def test_quantity_parsing(self):
        parse = ReorderPortal._cl_reorder_quantity
        self.assertEqual(parse('3'), 3)
        self.assertEqual(parse('2.2'), 3)
        self.assertEqual(parse('0'), 0)
        self.assertEqual(parse('-5'), 0)
        self.assertEqual(parse('abc'), 0)
        self.assertEqual(parse(None), 0)
        self.assertEqual(parse('inf'), 0)
        self.assertEqual(parse('nan'), 0)

    def test_page_lists_the_products_bought_before(self):
        response = self.url_open('/my/previously-ordered')
        self.assertEqual(response.status_code, 200)
        self.assertIn('CL Bought Before', response.text)
        self.assertNotIn('CL Never Bought', response.text)

        response = self.url_open('/my/previously-ordered?search=before+too')
        self.assertIn('CL Bought Before Too', response.text)
        self.assertNotIn('qty_%s"' % self.bought.id, response.text)

    def test_row_button_adds_that_product_only(self):
        response = self._post(**{
            'only': str(self.bought.id),
            'qty_%s' % self.bought.id: '2',
            'qty_%s' % self.bought_too.id: '1',
        })
        self.assertIn(response.status_code, (302, 303))
        self.assertTrue(response.headers['Location'].endswith('/shop/cart'))
        lines = self._cart().order_line
        self.assertEqual(lines.product_id, self.bought)
        self.assertEqual(lines.product_uom_qty, 2)

    def test_add_all_uses_the_quantities_shown(self):
        self._post(**{
            'qty_%s' % self.bought.id: '4',
            'qty_%s' % self.bought_too.id: '1',
        })
        quantities = {line.product_id: line.product_uom_qty for line in self._cart().order_line}
        self.assertEqual(quantities, {self.bought: 4, self.bought_too: 1})

    def test_add_all_can_be_switched_off(self):
        self.website.cl_reorder_add_all = False
        response = self._post(**{'qty_%s' % self.bought.id: '4'})
        self.assertTrue(response.headers['Location'].endswith('/my/previously-ordered'))
        self.assertFalse(self._cart().order_line)

    def test_only_products_of_the_history_and_positive_quantities(self):
        self._post(**{
            'only': str(self.never_bought.id),
            'qty_%s' % self.never_bought.id: '1',
        })
        self.assertFalse(self._cart().order_line)
        self._post(**{
            'only': str(self.bought.id),
            'qty_%s' % self.bought.id: '-3',
        })
        self.assertFalse(self._cart().order_line)
