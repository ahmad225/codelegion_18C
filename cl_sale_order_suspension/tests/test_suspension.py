# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSuspension(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Neither user has an email address on purpose: suspending and
        # resuming only log notes, so they must not need one.
        cls.suspender = cls.env['res.users'].create({
            'name': 'Suspender', 'login': 'cl_suspender',
            'groups_id': [(6, 0, [cls.env.ref('cl_sale_order_suspension.group_cl_sale_suspension').id,
                                  cls.env.ref('sales_team.group_sale_salesman_all_leads').id])]})
        cls.salesman = cls.env['res.users'].create({
            'name': 'Plain Salesman', 'login': 'cl_plain_salesman',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman_all_leads').id])]})
        cls.customer = cls.env['res.partner'].create({'name': 'Hold Customer'})
        cls.product = cls.env['product.product'].create({'name': 'Cup', 'list_price': 10})

    def _quotation(self):
        return self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    def _suspend(self, order, user=None):
        wizard = self.env['cl.sale.suspend.wizard'].with_user(user or self.suspender).create({
            'order_ids': [(6, 0, order.ids)], 'reason': 'Waiting for customer artwork'})
        wizard.action_suspend()

    def _followups(self, order):
        activity_type = self.env.ref('cl_sale_order_suspension.mail_act_cl_suspension_followup')
        return order.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)

    def test_suspended_quotation_cannot_be_confirmed_or_sent(self):
        order = self._quotation()
        self._suspend(order)
        self.assertTrue(order.cl_is_suspended)
        self.assertEqual(order.cl_suspended_by_id, self.suspender)
        self.assertEqual(self._followups(order).user_id, self.suspender)
        with self.assertRaises(UserError):
            order.action_confirm()
        with self.assertRaises(UserError):
            order.action_quotation_send()

    def test_resume_closes_followup_and_allows_confirmation(self):
        order = self._quotation()
        self._suspend(order)
        order.with_user(self.suspender).action_cl_resume()
        self.assertFalse(order.cl_is_suspended)
        self.assertFalse(self._followups(order))
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_rights_checked_on_server(self):
        order = self._quotation()
        with self.assertRaises(UserError):
            order.with_user(self.salesman)._cl_suspend('No reason to allow this')
        self._suspend(order)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_cl_resume()

    def test_only_quotations_can_be_suspended(self):
        order = self._quotation()
        order.action_confirm()
        with self.assertRaises(UserError):
            order._cl_suspend('Too late')

    def test_warning_on_other_quotations_of_customer(self):
        held = self._quotation()
        self._suspend(held)
        other = self._quotation()
        self.assertEqual(other.cl_other_suspended_order_ids, held)
        self.assertFalse(held.cl_other_suspended_order_ids)
        # an order for a contact of the same company sees it too; another customer does not
        contact = self.env['res.partner'].create({'name': 'Hold Contact', 'parent_id': self.customer.id})
        for_contact = self.env['sale.order'].create({'partner_id': contact.id})
        self.assertEqual(for_contact.cl_other_suspended_order_ids, held)
        stranger = self.env['res.partner'].create({'name': 'Someone Else'})
        self.assertFalse(self.env['sale.order'].create({'partner_id': stranger.id}).cl_other_suspended_order_ids)
        held.with_user(self.suspender).action_cl_resume()
        # not stored: recomputed on every read from the client, by hand here
        other.invalidate_recordset(['cl_other_suspended_order_ids'])
        self.assertFalse(other.cl_other_suspended_order_ids)

    def test_cancel_ends_suspension(self):
        order = self._quotation()
        self._suspend(order)
        order._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(order.cl_is_suspended)
        self.assertFalse(self._followups(order))

    def test_user_without_email_can_suspend_and_resume(self):
        self.assertFalse(self.suspender.email)
        order = self._quotation()
        self._suspend(order)
        self.assertTrue(any('Waiting for customer artwork' in (m.body or '') for m in order.message_ids))
        order.with_user(self.suspender).action_cl_resume()
        self.assertFalse(order.cl_is_suspended)

    def test_suspension_fields_cannot_be_written_without_the_right(self):
        order = self._quotation()
        self._suspend(order)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({'cl_is_suspended': False})
        self.assertTrue(order.cl_is_suspended)
        # other fields stay editable for everybody
        order.with_user(self.salesman).write({'client_order_ref': 'PO-1'})

    def test_cancel_of_suspended_quotation_needs_the_right(self):
        order = self._quotation()
        self._suspend(order)
        with self.assertRaises(UserError):
            order.with_user(self.salesman)._action_cancel()
        self.assertTrue(order.cl_is_suspended)
        order.with_user(self.suspender)._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(order.cl_is_suspended)

    def test_suspended_quotation_cannot_be_signed_or_paid_on_portal(self):
        order = self._quotation()
        order.write({'require_signature': True, 'require_payment': True})
        self.assertTrue(order._has_to_be_signed())
        self.assertTrue(order._has_to_be_paid())
        self._suspend(order)
        self.assertFalse(order._has_to_be_signed())
        self.assertFalse(order._has_to_be_paid())
        order.with_user(self.suspender).action_cl_resume()
        self.assertTrue(order._has_to_be_signed())
        self.assertTrue(order._has_to_be_paid())
