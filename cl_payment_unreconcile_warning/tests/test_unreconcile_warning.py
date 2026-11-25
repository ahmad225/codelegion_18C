# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUnreconcileWarning(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice = cls.init_invoice(
            'out_invoice', partner=cls.partner_a, invoice_date='2024-01-10',
            amounts=[100.0], post=True)

    def _partials(self, move):
        return move.line_ids.matched_debit_ids | move.line_ids.matched_credit_ids

    def _pay(self, move):
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({})._create_payments()
        self.assertTrue(payments.move_id, "The test payment needs a journal entry")
        return payments

    def test_message_when_partial_missing(self):
        res = self.invoice.cl_unreconcile_warning_message(999999999)
        self.assertIn('already been removed', res['message'])

    def test_message_names_payment_and_document(self):
        payment = self._pay(self.invoice)
        partial = self._partials(self.invoice)
        self.assertEqual(len(partial), 1)
        message = self.invoice.cl_unreconcile_warning_message(partial.id)['message']
        # The payment is what gets removed, the invoice is what it is removed
        # from - never the other way round.
        self.assertIn("Payment %s" % payment.name, message)
        self.assertIn("from %s %s?" % (self.invoice.type_name, self.invoice.name), message)
        self.assertTrue(message.startswith("Remove Payment %s" % payment.name))
        # The reconciled amount is shown in the currency of the invoice.
        self.assertIn(self.invoice.currency_id.format(partial.debit_amount_currency), message)

    def test_message_for_credit_note_match(self):
        credit_note = self.init_invoice(
            'out_refund', partner=self.partner_a, invoice_date='2024-01-12',
            amounts=[40.0], post=True)
        receivable = (self.invoice | credit_note).line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable')
        receivable.reconcile()
        partial = self._partials(self.invoice)
        self.assertEqual(len(partial), 1)

        # Seen from the invoice: the credit note is removed from the invoice.
        message = self.invoice.cl_unreconcile_warning_message(partial.id)['message']
        self.assertTrue(message.startswith(
            "Remove %s %s" % (credit_note.type_name, credit_note.name)))
        self.assertIn("from %s %s?" % (self.invoice.type_name, self.invoice.name), message)
        self.assertNotIn("Payment", message)

        # Seen from the credit note: the invoice is removed from the credit note.
        message = credit_note.cl_unreconcile_warning_message(partial.id)['message']
        self.assertTrue(message.startswith(
            "Remove %s %s" % (self.invoice.type_name, self.invoice.name)))
        self.assertIn("from %s %s?" % (credit_note.type_name, credit_note.name), message)

    def test_message_for_unrelated_partial_is_generic(self):
        other = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date='2024-01-11',
            amounts=[50.0], post=True)
        payment = self._pay(other)
        partial = self._partials(other)
        message = self.invoice.cl_unreconcile_warning_message(partial.id)['message']
        self.assertNotIn(payment.name, message)
        self.assertNotIn(other.name, message)

    def test_message_does_not_change_anything(self):
        self._pay(self.invoice)
        partial = self._partials(self.invoice)
        self.invoice.cl_unreconcile_warning_message(partial.id)
        self.assertTrue(partial.exists())
        self.assertIn(self.invoice.payment_state, ('paid', 'in_payment'))

    def test_message_needs_read_access_on_the_document(self):
        self._pay(self.invoice)
        partial = self._partials(self.invoice)
        user = new_test_user(self.env, login='cl_no_accounting', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.invoice.with_user(user).cl_unreconcile_warning_message(partial.id)
