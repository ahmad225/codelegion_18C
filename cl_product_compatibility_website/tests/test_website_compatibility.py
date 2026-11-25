# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.cl_product_compatibility_website.controllers.main import WebsiteSaleCompatibility
from odoo.addons.website.tools import MockRequest
from odoo.addons.website_sale.tests.common import WebsiteSaleCommon


@tagged('post_install', '-at_install')
class TestWebsiteCompatibility(WebsiteSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.controller = WebsiteSaleCompatibility()
        Product = cls.env['product.product']
        cls.cup12, cls.cup16, cls.lid12, cls.lid16 = Product.create([{
            'name': name,
            'type': 'consu',
            'list_price': 10.0,
            'sale_ok': True,
            'website_published': True,
        } for name in ('Cup 12oz', 'Cup 16oz', 'Lid 12oz', 'Lid 16oz')])
        cls.env['cl.product.compatibility.group'].create({
            'name': 'Cups & Lids',
            'product_ids': [Command.set((cls.cup12 | cls.cup16 | cls.lid12 | cls.lid16).ids)],
        })
        cls.cup12.cl_compatible_product_ids = [Command.link(cls.lid12.id)]
        cls.cup16.cl_compatible_product_ids = [Command.link(cls.lid16.id)]

    def _cart(self, *products):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'website_id': self.website.id,
            'order_line': [
                Command.create({'product_id': product.id, 'product_uom_qty': 1.0})
                for product in products
            ],
        })

    def test_cart_not_ready_and_payment_refused(self):
        cart = self._cart(self.cup12, self.lid16)
        self.assertFalse(cart._is_cart_ready())
        with self.assertRaisesRegex(ValidationError, 'do not fit together'):
            cart._check_cart_is_ready_to_be_paid()

        # Adding the lid that fits settles the cart.
        cart.write({'order_line': [Command.create({'product_id': self.lid12.id, 'product_uom_qty': 1.0})]})
        self.assertTrue(cart._is_cart_ready())

    def test_matching_cart_is_ready(self):
        cart = self._cart(self.cup12, self.lid12)
        self.assertTrue(cart._is_cart_ready())
        self.assertFalse(cart._cl_compatibility_messages(website=True))

    def test_checkout_sends_back_to_cart(self):
        cart = self._cart(self.cup12, self.lid16)
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            redirection = self.controller._check_cart(cart.sudo())
            self.assertTrue(redirection is not None)
            self.assertEqual(redirection.location, '/shop/cart')

        good_cart = self._cart(self.cup12, self.lid12)
        with MockRequest(self.env, website=self.website, sale_order_id=good_cart.id):
            self.assertIsNone(self.controller._check_cart(good_cart.sudo()))

    def test_only_published_options_are_suggested(self):
        self.lid12.website_published = False
        cart = self._cart(self.cup12, self.lid16)

        shop_message = cart._cl_compatibility_messages(website=True)[0]
        self.assertIn('Cup 16oz', shop_message)
        self.assertNotIn('Lid 12oz', shop_message)

        back_office_message = cart._cl_compatibility_messages()[0]
        self.assertIn('Lid 12oz', back_office_message)

        # The mismatch is still reported when nothing published can be suggested.
        self.cup16.website_published = False
        shop_message = cart._cl_compatibility_messages(website=True)[0]
        self.assertNotIn('Compatible options', shop_message)
        self.assertFalse(cart._is_cart_ready())

    def test_cart_page_notice_follows_the_cart(self):
        """The notice is part of the cart lines block, which the shop renders
        again after each quantity change."""
        website = self.website.with_user(self.public_user)
        with MockRequest(self.cup12.with_user(self.public_user).env, website=website):
            self.controller.cart_update_json(product_id=self.cup12.id, add_qty=1)
            values = self.controller.cart_update_json(product_id=self.lid16.id, add_qty=1)
            self.assertFalse(values['cart_ready'])
            self.assertIn('o_cl_compatibility_warning', values['website_sale.cart_lines'])
            self.assertIn('Lid 16oz', values['website_sale.cart_lines'])

            values = self.controller.cart_update_json(product_id=self.lid12.id, add_qty=1)
            self.assertTrue(values['cart_ready'])
            self.assertNotIn('o_cl_compatibility_warning', values['website_sale.cart_lines'])
