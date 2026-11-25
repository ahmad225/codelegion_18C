# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInactivityApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.cl_quotation_inactivity_days = 14
        # Neither user has an email address on purpose: the workflow must not need one.
        cls.salesman = cls.env['res.users'].create({
            'name': 'Salesman', 'login': 'cl_stale_salesman',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman_all_leads').id])]})
        cls.approver = cls.env['res.users'].create({
            'name': 'Approver', 'login': 'cl_stale_approver',
            'groups_id': [(6, 0, [cls.env.ref(
                'cl_quotation_inactivity_approval.group_cl_quotation_approver').id])]})
        cls.customer = cls.env['res.partner'].create({'name': 'Slow Customer', 'email': 'slow@example.com'})
        cls.product = cls.env['product.product'].create({'name': 'Lid', 'list_price': 3})

    def _quotation(self, stale=False):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'user_id': self.salesman.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 2})],
        })
        if stale:
            order.write({'cl_last_activity_date': fields.Datetime.now() - timedelta(days=20)})
        return order

    def _approval_activities(self, order):
        activity_type = self.env.ref('cl_quotation_inactivity_approval.mail_act_cl_quotation_approval')
        return order.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)

    def test_fresh_quotation_confirms(self):
        order = self._quotation()
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_stale_quotation_goes_to_approval(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.cl_approval_state, 'pending')
        self.assertIn(self.approver, self._approval_activities(order).user_id)

    def test_multi_confirm_handles_each_order(self):
        stale, fresh = self._quotation(stale=True), self._quotation()
        (stale | fresh).with_user(self.salesman).action_confirm()
        self.assertEqual(fresh.state, 'sale')
        self.assertEqual(stale.state, 'draft')
        self.assertEqual(stale.cl_approval_state, 'pending')

    def test_pending_quotation_locked_for_non_approvers(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        with self.assertRaises(UserError):
            order.order_line.with_user(self.salesman).write({'product_uom_qty': 5})
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_cl_approve()
        order.order_line.with_user(self.approver).write({'product_uom_qty': 5})
        self.assertEqual(order.order_line.product_uom_qty, 5)

    def test_approve_then_confirm(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.approver).action_cl_approve()
        self.assertEqual(order.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(order))
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_reject_keeps_quotation_and_requires_new_activity(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.approver).action_cl_reject()
        self.assertEqual(order.cl_approval_state, 'none')
        # Still stale: confirming asks for approval again.
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.cl_approval_state, 'pending')

    def test_internal_note_is_not_activity_but_customer_message_is(self):
        order = self._quotation(stale=True)
        before = order.cl_last_activity_date
        order.message_post(body='Internal remark', subtype_xmlid='mail.mt_note')
        self.assertEqual(order.cl_last_activity_date, before)
        order.message_post(body='Customer asks for a new price', message_type='comment',
                           subtype_xmlid='mail.mt_comment', author_id=self.customer.id)
        self.assertGreater(order.cl_last_activity_date, before)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_editing_lines_resets_clock(self):
        order = self._quotation(stale=True)
        order.order_line.write({'product_uom_qty': 3})
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_approver_confirms_directly(self):
        order = self._quotation(stale=True)
        order.with_user(self.approver).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_switched_off(self):
        self.env.company.cl_quotation_inactivity_days = 0
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    # ---- closing the request when the quotation is confirmed anyway ----

    def test_pending_quotation_confirmed_by_approver_closes_request(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        self.assertTrue(self._approval_activities(order))
        order.with_user(self.approver).action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(order))
        # a confirmed order is not "waiting for approval": lines stay editable
        order.order_line.with_user(self.salesman).write({'name': 'Lid, white'})

    def test_pending_quotation_accepted_online_closes_request(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        # customer signature / payment confirm the order in sudo
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.cl_approval_state, 'none')
        self.assertFalse(self._approval_activities(order))

    # ---- approval is not a permanent pass ----

    def test_approved_quotation_left_idle_again_needs_new_approval(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.approver).action_cl_approve()
        self.assertFalse(order._cl_needs_inactivity_approval())
        order.write({'cl_last_activity_date': fields.Datetime.now() - timedelta(days=20)})
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(order.cl_approval_state, 'pending')

    # ---- rights ----

    def test_approval_fields_cannot_be_set_by_non_approvers(self):
        order = self._quotation(stale=True)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({'cl_last_activity_date': fields.Datetime.now()})
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({'cl_approval_state': 'approved'})
        future = fields.Datetime.now() + timedelta(days=3650)
        created = self.env['sale.order'].with_user(self.salesman).create({
            'partner_id': self.customer.id,
            'cl_last_activity_date': future,
            'cl_approval_state': 'approved',
        })
        self.assertLess(created.cl_last_activity_date, future)
        self.assertEqual(created.cl_approval_state, 'none')

    def test_no_approver_gives_clear_error(self):
        self.env.ref('cl_quotation_inactivity_approval.group_cl_quotation_approver').write(
            {'users': [(5, 0, 0)]})
        order = self._quotation(stale=True)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.cl_approval_state, 'none')

    def test_unconfirmable_quotation_is_not_sent_for_approval(self):
        order = self._quotation(stale=True)
        with patch.object(type(order), '_confirmation_error_message', lambda self: 'Blocked'), \
                self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.cl_approval_state, 'none')
        self.assertFalse(self._approval_activities(order))

    # ---- notes and notifications ----

    def test_users_without_email_can_request_and_approve(self):
        self.assertFalse(self.salesman.email)
        self.assertFalse(self.approver.email)
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.approver).action_cl_approve()
        self.assertEqual(order.cl_approval_state, 'approved')

    def test_salesperson_is_notified_of_the_decision(self):
        self.approver.email = 'approver@example.com'
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        order.with_user(self.approver).action_cl_reject()
        self.assertIn(self.salesman.partner_id, order.message_ids.partner_ids)

    def test_one_activity_done_message_whatever_the_number_of_approvers(self):
        order = self._quotation(stale=True)
        order.with_user(self.salesman).action_confirm()
        self.assertGreaterEqual(len(self._approval_activities(order)), 2)
        done_subtype = self.env.ref('mail.mt_activities')
        order.with_user(self.approver).action_cl_approve()
        self.assertEqual(len(order.message_ids.filtered(lambda m: m.subtype_id == done_subtype)), 1)
