# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.addons.sale.tests.common import TestSaleCommon
from odoo.tests import new_test_user, tagged


@tagged('post_install', '-at_install')
class TestDeliveryInvoiceAutoSend(TestSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.cl_send_invoices_when_delivered = True
        cls.partner_a.email = 'customer@example.com'
        # Goods that are not tracked in stock: they still get a delivery
        # order, and need no stock to be delivered.
        cls.product_order = cls.env['product.product'].create({
            'name': 'Invoiced on order', 'type': 'consu',
            'invoice_policy': 'order', 'list_price': 50.0})
        cls.product_delivery = cls.env['product.product'].create({
            'name': 'Invoiced on delivery', 'type': 'consu',
            'invoice_policy': 'delivery', 'list_price': 50.0})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _confirmed_order(self, product, partner=None):
        order = self.env['sale.order'].create({
            'partner_id': (partner or self.partner_a).id,
            'order_line': [Command.create({
                'product_id': product.id, 'product_uom_qty': 2})],
        })
        order.action_confirm()
        self.assertEqual(
            len(order.picking_ids), 1, "The order should have one delivery")
        self.assertEqual(order.picking_ids.picking_type_id.code, 'outgoing')
        return order

    def _posted_invoice(self, order):
        invoice = order._create_invoices()
        invoice.action_post()
        return invoice

    def _deliver(self, order, user=None):
        picking = order.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        if user:
            picking = picking.with_user(user)
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        return picking

    def _refresh(self, invoice):
        invoice.invalidate_recordset()
        return invoice

    def _notes(self, invoice, text):
        return self.env['mail.message'].sudo().search([
            ('model', '=', 'account.move'), ('res_id', '=', invoice.id),
            ('body', 'ilike', text)])

    def assertQueued(self, invoice):
        self._refresh(invoice)
        self.assertTrue(invoice.sending_data, "The invoice should wait in the sending queue")
        self.assertTrue(invoice.is_being_sent)
        self.assertTrue(invoice.cl_queued_on_delivery)
        self.assertTrue(invoice.is_move_sent)

    def assertNotQueued(self, invoice):
        self._refresh(invoice)
        self.assertFalse(invoice.sending_data)
        self.assertFalse(invoice.cl_queued_on_delivery)

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def test_invoice_posted_before_delivery_is_queued_on_validation(self):
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        self.assertNotQueued(invoice)  # nothing delivered yet

        picking = self._deliver(order)

        self.assertQueued(invoice)
        self.assertEqual(invoice.sending_data, {
            'author_user_id': self.env.user.id,
            'author_partner_id': self.env.user.partner_id.id,
        })
        self.assertTrue(self._notes(invoice, picking.name))

    def test_invoice_posted_after_delivery_is_queued_on_post(self):
        order = self._confirmed_order(self.product_delivery)
        picking = self._deliver(order)
        invoice = order._create_invoices()
        self.assertNotQueued(invoice)  # still a draft

        invoice.action_post()

        self.assertQueued(invoice)
        self.assertTrue(self._notes(invoice, picking.name))

    def test_draft_invoice_is_not_queued(self):
        order = self._confirmed_order(self.product_order)
        draft = order._create_invoices()
        self._deliver(order)
        self.assertNotQueued(draft)

    def test_setting_off_does_nothing(self):
        self.company.cl_send_invoices_when_delivered = False
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        self._deliver(order)
        self.assertNotQueued(invoice)
        self.assertFalse(self._refresh(invoice).is_move_sent)

        # ...and neither on a later posting.
        other = self._confirmed_order(self.product_delivery)
        self._deliver(other)
        self.assertNotQueued(self._posted_invoice(other))

    def test_invoice_without_sale_order_is_not_queued(self):
        order = self._confirmed_order(self.product_order)
        self._deliver(order)
        invoice = self.init_invoice(
            'out_invoice', partner=self.partner_a, amounts=[100.0], post=True)
        self.assertNotQueued(invoice)

    # ------------------------------------------------------------------
    # Never twice
    # ------------------------------------------------------------------

    def test_invoice_is_queued_only_once(self):
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        picking = self._deliver(order)
        self.assertQueued(invoice)

        # The background job has done its work...
        invoice.sudo().sending_data = False
        # ...and something triggers the delivery hook again.
        picking._cl_auto_send_delivery_invoices()
        self.assertFalse(self._refresh(invoice).sending_data)
        self.assertFalse(invoice._cl_queue_delivery_auto_send())

    def test_invoice_already_sent_by_hand_is_left_alone(self):
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        invoice.sudo().is_move_sent = True
        self._deliver(order)
        self.assertNotQueued(invoice)

    def test_invoice_already_in_the_queue_is_left_alone(self):
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        waiting = {'author_user_id': 1, 'author_partner_id': 1}
        invoice.sudo().sending_data = waiting
        self._deliver(order)
        self._refresh(invoice)
        self.assertEqual(invoice.sending_data, waiting)
        self.assertFalse(invoice.cl_queued_on_delivery)

    # ------------------------------------------------------------------
    # Robustness
    # ------------------------------------------------------------------

    def test_customer_without_email_gets_a_note_instead(self):
        no_mail = self.env['res.partner'].create({'name': 'No Mail Ltd'})
        order = self._confirmed_order(self.product_order, partner=no_mail)
        invoice = self._posted_invoice(order)

        self._deliver(order)

        self.assertNotQueued(invoice)
        self.assertFalse(self._refresh(invoice).is_move_sent)
        self.assertEqual(len(self._notes(invoice, 'no email address')), 1)

    def test_warehouse_user_without_accounting_rights_can_validate(self):
        """The person validating the delivery usually cannot read invoices:
        the validation must go through and the invoice must still be sent."""
        warehouse_user = new_test_user(
            self.env, login='cl_warehouse_only',
            groups='base.group_user,stock.group_stock_user',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        self.assertFalse(warehouse_user.has_group('account.group_account_invoice'))
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)

        self._deliver(order, user=warehouse_user)

        self.assertQueued(invoice)
        self.assertEqual(invoice.sending_data['author_user_id'], warehouse_user.id)

    def test_background_job_sends_the_queued_invoice(self):
        order = self._confirmed_order(self.product_order)
        invoice = self._posted_invoice(order)
        self._deliver(order)
        self.assertQueued(invoice)
        self.assertFalse(invoice.invoice_pdf_report_id)

        self.env.ref('account.ir_cron_account_move_send').sudo().method_direct_trigger()

        self._refresh(invoice)
        self.assertFalse(invoice.sending_data)
        self.assertTrue(invoice.invoice_pdf_report_id, "The invoice PDF should be generated")
        emails = self.env['mail.message'].sudo().search([
            ('model', '=', 'account.move'), ('res_id', '=', invoice.id),
            ('message_type', '=', 'comment'),
            ('partner_ids', 'in', self.partner_a.ids)])
        self.assertEqual(len(emails), 1, "The customer should get exactly one email")
        self.assertTrue(emails.attachment_ids, "The email should carry the invoice PDF")
