# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestMarginControl(TransactionCase):
    """Run with:  odoo-bin -d <db> -i cl_margin_control --test-tags /cl_margin_control"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.approval_group = cls.env['res.groups'].create({'name': 'Margin Approvers (test)'})
        cls.company.write({
            'cl_margin_floor_enabled': True,
            'cl_margin_floor': 20.0,
            'cl_margin_line_alert': True,
            'cl_margin_line_alert_below': 20.0,
            'cl_margin_order_alert': True,
            'cl_margin_order_alert_below': 30.0,
            'cl_margin_approver_group_id': cls.approval_group.id,
            'cl_margin_skip_automatic': True,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Client'})
        # consumables: no stock involved in the confirmation
        cls.low = cls.env['product.product'].create({
            'name': 'Low Margin', 'type': 'consu',
            'list_price': 100.0, 'standard_price': 90.0})
        cls.high = cls.env['product.product'].create({
            'name': 'High Margin', 'type': 'consu',
            'list_price': 100.0, 'standard_price': 10.0})
        cls.salesperson = new_test_user(
            cls.env, login='cl_margin_salesperson',
            groups='sales_team.group_sale_salesman_all_leads')
        cls.approver = new_test_user(
            cls.env, login='cl_margin_approver',
            groups='sales_team.group_sale_salesman_all_leads')
        cls.approval_group.users = [Command.link(cls.approver.id)]
        cls.sales_admin = new_test_user(
            cls.env, login='cl_margin_sales_admin',
            groups='sales_team.group_sale_manager')
        cls.activity_type = cls.env.ref('cl_margin_control.mail_activity_type_margin_approval')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _order(self, product, price=100.0):
        """A quotation of the salesperson, with a fixed price and no tax so
        that the margin does not depend on the database's pricelists/taxes."""
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.salesperson.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': 1,
                'price_unit': price,
                'tax_id': [Command.clear()],
            })],
        })

    def _confirm(self, orders):
        """Confirm as the salesperson (a real user, not the superuser)."""
        return orders.with_user(self.salesperson).action_confirm()

    def _margin_activities(self, order):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
            ('activity_type_id', '=', self.activity_type.id),
        ])

    # ------------------------------------------------------------------
    # the floor
    # ------------------------------------------------------------------
    def test_low_margin_order_blocked_then_approved(self):
        order = self._order(self.low)
        self._confirm(order)
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertEqual(order.state, 'draft')
        # only the members of the approval group get the activity
        self.assertEqual(self._margin_activities(order).user_id, self.approver)

        order.with_user(self.approver).action_cl_margin_approve()
        self.assertEqual(order.cl_margin_approval_state, 'approved')
        self.assertEqual(order.state, 'sale')
        self.assertFalse(self._margin_activities(order))

    def test_high_margin_order_confirms(self):
        order = self._order(self.high)
        self._confirm(order)
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.cl_margin_approval_state, 'none')

    def test_batch_confirm_handles_each(self):
        low = self._order(self.low)
        high = self._order(self.high)
        self._confirm(low | high)
        self.assertEqual(high.state, 'sale')
        self.assertEqual(low.cl_margin_approval_state, 'to_approve')
        self.assertEqual(low.state, 'draft')

    def test_order_exactly_at_the_floor_is_not_blocked(self):
        """0.29 * 100 is 28.999999999999996 in floating point: an order at
        exactly 29% must not be treated as below a 29% floor."""
        self.company.cl_margin_floor = 29.0
        self.company.cl_margin_line_alert_below = 29.0
        self.company.cl_margin_order_alert_below = 29.0
        product = self.env['product.product'].create({
            'name': 'At The Floor', 'type': 'consu',
            'list_price': 100.0, 'standard_price': 71.0})
        order = self._order(product)
        self.assertFalse(order.order_line.cl_margin_low)
        self.assertFalse(order.cl_margin_order_low)
        self._confirm(order)
        self.assertEqual(order.state, 'sale')

    def test_floor_disabled_never_blocks(self):
        self.company.cl_margin_floor_enabled = False
        order = self._order(self.low)
        self._confirm(order)
        self.assertEqual(order.state, 'sale')

    # ------------------------------------------------------------------
    # who may approve
    # ------------------------------------------------------------------
    def test_only_an_approver_can_approve_or_reject(self):
        order = self._order(self.low)
        self._confirm(order)
        self.assertFalse(order.with_user(self.salesperson).cl_margin_can_approve)
        self.assertTrue(order.with_user(self.approver).cl_margin_can_approve)
        with self.assertRaises(AccessError):
            order.with_user(self.salesperson).action_cl_margin_approve()
        with self.assertRaises(AccessError):
            order.with_user(self.salesperson).action_cl_margin_reject()
        # nor by writing the field directly
        with self.assertRaises(AccessError):
            order.with_user(self.salesperson).write({'cl_margin_approval_state': 'approved'})
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertEqual(order.state, 'draft')

    def test_sales_administrators_approve_when_no_group_is_set(self):
        self.company.cl_margin_approver_group_id = False
        order = self._order(self.low)
        self._confirm(order)
        self.assertIn(self.sales_admin, self._margin_activities(order).user_id)
        self.assertNotIn(self.approver, self._margin_activities(order).user_id)
        with self.assertRaises(AccessError):
            order.with_user(self.approver).action_cl_margin_approve()
        order.with_user(self.sales_admin).action_cl_margin_approve()
        self.assertEqual(order.state, 'sale')

    def test_reject_sends_the_order_back(self):
        order = self._order(self.low)
        self._confirm(order)
        order.with_user(self.approver).action_cl_margin_reject()
        self.assertEqual(order.cl_margin_approval_state, 'none')
        self.assertEqual(order.state, 'draft')
        self.assertFalse(self._margin_activities(order))
        # confirming again asks again
        self._confirm(order)
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertTrue(self._margin_activities(order))

    # ------------------------------------------------------------------
    # activities and stale requests
    # ------------------------------------------------------------------
    def test_other_todo_activities_are_left_alone(self):
        order = self._order(self.low)
        todo = order.activity_schedule(
            'mail.mail_activity_data_todo', user_id=self.salesperson.id,
            summary="Call the customer")
        self._confirm(order)
        order.with_user(self.approver).action_cl_margin_approve()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(todo.exists())

    def test_request_is_withdrawn_when_the_margin_is_fixed(self):
        order = self._order(self.low)
        self._confirm(order)
        self.assertTrue(self._margin_activities(order))
        order.order_line.price_unit = 200.0  # cost 90: margin 55%
        self._confirm(order)
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.cl_margin_approval_state, 'none')
        self.assertFalse(self._margin_activities(order))

    def test_cancel_withdraws_the_request(self):
        order = self._order(self.low)
        self._confirm(order)
        order.with_user(self.salesperson)._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(order.cl_margin_approval_state, 'none')
        self.assertFalse(self._margin_activities(order))

    def test_approval_does_not_survive_cancel_and_reset(self):
        order = self._order(self.low)
        self._confirm(order)
        order.with_user(self.approver).action_cl_margin_approve()
        self.assertEqual(order.state, 'sale')
        order._action_cancel()
        order.action_draft()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.cl_margin_approval_state, 'none')
        self._confirm(order)
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertEqual(order.state, 'draft')

    def test_approval_only_covers_the_approved_margin(self):
        order = self._order(self.low)  # 10%
        order.write({'cl_margin_approval_state': 'approved', 'cl_margin_approved_percent': 10.0})
        self.assertFalse(order._cl_needs_margin_approval())
        order.order_line.price_unit = 95.0  # cost 90: margin 5.26%
        self.assertTrue(order._cl_needs_margin_approval())
        self._confirm(order)
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertEqual(order.state, 'draft')

    # ------------------------------------------------------------------
    # automatic confirmations (payment, signature, eCommerce)
    # ------------------------------------------------------------------
    def test_automatic_confirmation_is_let_through_and_logged(self):
        order = self._order(self.low)
        messages_before = len(order.message_ids)
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.cl_margin_approval_state, 'none')
        self.assertGreater(len(order.message_ids), messages_before)

    def test_automatic_confirmation_can_be_held_by_setting(self):
        self.company.cl_margin_skip_automatic = False
        order = self._order(self.low)
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.cl_margin_approval_state, 'to_approve')
        self.assertTrue(self._margin_activities(order))

    # ------------------------------------------------------------------
    # warnings
    # ------------------------------------------------------------------
    def test_line_warning_on_low_margin(self):
        order = self._order(self.low)
        self.assertAlmostEqual(order.order_line.cl_margin_pct, 10.0)
        self.assertTrue(order.order_line.cl_margin_low)
        order2 = self._order(self.high)
        self.assertFalse(order2.order_line.cl_margin_low)

    def test_order_warning_on_low_margin(self):
        self.assertTrue(self._order(self.low).cl_margin_order_low)
        self.assertFalse(self._order(self.high).cl_margin_order_low)
        self.company.cl_margin_order_alert = False
        self.assertFalse(self._order(self.low).cl_margin_order_low)
