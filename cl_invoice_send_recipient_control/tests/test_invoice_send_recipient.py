# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestInvoiceSendRecipient(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.partner_a
        cls.customer.email = 'customer@example.com'
        cls.follower = cls.env['res.partner'].create(
            {'name': 'Follower', 'email': 'follower@example.com'})
        cls.colleague = cls.env['res.partner'].create(
            {'name': 'Added In Wizard', 'email': 'colleague@example.com'})
        cls.invoice = cls.init_invoice(
            'out_invoice', partner=cls.customer, amounts=[100.0], post=True)
        cls.invoice.message_subscribe(partner_ids=cls.follower.ids)

    def _last_email(self, invoice):
        return self.env['mail.message'].sudo().search([
            ('model', '=', 'account.move'), ('res_id', '=', invoice.id),
            ('message_type', '=', 'comment'),
        ], order='id desc', limit=1)

    def _send_with_wizard(self, invoice, recipients=None):
        vals = {}
        if recipients is not None:
            vals['mail_partner_ids'] = [Command.set(recipients.ids)]
        wizard = self.env['account.move.send.wizard'].with_context(
            active_model='account.move', active_ids=invoice.ids).create(vals)
        wizard.action_send_and_print()
        email = self._last_email(invoice)
        self.assertTrue(email, "Sending should post the invoice email")
        return email.notified_partner_ids

    # ------------------------------------------------------------------
    # Send window
    # ------------------------------------------------------------------

    def test_standard_behaviour_when_setting_is_off(self):
        notified = self._send_with_wizard(self.invoice)
        self.assertIn(self.customer, notified)
        self.assertIn(self.follower, notified)

    def test_followers_are_skipped_when_setting_is_on(self):
        self.company.cl_invoice_email_skip_followers = True
        notified = self._send_with_wizard(self.invoice)
        self.assertEqual(notified, self.customer)

    def test_recipient_added_in_the_wizard_is_kept(self):
        self.company.cl_invoice_email_skip_followers = True
        notified = self._send_with_wizard(
            self.invoice, recipients=self.customer | self.colleague)
        self.assertEqual(notified, self.customer | self.colleague)

    def test_follower_picked_on_purpose_is_kept(self):
        self.company.cl_invoice_email_skip_followers = True
        notified = self._send_with_wizard(
            self.invoice, recipients=self.customer | self.follower)
        self.assertEqual(notified, self.customer | self.follower)

    # ------------------------------------------------------------------
    # Other ways an invoice email leaves
    # ------------------------------------------------------------------

    def test_sending_engine_without_wizard_is_covered(self):
        """Batch sending and automatic flows call the engine directly."""
        self.company.cl_invoice_email_skip_followers = True
        self.env['account.move.send']._generate_and_send_invoices(self.invoice)
        self.assertEqual(self._last_email(self.invoice).notified_partner_ids, self.customer)

    def test_chatter_messages_still_reach_followers(self):
        self.company.cl_invoice_email_skip_followers = True
        message = self.invoice.message_post(
            body='A question about this invoice',
            message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertIn(self.follower, message.notified_partner_ids)

    # ------------------------------------------------------------------
    # The filter itself
    # ------------------------------------------------------------------

    def _recipient_ids(self, invoice):
        message = self.env['mail.message']
        msg_vals = {
            'partner_ids': self.customer.ids,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
        }
        return {r['id'] for r in invoice._notify_get_recipients(message, msg_vals)}

    def test_filter_without_list_changes_nothing(self):
        ids = self._recipient_ids(self.invoice)
        self.assertIn(self.customer.id, ids)
        self.assertIn(self.follower.id, ids)

    def test_filter_keeps_only_listed_partners(self):
        invoice = self.invoice.with_context(
            cl_invoice_email_only_partner_ids=tuple(self.customer.ids))
        self.assertEqual(self._recipient_ids(invoice), set(self.customer.ids))

    def test_filter_with_empty_list_notifies_nobody(self):
        """All recipients removed in the Send window: followers must not get
        the invoice through the back door."""
        invoice = self.invoice.with_context(cl_invoice_email_only_partner_ids=())
        self.assertEqual(self._recipient_ids(invoice), set())
