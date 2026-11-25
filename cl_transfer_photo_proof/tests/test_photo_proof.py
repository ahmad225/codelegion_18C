# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhotoProof(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.receipt_type = warehouse.in_type_id
        cls.receipt_type.write({'cl_require_photo_proof': True, 'create_backorder': 'ask'})
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.stock_location = warehouse.lot_stock_id
        cls.cup = cls.env['product.product'].create({'name': 'Paper Cup', 'is_storable': True})
        cls.lid = cls.env['product.product'].create({'name': 'Cup Lid', 'is_storable': True})
        cls.stock_user = cls.env['res.users'].create({
            'name': 'Proof Clerk', 'login': 'cl_proof_clerk',  # no email: validating must still work
            'groups_id': [Command.set([cls.env.ref('stock.group_stock_user').id])]})

    def _receipt(self, lines):
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.receipt_type.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'move_ids': [Command.create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': self.supplier_location.id,
                'location_dest_id': self.stock_location.id,
            }) for product, qty in lines],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _move(self, picking, product):
        return picking.move_ids.filtered(lambda m: m.product_id == product)

    def _add_proof(self, move, name='proof.jpg', mimetype='image/jpeg'):
        attachment = self.env['ir.attachment'].create({
            'name': name, 'raw': b'not really an image', 'mimetype': mimetype,
            'res_model': 'stock.move', 'res_id': move.id})
        move.cl_proof_attachment_ids = [Command.link(attachment.id)]
        return attachment

    def test_type_without_rule_validates_freely(self):
        self.receipt_type.cl_require_photo_proof = False
        picking = self._receipt([(self.cup, 5)])
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertFalse(picking.message_ids.filtered('attachment_ids'))

    def test_missing_proof_blocks_validation_and_names_product(self):
        picking = self._receipt([(self.cup, 5), (self.lid, 5)])
        self._add_proof(self._move(picking, self.lid))
        with self.assertRaises(UserError) as error:
            picking.button_validate()
        self.assertIn('Paper Cup', str(error.exception))
        self.assertNotIn('Cup Lid', str(error.exception))
        self.assertEqual(picking.state, 'assigned')

    def test_partial_validation_needs_proof_only_on_processed_lines(self):
        picking = self._receipt([(self.cup, 10), (self.lid, 5)])
        cup_move, lid_move = self._move(picking, self.cup), self._move(picking, self.lid)
        cup_move.quantity = 4
        cup_move.picked = True
        lid_move.quantity = 0
        # Only the cup line is processed; without its proof validation is refused.
        with self.assertRaises(UserError) as error:
            picking.with_context(skip_backorder=True).button_validate()
        self.assertIn('Paper Cup', str(error.exception))
        self.assertNotIn('Cup Lid', str(error.exception))

        proof = self._add_proof(cup_move)
        picking.with_context(skip_backorder=True).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(cup_move.state, 'done')
        self.assertEqual(cup_move.cl_proof_attachment_ids, proof)

        backorder = picking.backorder_ids
        self.assertTrue(backorder)
        self.assertEqual(set(backorder.move_ids.product_id.ids), {self.cup.id, self.lid.id})
        self.assertFalse(backorder.move_ids.cl_proof_attachment_ids)

    def test_validation_with_proofs_posts_one_note_linking_the_files(self):
        picking = self._receipt([(self.cup, 5), (self.lid, 3)])
        proofs = self._add_proof(self._move(picking, self.cup))
        proofs |= self._add_proof(self._move(picking, self.cup), name='label.pdf', mimetype='application/pdf')
        proofs |= self._add_proof(self._move(picking, self.lid))
        attachment_count = self.env['ir.attachment'].search_count([])

        picking.with_user(self.stock_user).button_validate()

        self.assertEqual(picking.state, 'done')
        notes = picking.message_ids.filtered('attachment_ids')
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.attachment_ids, proofs)
        self.assertIn('Paper Cup', notes.body)
        self.assertIn('Cup Lid', notes.body)
        self.assertIn('Proof Clerk', notes.body)
        # The note links the existing files: nothing was copied.
        self.assertEqual(self.env['ir.attachment'].search_count([]), attachment_count)
        self.assertTrue(all(a.res_model == 'stock.move' for a in proofs))

    def test_rule_applies_when_calling_action_done_directly(self):
        picking = self._receipt([(self.cup, 5)])
        picking.move_ids.picked = True
        with self.assertRaises(UserError):
            picking._action_done()
        self.assertEqual(picking.state, 'assigned')

        self._add_proof(picking.move_ids)
        picking._action_done()
        self.assertEqual(picking.state, 'done')

    def test_only_photos_and_pdfs_are_accepted(self):
        picking = self._receipt([(self.cup, 5)])
        with self.assertRaises(ValidationError):
            self._add_proof(picking.move_ids, name='notes.docx', mimetype=(
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))

    def test_proof_of_done_line_is_locked(self):
        picking = self._receipt([(self.cup, 5)])
        self._add_proof(picking.move_ids)
        picking.button_validate()
        with self.assertRaises(UserError):
            picking.with_user(self.stock_user).move_ids.cl_proof_attachment_ids = [Command.clear()]

    def test_file_uploaded_before_line_saved_is_linked_to_the_line(self):
        picking = self._receipt([(self.cup, 5)])
        move = picking.move_ids.with_user(self.stock_user)
        pending = self.env['ir.attachment'].with_user(self.stock_user).create({
            'name': 'shelf.png', 'raw': b'not really an image', 'mimetype': 'image/png',
            'res_model': 'stock.move', 'res_id': 0})
        move.cl_proof_attachment_ids = [Command.link(pending.id)]
        self.assertEqual((pending.res_model, pending.res_id), ('stock.move', move.id))

    def test_file_of_another_document_is_not_a_proof(self):
        """Linking an existing file by id (API, import) is not an upload."""
        picking = self._receipt([(self.cup, 5), (self.lid, 5)])
        cup_move, lid_move = self._move(picking, self.cup), self._move(picking, self.lid)
        partner = self.env['res.partner'].create({'name': 'Somebody'})
        foreign = self.env['ir.attachment'].create({
            'name': 'contract.pdf', 'raw': b'%PDF-1.4 contract', 'mimetype': 'application/pdf',
            'res_model': 'res.partner', 'res_id': partner.id})
        with self.assertRaises(UserError):
            cup_move.with_user(self.stock_user).cl_proof_attachment_ids = [Command.link(foreign.id)]
        # nor the proof of another line
        lid_proof = self._add_proof(lid_move)
        with self.assertRaises(ValidationError):
            cup_move.cl_proof_attachment_ids = [Command.link(lid_proof.id)]
        # nor a file somebody else uploaded and that is not on any record yet
        pending = self.env['ir.attachment'].create({
            'name': 'other.png', 'raw': b'not really an image', 'mimetype': 'image/png'})
        with self.assertRaises(UserError):
            cup_move.with_user(self.stock_user).cl_proof_attachment_ids = [Command.link(pending.id)]
        self.assertFalse(cup_move.cl_proof_attachment_ids)
        self.assertEqual((foreign.res_model, foreign.res_id), ('res.partner', partner.id))
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_link_or_empty_file_is_not_a_proof(self):
        picking = self._receipt([(self.cup, 5)])
        move = picking.move_ids
        link = self.env['ir.attachment'].create({
            'name': 'photo.jpg', 'type': 'url', 'url': 'https://example.com/photo.jpg',
            'mimetype': 'image/jpeg', 'res_model': 'stock.move', 'res_id': move.id})
        with self.assertRaises(ValidationError):
            move.cl_proof_attachment_ids = [Command.link(link.id)]
        empty = self.env['ir.attachment'].create({
            'name': 'empty.jpg', 'raw': b'', 'mimetype': 'image/jpeg',
            'res_model': 'stock.move', 'res_id': move.id})
        with self.assertRaises(ValidationError):
            move.cl_proof_attachment_ids = [Command.link(empty.id)]
        self.assertFalse(move.cl_proof_attachment_ids)

    def test_proof_files_of_done_line_cannot_be_deleted_or_replaced(self):
        """Any Inventory user has write access to the line, so to its files:
        without the lock a proof could be deleted from the chatter note."""
        picking = self._receipt([(self.cup, 5)])
        proof = self._add_proof(picking.move_ids)
        spare = self._add_proof(picking.move_ids, name='blurred.jpg')
        # before validation a wrong picture can still be removed
        spare.with_user(self.stock_user).unlink()
        self.assertFalse(spare.exists())
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

        user_proof = proof.with_user(self.stock_user)
        with self.assertRaises(UserError):
            user_proof.unlink()
        with self.assertRaises(UserError):
            user_proof.write({'raw': b'something else'})
        with self.assertRaises(UserError):
            user_proof.write({'res_model': 'res.partner', 'res_id': self.stock_user.partner_id.id})
        self.assertTrue(proof.exists())
        self.assertEqual(proof.raw, b'not really an image')
        self.assertEqual((proof.res_model, proof.res_id), ('stock.move', picking.move_ids.id))
        self.assertEqual(picking.message_ids.filtered('attachment_ids').attachment_ids, proof)

    def test_deleting_an_open_transfer_deletes_its_proof_files(self):
        picking = self._receipt([(self.cup, 5)])
        proof = self._add_proof(picking.move_ids)
        picking.action_cancel()
        picking.unlink()
        self.assertFalse(proof.exists())
