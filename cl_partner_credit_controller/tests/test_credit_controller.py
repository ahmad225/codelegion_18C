# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCreditController(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users']
        group = cls.env.ref('base.group_user')
        cls.alice = Users.create({'name': 'Alice Credit', 'login': 'cl_cc_alice', 'groups_id': [(6, 0, group.ids)]})
        cls.bob = Users.create({'name': 'Bob Credit', 'login': 'cl_cc_bob', 'groups_id': [(6, 0, group.ids)]})
        Partner = cls.env['res.partner']
        cls.company = Partner.create({'name': 'Cup Buyers Ltd', 'is_company': True,
                                      'cl_credit_controller_id': cls.alice.id})
        cls.contact = Partner.create({'name': 'Accounts Dept', 'parent_id': cls.company.id})
        cls.grandchild = Partner.create({'name': 'Clerk', 'parent_id': cls.contact.id, 'type': 'invoice'})

    def test_new_contacts_take_company_controller(self):
        self.assertEqual(self.contact.cl_credit_controller_id, self.alice)
        self.assertEqual(self.grandchild.cl_credit_controller_id, self.alice)

    def test_change_on_company_reaches_every_level(self):
        self.company.cl_credit_controller_id = self.bob
        self.assertEqual(self.contact.cl_credit_controller_id, self.bob)
        self.assertEqual(self.grandchild.cl_credit_controller_id, self.bob)

    def test_moved_contact_takes_new_company_controller(self):
        other = self.env['res.partner'].create({'name': 'Other Co', 'is_company': True,
                                                'cl_credit_controller_id': self.bob.id})
        self.contact.parent_id = other
        self.assertEqual(self.contact.cl_credit_controller_id, self.bob)

    def test_sync_action_repairs_contacts(self):
        # Simulate data written around the ORM sync.
        self.env.cr.execute("UPDATE res_partner SET cl_credit_controller_id = NULL WHERE id = %s",
                            [self.contact.id])
        self.contact.invalidate_recordset(['cl_credit_controller_id'])
        self.assertFalse(self.contact.cl_credit_controller_id)
        self.contact.action_cl_sync_credit_controller()
        self.assertEqual(self.contact.cl_credit_controller_id, self.alice)

    def test_orders_and_invoices_show_controller(self):
        product = self.env['product.product'].create({'name': 'Cup', 'list_price': 2})
        order = self.env['sale.order'].create({
            'partner_id': self.contact.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })
        self.assertEqual(order.cl_credit_controller_id, self.alice)
        if not self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1):
            self.skipTest('No sales journal (no chart of accounts) in this database.')
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.grandchild.id,
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1, 'price_unit': 2})],
        })
        self.assertEqual(invoice.cl_credit_controller_id, self.alice)
        self.company.cl_credit_controller_id = self.bob
        self.assertEqual(order.cl_credit_controller_id, self.bob)
        self.assertEqual(invoice.cl_credit_controller_id, self.bob)

    def test_portal_user_cannot_be_credit_controller(self):
        portal = self.env['res.users'].create({
            'name': 'Portal Person', 'login': 'cl_cc_portal',
            'groups_id': [(6, 0, self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(ValidationError):
            self.company.cl_credit_controller_id = portal

    def test_sync_action_reports_number_of_repaired_contacts(self):
        self.env.cr.execute("UPDATE res_partner SET cl_credit_controller_id = NULL WHERE id IN %s",
                            [(self.contact.id, self.grandchild.id)])
        (self.contact | self.grandchild).invalidate_recordset(['cl_credit_controller_id'])
        action = self.company.action_cl_sync_credit_controller()
        self.assertIn('2', action['params']['message'])
        self.assertEqual(self.grandchild.cl_credit_controller_id, self.alice)

    def test_orders_can_be_grouped_by_controller(self):
        product = self.env['product.product'].create({'name': 'Saucer', 'list_price': 1})
        order = self.env['sale.order'].create({
            'partner_id': self.grandchild.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })
        groups = self.env['sale.order'].read_group(
            [('id', '=', order.id)], ['cl_credit_controller_id'], ['cl_credit_controller_id'])
        self.assertEqual(groups[0]['cl_credit_controller_id'][0], self.alice.id)

    def test_stored_columns_exist(self):
        # created by hand in _auto_init on a first install; the ORM must still see them
        for model in ('sale.order', 'account.move'):
            field = self.env[model]._fields['cl_credit_controller_id']
            self.assertTrue(field.store)
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                [self.env[model]._table, 'cl_credit_controller_id'])
            self.assertTrue(self.env.cr.fetchone())
