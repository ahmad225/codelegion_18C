# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged('post_install', '-at_install')
class TestCreditNoteReturn(TestSaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the test user sells, ships, invoices and approves returns
        cls.env.user.groups_id |= (
            cls.env.ref('sales_team.group_sale_manager')
            | cls.env.ref('stock.group_stock_manager')
            | cls.env.ref('cl_credit_note_return_approval.group_cl_return_approver'))
        # ... while this one only prepares credit notes
        cls.billing_user = new_test_user(
            cls.env, login='cl_billing_only', groups='account.group_account_invoice',
            company_id=cls.env.company.id)
        Reason = cls.env['cl.credit.note.reason']
        cls.reason_return = Reason.create({'name': 'Damaged', 'requires_return': True})
        cls.reason_plain = Reason.create({'name': 'Price correction'})
        cls.customer = cls.env['res.partner'].create({'name': 'Customer'})
        cls.product = cls.env['product.product'].create({
            'name': 'Widget', 'type': 'consu', 'is_storable': True,
            'invoice_policy': 'order', 'list_price': 20.0,
            'taxes_id': [Command.clear()]})

    # ---- helpers -------------------------------------------------------
    def _process(self, picking, qty=None):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty if qty is None else qty
            move.picked = True
        return picking.button_validate()

    def _sell(self, qty=5.0):
        """Sell, deliver and invoice ``qty`` widgets; return the invoice."""
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id, 'product_uom_qty': qty})],
        })
        order.action_confirm()
        self._process(order.picking_ids)
        invoice = order._create_invoices()
        invoice.action_post()
        return invoice

    def _reversal_wizard(self, move, reason=None):
        return self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({
            'journal_id': move.journal_id.id,
            'cl_credit_reason_id': reason.id if reason else False,
        })

    def _credit(self, invoice, reason, qty=None):
        wizard = self._reversal_wizard(invoice, reason)
        wizard.refund_moves()
        credit = wizard.new_move_ids
        if qty is not None:
            credit.invoice_line_ids.filtered('product_id').quantity = qty
        return credit

    def _manual_invoice(self, extra_line=False):
        lines = [Command.create({
            'product_id': self.product.id, 'quantity': 1, 'price_unit': 20.0,
            'tax_ids': []})]
        if extra_line:
            lines.append(Command.create({
                'name': 'Handling', 'quantity': 1, 'price_unit': 5.0, 'tax_ids': []}))
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': lines,
        })
        invoice.action_post()
        return invoice

    # ---- reason --------------------------------------------------------
    def test_reason_goes_to_credit_note(self):
        credit = self._credit(self._sell(), self.reason_plain)
        self.assertEqual(credit.cl_credit_reason_id, self.reason_plain)
        self.assertFalse(credit.cl_return_status)
        credit.action_post()
        self.assertEqual(credit.state, 'posted')

    def test_vendor_bill_needs_no_reason(self):
        bill = self.init_invoice('in_invoice', amounts=[100.0], post=True)
        wizard = self._reversal_wizard(bill)
        wizard.refund_moves()
        self.assertEqual(wizard.new_move_ids.move_type, 'in_refund')
        self.assertFalse(wizard.new_move_ids.cl_credit_reason_id)

    # ---- limits --------------------------------------------------------
    def test_limits_against_the_invoice(self):
        invoice = self._sell(qty=5.0)
        credit = self._credit(invoice, self.reason_plain, qty=9.0)
        with self.assertRaises(ValidationError) as error:
            credit.action_post()
        self.assertIn('left to credit', str(error.exception))

        line = credit.invoice_line_ids.filtered('product_id')
        line.write({'quantity': 3.0, 'price_unit': 25.0})
        with self.assertRaises(ValidationError) as error:
            credit.action_post()
        self.assertIn('higher than the invoiced', str(error.exception))

        line.price_unit = 20.0
        credit.action_post()
        # a second credit note only has what the first one left
        second = self._credit(invoice, self.reason_plain, qty=3.0)
        with self.assertRaises(ValidationError):
            second.action_post()
        second.invoice_line_ids.filtered('product_id').quantity = 2.0
        second.action_post()
        self.assertEqual(second.state, 'posted')

    def test_line_without_product_is_allowed(self):
        credit = self._credit(self._manual_invoice(extra_line=True), self.reason_plain)
        credit.action_post()
        self.assertEqual(credit.state, 'posted')

    # ---- return flow ---------------------------------------------------
    def test_return_must_be_approved_and_received(self):
        credit = self._credit(self._sell(qty=5.0), self.reason_return)
        self.assertEqual(credit.cl_return_status, 'to_request')
        with self.assertRaises(ValidationError):
            credit.action_post()

        # asked by someone who has no access to Inventory
        credit.with_user(self.billing_user).action_cl_request_return()
        request = credit.cl_return_request_ids
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(request.user_id, self.billing_user)
        self.assertEqual(request.line_ids.product_id, self.product)
        self.assertEqual(request.line_ids.quantity, 5.0)
        self.assertFalse(request.picking_ids, "Nothing reaches the warehouse before approval.")
        self.assertEqual(request.activity_ids.user_id, self.env.user)
        self.assertEqual(credit.cl_return_status, 'to_approve')
        with self.assertRaises(ValidationError):
            credit.action_post()

        # the decision belongs to Return Approvers, also through the API
        with self.assertRaises(AccessError):
            request.with_user(self.billing_user).action_approve()
        with self.assertRaises(AccessError):
            request.with_user(self.billing_user).write({'state': 'approved'})

        request.action_approve()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.decided_by_id, self.env.user)
        self.assertFalse(request.activity_ids)
        picking = request.picking_ids
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.move_ids.product_uom_qty, 5.0)
        self.assertEqual(credit.cl_return_status, 'to_receive')
        with self.assertRaises(ValidationError):
            credit.action_post()

        self._process(picking)
        self.assertEqual(picking.state, 'done')
        self.assertTrue(request.is_received)
        self.assertEqual(credit.cl_return_status, 'received')
        credit.action_post()
        self.assertEqual(credit.state, 'posted')

        self.env.flush_all()
        rows = self.env['cl.return.analysis'].search([('request_id', '=', request.id)])
        self.assertEqual(sum(rows.mapped('quantity')), 5.0)
        self.assertAlmostEqual(sum(rows.mapped('amount')), 100.0)
        self.assertEqual(rows.reason_id, self.reason_return)

    def test_reject_leaves_nothing_in_the_warehouse(self):
        credit = self._credit(self._sell(), self.reason_return)
        credit.action_cl_request_return()
        request = credit.cl_return_request_ids
        request.action_reject()
        self.assertEqual(request.state, 'rejected')
        self.assertFalse(request.picking_ids)
        self.assertEqual(credit.cl_return_status, 'rejected')
        with self.assertRaises(ValidationError):
            credit.action_post()
        with self.assertRaises(UserError):
            request.action_approve()  # decided once
        # the credit note is not stuck: ask again, or change the reason
        credit.action_cl_request_return()
        self.assertEqual(len(credit.cl_return_request_ids), 2)
        self.assertEqual(credit.cl_return_status, 'to_approve')
        credit.cl_return_request_ids.filtered(lambda r: r.state == 'to_approve').action_cancel()
        credit.cl_credit_reason_id = self.reason_plain
        credit.action_post()
        self.assertEqual(credit.state, 'posted')

    def test_cancel_request_cancels_its_transfers(self):
        credit = self._credit(self._sell(qty=5.0), self.reason_return)
        credit.action_cl_request_return()
        request = credit.cl_return_request_ids
        with self.assertRaises(UserError):
            credit.action_cl_request_return()  # one request at a time
        request.action_approve()
        picking = request.picking_ids
        request.action_cancel()
        self.assertEqual(request.state, 'cancel')
        self.assertEqual(picking.state, 'cancel')
        self.assertEqual(credit.cl_return_status, 'to_request')
        # the cancelled transfer frees the quantity for a new request
        credit.action_cl_request_return()
        new_request = credit.cl_return_request_ids - request
        self.assertEqual(new_request.line_ids.quantity, 5.0)

    def test_partial_return_and_back_order(self):
        invoice = self._sell(qty=5.0)
        credit = self._credit(invoice, self.reason_return, qty=3.0)
        credit.action_cl_request_return()
        request = credit.cl_return_request_ids
        self.assertEqual(request.line_ids.quantity, 3.0)
        request.action_approve()
        picking = request.picking_ids

        # 2 of the 3 arrive; the rest stays on a back order
        action = self._process(picking, qty=2.0)
        Form(self.env[action['res_model']].with_context(action['context'])).save().process()
        backorder = picking.backorder_ids
        self.assertEqual(backorder.cl_return_request_id, request)
        self.assertFalse(request.is_received)
        with self.assertRaises(ValidationError):
            credit.action_post()
        self._process(backorder)
        self.assertTrue(request.is_received)
        credit.action_post()

        # 3 are back: a second credit note can only return the 2 that are left
        second = self._credit(invoice, self.reason_return)
        with self.assertRaises(ValidationError):
            second.action_cl_request_return()
        second.invoice_line_ids.filtered('product_id').quantity = 2.0
        second.action_cl_request_return()
        self.assertEqual(second.cl_return_request_ids.line_ids.quantity, 2.0)

    def test_cannot_receive_more_than_delivered(self):
        credit = self._credit(self._sell(qty=5.0), self.reason_return)
        credit.action_cl_request_return()
        request = credit.cl_return_request_ids
        request.action_approve()
        with self.assertRaises(UserError):
            self._process(request.picking_ids, qty=6.0)

    # ---- no way around -------------------------------------------------
    def test_reverse_and_create_invoice_cannot_skip_the_return(self):
        invoice = self._sell()
        wizard = self._reversal_wizard(invoice, self.reason_return)
        with self.assertRaises(ValidationError):
            wizard.modify_moves()

    def test_request_needs_delivered_goods(self):
        # an invoice that does not come from a delivered sales order
        credit = self._credit(self._manual_invoice(), self.reason_return)
        with self.assertRaises(UserError):
            credit.action_cl_request_return()

    def test_decision_cannot_be_forged(self):
        credit = self._credit(self._sell(), self.reason_return)
        other_credit = self._credit(self._sell(), self.reason_return)
        Request = self.env['cl.return.request'].with_user(self.billing_user)
        forged = Request.create({'credit_note_id': credit.id, 'state': 'approved'})
        self.assertEqual(forged.state, 'to_approve')
        self.assertFalse(forged.decided_by_id)
        with self.assertRaises(UserError):
            forged.write({'credit_note_id': other_credit.id})
        # a transfer cannot be passed off as an authorised return either
        delivery = credit.reversed_entry_id.invoice_line_ids.sale_line_ids.order_id.picking_ids
        with self.assertRaises(AccessError):
            delivery.write({'cl_return_request_id': forged.id})
