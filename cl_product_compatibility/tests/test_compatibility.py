# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCompatibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.product']
        cls.cup12 = Product.create({'name': 'Cup 12oz', 'type': 'consu'})
        cls.cup16 = Product.create({'name': 'Cup 16oz', 'type': 'consu'})
        cls.lid12 = Product.create({'name': 'Lid 12oz', 'type': 'consu'})
        cls.lid16 = Product.create({'name': 'Lid 16oz', 'type': 'consu'})
        cls.other = Product.create({'name': 'Napkin', 'type': 'consu'})
        cls.group = cls.env['cl.product.compatibility.group'].create({
            'name': 'Cups & Lids',
            'product_ids': [(6, 0, (cls.cup12 | cls.cup16 | cls.lid12 | cls.lid16).ids)],
        })
        cls.cup12.cl_compatible_product_ids = [(4, cls.lid12.id)]
        cls.cup16.cl_compatible_product_ids = [(4, cls.lid16.id)]
        cls.partner = cls.env['res.partner'].create({'name': 'Cafe'})
        # The tests themselves run as the superuser, for whom confirmation is
        # never blocked: the checks are exercised with real users.
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.salesperson = Users.create({
            'name': 'Compatibility Salesperson',
            'login': 'cl_compat_salesperson',
            'email': 'cl_compat_salesperson@example.com',
            'groups_id': [Command.set(cls.env.ref('sales_team.group_sale_salesman_all_leads').ids)],
        })
        cls.manager = Users.create({
            'name': 'Compatibility Manager',
            'login': 'cl_compat_manager',
            'email': 'cl_compat_manager@example.com',
            'groups_id': [Command.set(cls.env.ref('sales_team.group_sale_manager').ids)],
        })

    def _order(self, *products):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': 1}) for p in products],
        })

    def _notes(self, order, text):
        return order.message_ids.filtered(lambda message: text in (message.body or ''))

    def test_links_are_symmetric(self):
        self.assertIn(self.cup12, self.lid12.cl_compatible_product_ids)
        self.cup12.cl_compatible_product_ids = [(3, self.lid12.id)]
        self.assertNotIn(self.cup12, self.lid12.cl_compatible_product_ids)

    def test_mismatch_detected_and_blocks_confirm(self):
        order = self._order(self.cup12, self.lid16)
        self.assertEqual(len(order._cl_compatibility_mismatches()), 1)
        self.assertTrue(order.cl_compatibility_warning)
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_mismatch_reported_without_suggestion(self):
        # Nothing is compatible with anything: still a mismatch, with no options.
        (self.cup12 | self.cup16).cl_compatible_product_ids = [(5, 0, 0)]
        order = self._order(self.cup12, self.lid16)
        messages = order._cl_compatibility_messages()
        self.assertEqual(len(messages), 1)
        self.assertNotIn('Compatible options', messages[0])
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()

    def test_matched_sets_pass(self):
        order = self._order(self.cup12, self.lid12, self.cup16, self.lid16)
        self.assertFalse(order._cl_compatibility_mismatches())
        self.assertFalse(order.cl_compatibility_warning)
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_products_outside_groups_ignored(self):
        order = self._order(self.cup12, self.other)
        self.assertFalse(order._cl_compatibility_mismatches())

    def test_archived_group_ignored(self):
        self.group.active = False
        order = self._order(self.cup12, self.lid16)
        self.assertFalse(order._cl_compatibility_mismatches())

    def test_manager_override_confirms(self):
        order = self._order(self.cup12, self.lid16)
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_cl_override_compatibility()
        self.assertEqual(order.state, 'draft')

        order.with_user(self.manager).action_cl_override_compatibility()
        self.assertTrue(order.cl_compatibility_override)
        self.assertEqual(order.state, 'sale')
        self.assertEqual(len(self._notes(order, 'Compatibility warning overridden')), 1)

    def test_log_note_works_without_email(self):
        """The override note is a log note: it must not need a sender address."""
        self.manager.partner_id.email = False
        order = self._order(self.cup12, self.lid16)
        order.with_user(self.manager)._cl_log_compatibility_note('Override test', ['First mismatch'])
        self.assertEqual(len(self._notes(order, 'Override test')), 1)

    def test_line_change_resets_override(self):
        order = self._order(self.cup12, self.lid16)
        order.cl_compatibility_override = True
        order.write({'order_line': [(0, 0, {'product_id': self.other.id, 'product_uom_qty': 1})]})
        self.assertFalse(order.cl_compatibility_override)
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()

    def test_system_confirmation_is_not_blocked(self):
        """An order confirmed by the system or for the customer (online payment,
        signature) must not stay unconfirmed: it goes through with a log note."""
        order = self._order(self.cup12, self.lid16)
        self.assertTrue(order.env.su)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.cl_compatibility_override)
        self.assertEqual(len(self._notes(order, 'not compatible')), 1)

    def test_new_product_form_values_reach_the_variant(self):
        """Compatibility typed on a new product form is set on its variant."""
        template = self.env['product.template'].create({
            'name': 'Lid 12oz Dome',
            'type': 'consu',
            'cl_compatibility_group_ids': [(6, 0, self.group.ids)],
            'cl_compatible_product_ids': [(6, 0, self.cup12.ids)],
        })
        variant = template.product_variant_id
        self.assertEqual(variant.cl_compatibility_group_ids, self.group)
        self.assertEqual(variant.cl_compatible_product_ids, self.cup12)
        self.assertIn(variant, self.cup12.cl_compatible_product_ids)
        self.assertEqual(template.cl_compatible_product_ids, self.cup12)

    def test_options_from_another_company_not_listed(self):
        other_company = self.env['res.company'].create({'name': 'Compatibility Other Company'})
        foreign_lid = self.env['product.product'].create({
            'name': 'Foreign Cover',
            'type': 'consu',
            'company_id': other_company.id,
        })
        self.cup12.cl_compatible_product_ids = [(4, foreign_lid.id)]
        order = self._order(self.cup12, self.lid16)
        message = order._cl_compatibility_messages()[0]
        self.assertIn('Lid 12oz', message)
        self.assertNotIn('Foreign Cover', message)

    def test_variant_form_shows_compatibility(self):
        """Variants of a multi-variant product are edited in the short variant form."""
        view = self.env.ref('product.product_variant_easy_edit_view')
        arch = self.env['product.product'].get_view(view.id, 'form')['arch']
        self.assertIn('cl_compatibility_group_ids', arch)
        self.assertIn('cl_compatible_product_ids', arch)
