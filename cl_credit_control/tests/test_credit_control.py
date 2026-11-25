# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.tests import new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCreditControl(AccountTestInvoicingCommon):
    """Run with:  odoo-bin -d <db> -i cl_credit_control --test-tags /cl_credit_control"""

    @classmethod
    def get_default_groups(cls):
        # the user running the tests creates quotations: make sure it may
        return super().get_default_groups() | cls.env.ref('sales_team.group_sale_manager')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.write({
            'cl_credit_block_overdue': True,
            'cl_credit_grace_days': 30,
            'cl_credit_min_overdue_amount': 0.0,
            'cl_credit_block_limit': False,
            'cl_credit_skip_automatic': True,
        })
        cls.customer = cls.env['res.partner'].create({
            'name': "Credit Test Customer",
            'is_company': True,
        })
        cls.salesperson = new_test_user(
            cls.env, login='cl_credit_salesperson',
            groups='sales_team.group_sale_salesman_all_leads,base.group_partner_manager')
        # the Credit Manager right alone must be enough to decide on any quotation
        cls.manager = new_test_user(
            cls.env, login='cl_credit_manager',
            groups='cl_credit_control.group_cl_credit_manager,base.group_partner_manager')
        cls.activity_type = cls.env.ref('cl_credit_control.mail_activity_type_credit_approval')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @classmethod
    def _overdue_invoice(cls, days_overdue, amount=1000.0, partner=None):
        """A posted, unpaid customer invoice whose due date is `days_overdue` days ago."""
        date = fields.Date.today() - timedelta(days=days_overdue)
        invoice = cls.init_invoice(
            'out_invoice', partner=partner or cls.customer,
            invoice_date=date, amounts=[amount], taxes=[])
        invoice.invoice_date_due = date
        invoice.action_post()
        return invoice

    def _quotation(self, price=100.0, partner=None):
        return self.env['sale.order'].create({
            'partner_id': (partner or self.customer).id,
            'user_id': self.salesperson.id,
            'order_line': [Command.create({
                'product_id': self.product_a.id,
                'product_uom_qty': 1,
                'price_unit': price,
                'tax_id': [Command.clear()],
            })],
        })

    def _credit_activities(self, order):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
            ('activity_type_id', '=', self.activity_type.id),
        ])

    # ------------------------------------------------------------------
    # when is a quotation blocked?
    # ------------------------------------------------------------------
    def test_clean_customer_is_not_blocked(self):
        order = self._quotation()
        self.assertFalse(order.cl_credit_warning)
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_overdue_beyond_allowance_blocks(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        self.assertTrue(order.cl_credit_warning)
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(self.customer.cl_credit_status, 'overdue')
        self.assertEqual(self.customer.cl_credit_overdue_amount, 1000.0)
        self.assertEqual(self.customer.cl_credit_overdue_days, 90)

    def test_overdue_within_allowance_passes(self):
        self._overdue_invoice(days_overdue=10)
        order = self._quotation()
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_small_overdue_amount_is_ignored(self):
        self.company.cl_credit_min_overdue_amount = 5000.0
        self._overdue_invoice(days_overdue=90, amount=1000.0)
        order = self._quotation()
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_customer_own_allowance(self):
        self._overdue_invoice(days_overdue=90)
        self.customer.with_user(self.manager).write(
            {'cl_credit_custom_grace': True, 'cl_credit_grace_days': 120})
        order = self._quotation()
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_exempt_customer_is_never_blocked(self):
        self._overdue_invoice(days_overdue=90)
        self.customer.with_user(self.manager).write(
            {'cl_credit_exempt': True, 'cl_credit_hold': True})
        self.assertEqual(self.customer.cl_credit_status, 'exempt')
        order = self._quotation()
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_credit_hold_blocks_without_overdue(self):
        self.customer.with_user(self.manager).cl_credit_hold = True
        order = self._quotation()
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()

    def test_contact_of_blocked_company_is_blocked(self):
        self._overdue_invoice(days_overdue=90)
        contact = self.env['res.partner'].create({
            'name': "Buyer", 'parent_id': self.customer.id, 'type': 'contact'})
        order = self._quotation(partner=contact)
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()

    def test_credit_limit_blocks(self):
        self.company.write({
            'cl_credit_block_overdue': False,
            'cl_credit_block_limit': True,
            'account_use_credit_limit': True,
        })
        self.customer.credit_limit = 50.0
        order = self._quotation(price=100.0)
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()
        small = self._quotation(price=20.0)
        small.with_user(self.salesperson).action_confirm()
        self.assertEqual(small.state, 'sale')

    # ------------------------------------------------------------------
    # approval workflow
    # ------------------------------------------------------------------
    def test_request_then_approve_confirms(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request("Customer pays on Friday")
        self.assertEqual(order.cl_credit_state, 'to_approve')
        self.assertEqual(order.cl_credit_requested_by_id, self.salesperson)
        self.assertIn(self.manager, self._credit_activities(order).user_id)

        # the salesperson still cannot confirm while it is waiting
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()

        order.with_user(self.manager).action_cl_credit_approve()
        self.assertEqual(order.cl_credit_state, 'approved')
        self.assertEqual(order.cl_credit_decided_by_id, self.manager)
        self.assertEqual(order.state, 'sale')
        self.assertFalse(self._credit_activities(order))

    def test_only_a_credit_manager_can_approve(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        with self.assertRaises(AccessError):
            order.with_user(self.salesperson).action_cl_credit_approve()
        self.assertEqual(order.state, 'draft')

    def test_reject_keeps_quotation_and_allows_new_request(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        order.with_user(self.manager)._cl_credit_reject("Too far behind")
        self.assertEqual(order.cl_credit_state, 'rejected')
        self.assertEqual(order.cl_credit_reject_reason, "Too far behind")
        self.assertEqual(order.state, 'draft')
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()
        order.with_user(self.salesperson)._cl_credit_request("Paid half today")
        self.assertEqual(order.cl_credit_state, 'to_approve')

    def test_request_refused_when_nothing_is_blocking(self):
        order = self._quotation()
        with self.assertRaises(UserError):
            order.with_user(self.salesperson)._cl_credit_request()

    def test_approval_only_covers_the_approved_amount(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation(price=100.0)
        order.write({'cl_credit_state': 'approved', 'cl_credit_approved_amount': order.amount_total})
        self.assertTrue(order._cl_credit_is_approved())
        order.order_line.price_unit = 500.0
        self.assertFalse(order._cl_credit_is_approved())
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()

    def test_changing_the_customer_resets_the_approval(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        other = self.env['res.partner'].create({'name': "Other Customer", 'is_company': True})
        order.partner_id = other
        self.assertFalse(order.cl_credit_state)

    def test_credit_manager_alone_can_decide_on_any_quotation(self):
        """The Credit Manager right is enough to open and approve a quotation
        that belongs to another salesperson."""
        self.assertTrue(self.manager.has_group('sales_team.group_sale_salesman_all_leads'))
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        order.with_user(self.manager).check_access('write')
        order.with_user(self.manager).action_cl_credit_approve()
        self.assertEqual(order.state, 'sale')

    def test_review_button_opens_the_dialog(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        action = order.with_user(self.salesperson).action_cl_credit_review()
        self.assertEqual(action['res_model'], 'cl.credit.approval.request')
        wizard = self.env['cl.credit.approval.request'].with_user(self.salesperson).with_context(
            **action['context']).create({'note': "Pays on Friday"})
        self.assertEqual(wizard.order_id, order)
        self.assertTrue(wizard.reason_html)
        self.assertTrue(wizard.overdue_html)
        wizard.action_request()
        self.assertEqual(order.cl_credit_state, 'to_approve')
        self.assertEqual(order.cl_credit_request_note, "Pays on Friday")

    def test_request_is_withdrawn_when_the_block_disappears(self):
        """The customer is cleared while the request waits: the salesperson
        confirms, and no Credit Manager is left with an activity to do."""
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        self.assertTrue(self._credit_activities(order))
        self.customer.with_user(self.manager).cl_credit_exempt = True
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.cl_credit_state)
        self.assertFalse(self._credit_activities(order))

    def test_cancel_withdraws_the_request(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        order.with_user(self.salesperson)._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(order.cl_credit_state)
        self.assertFalse(self._credit_activities(order))

    def test_approval_does_not_survive_cancel_and_reset(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        order.with_user(self.manager).action_cl_credit_approve()
        self.assertEqual(order.state, 'sale')
        order._action_cancel()
        order.action_draft()
        self.assertEqual(order.state, 'draft')
        self.assertFalse(order.cl_credit_state)
        with self.assertRaises(RedirectWarning):
            order.with_user(self.salesperson).action_confirm()

    def test_only_a_credit_manager_can_change_customer_settings(self):
        for vals in ({'cl_credit_exempt': True}, {'cl_credit_hold': False},
                     {'cl_credit_custom_grace': True, 'cl_credit_grace_days': 999}):
            with self.assertRaises(AccessError):
                self.customer.with_user(self.salesperson).write(vals)
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.salesperson).create(
                {'name': "Self-exempted", 'cl_credit_exempt': True})
        # other fields are not affected, and a Credit Manager may change the settings
        self.customer.with_user(self.salesperson).write({'comment': "Called about the invoices"})
        self.customer.with_user(self.manager).write({'cl_credit_hold': True})
        self.assertTrue(self.customer.cl_credit_hold)

    # ------------------------------------------------------------------
    # automatic confirmations
    # ------------------------------------------------------------------
    def test_automatic_confirmation_is_let_through_and_logged(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        messages_before = len(order.message_ids)
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertGreater(len(order.message_ids), messages_before)

    def test_automatic_confirmation_withdraws_a_waiting_request(self):
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        order.with_user(self.salesperson)._cl_credit_request()
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.cl_credit_state)
        self.assertFalse(self._credit_activities(order))

    def test_automatic_confirmation_can_be_blocked_by_setting(self):
        self.company.cl_credit_skip_automatic = False
        self._overdue_invoice(days_overdue=90)
        order = self._quotation()
        with self.assertRaises(RedirectWarning):
            order.sudo().action_confirm()
        self.assertEqual(order.state, 'draft')

    # ------------------------------------------------------------------
    # customer search
    # ------------------------------------------------------------------
    def test_search_customers_with_overdue(self):
        self._overdue_invoice(days_overdue=90)
        clean = self.env['res.partner'].create({'name': "Clean Customer", 'is_company': True})
        found = self.env['res.partner'].search([('cl_credit_has_overdue', '=', True)])
        self.assertIn(self.customer, found)
        self.assertNotIn(clean, found)
