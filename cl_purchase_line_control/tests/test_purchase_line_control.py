# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPurchaseLineControl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref('cl_purchase_line_control.group_cl_po_line_delete')
        cls.buyer = new_test_user(
            cls.env, login='cl_plain_buyer', groups='purchase.group_purchase_user')
        cls.vendor = cls.env['res.partner'].create({'name': 'Vendor'})
        Product = cls.env['product.product']
        cls.keep = Product.create({'name': 'Keep', 'type': 'consu', 'is_storable': True})
        cls.drop = Product.create({'name': 'Drop', 'type': 'consu', 'is_storable': True,
                                   'purchase_method': 'purchase'})

    def _po(self, confirm=True, extra_lines=()):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [
                (0, 0, {'product_id': self.keep.id, 'product_qty': 5, 'price_unit': 1}),
                (0, 0, {'product_id': self.drop.id, 'product_qty': 3, 'price_unit': 1}),
                *extra_lines,
            ],
        })
        if confirm:
            po.button_confirm()
        return po

    def _line(self, po, product):
        return po.order_line.filtered(lambda l: l.product_id == product)

    def _receive_all(self, po):
        receipt = po.picking_ids
        for move in receipt.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        receipt.button_validate()

    def test_delete_cancels_receipt_move(self):
        po = self._po()
        line = self._line(po, self.drop)
        move = line.move_ids
        kept_move = self._line(po, self.keep).move_ids
        line.unlink()
        self.assertEqual(move.state, 'cancel')
        self.assertNotEqual(kept_move.state, 'cancel')
        self.assertEqual(po.order_line.product_id, self.keep)

    def test_deletion_is_logged_on_order_and_receipt(self):
        po = self._po()
        receipt = po.picking_ids
        self._line(po, self.drop).unlink()
        (po | receipt).invalidate_recordset(['message_ids'])
        order_note = po.message_ids[0]
        self.assertIn('Drop', order_note.body)
        self.assertNotIn('Keep', order_note.body)
        self.assertEqual(order_note.author_id, self.env.user.partner_id)
        receipt_note = receipt.message_ids[0]
        self.assertIn('Drop', receipt_note.body)
        self.assertIn(po.name, receipt_note.body)

    def test_several_lines_one_note(self):
        po = self._po()
        po.order_line.unlink()
        self.assertFalse(po.order_line)
        po.invalidate_recordset(['message_ids'])
        self.assertIn('Keep', po.message_ids[0].body)
        self.assertIn('Drop', po.message_ids[0].body)
        self.assertEqual(po.picking_ids.state, 'cancel')

    def test_user_without_group_is_blocked(self):
        po = self._po()
        with self.assertRaises(UserError):
            self._line(po, self.drop).with_user(self.buyer).unlink()
        self.assertTrue(self._line(po, self.drop).exists())

    def test_user_without_group_keeps_standard_freedom(self):
        """Draft lines, sections and notes are deleted as in standard Odoo."""
        section = (0, 0, {'display_type': 'line_section', 'name': 'Section', 'product_qty': 0})
        draft = self._po(confirm=False).with_user(self.buyer)
        self._line(draft, self.drop).unlink()
        self.assertEqual(draft.order_line.product_id, self.keep)
        confirmed = self._po(extra_lines=[section]).with_user(self.buyer)
        confirmed.order_line.filtered('display_type').unlink()
        self.assertFalse(confirmed.order_line.filtered('display_type'))

    def test_billed_line_cannot_be_deleted(self):
        po = self._po()
        po.action_create_invoice()
        self.assertTrue(self._line(po, self.drop).invoice_lines)
        with self.assertRaises(UserError):
            self._line(po, self.drop).unlink()

    def test_received_line_cannot_be_deleted(self):
        po = self._po()
        self._receive_all(po)
        with self.assertRaises(UserError):
            self._line(po, self.drop).unlink()

    def test_locked_order_line_cannot_be_deleted(self):
        po = self._po()
        po.button_done()
        with self.assertRaises(UserError):
            self._line(po, self.drop).unlink()
        po.button_unlock()
        self._line(po, self.drop).unlink()
        self.assertEqual(po.order_line.product_id, self.keep)

    def test_error_lists_every_blocked_line(self):
        po = self._po()
        self._receive_all(po)
        with self.assertRaises(UserError) as error:
            po.order_line.unlink()
        self.assertIn('Keep', str(error.exception))
        self.assertIn('Drop', str(error.exception))

    def test_product_change_blocked_after_receipt(self):
        po = self._po()
        other = self.env['product.product'].create({
            'name': 'Other', 'type': 'consu', 'is_storable': True})
        line = self._line(po, self.drop)
        # Nothing received yet: the product may still be corrected.
        line.write({'product_id': line.product_id.id})
        self._receive_all(po)
        with self.assertRaises(UserError):
            line.write({'product_id': other.id})
