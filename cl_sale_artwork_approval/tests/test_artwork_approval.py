# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

LOGO = base64.b64encode(b'customer logo file')
PROOF = base64.b64encode(b'designer proof file')
PROOF_2 = base64.b64encode(b'designer proof file, second try')


@tagged('post_install', '-at_install')
class TestArtworkApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.cl_artwork_block_sale = True
        cls.env.company.cl_artwork_attach_production = True
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.salesman = Users.create({
            'name': 'Artwork Salesman', 'login': 'cl_art_salesman',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])]})
        designer_group = cls.env.ref('cl_sale_artwork_approval.group_cl_artwork_designer')
        cls.designer = Users.create({
            'name': 'Artwork Designer', 'login': 'cl_art_designer',
            'groups_id': [(6, 0, [designer_group.id])]})
        cls.designer_2 = Users.create({
            'name': 'Other Designer', 'login': 'cl_art_designer_2',
            'groups_id': [(6, 0, [designer_group.id])]})
        cls.employee = Users.create({
            'name': 'Plain Employee', 'login': 'cl_art_employee',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])]})

        Partner = cls.env['res.partner']
        cls.customer = Partner.create({'name': 'Brand Co', 'is_company': True, 'email': 'brand@example.com'})
        cls.contact = Partner.create({'name': 'Anna Brand', 'parent_id': cls.customer.id,
                                      'email': 'anna@example.com'})
        cls.other_customer = Partner.create({'name': 'Other Co', 'is_company': True,
                                             'email': 'other@example.com'})
        portal_group = cls.env.ref('base.group_portal')
        cls.portal_other = Users.create({
            'name': 'Other Portal', 'login': 'cl_art_portal_other',
            'partner_id': cls.other_customer.id,
            'groups_id': [(6, 0, [portal_group.id])]})

        cls.mug = cls.env['product.product'].create({
            'name': 'Printed Mug', 'type': 'consu', 'list_price': 10, 'cl_artwork_required': True})
        cls.lid = cls.env['product.product'].create({'name': 'Plain Lid', 'type': 'consu', 'list_price': 2})
        cls.design_type = cls.env.ref('cl_sale_artwork_approval.mail_act_cl_artwork_design')
        cls.review_type = cls.env.ref('cl_sale_artwork_approval.mail_act_cl_artwork_review')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _order(self, partner, products):
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'user_id': self.salesman.id,
            'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': 10}) for p in products],
        })

    def _artwork(self, order, product, designer=None):
        return self.env['cl.artwork'].with_user(self.salesman).create({
            'name': 'Front logo',
            'partner_id': order.partner_id.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'cl_sale_order_id': order.id,
            'cl_designer_id': (designer or self.designer).id,
            'user_id': self.salesman.id,
            'cl_source_file': LOGO,
            'cl_source_filename': 'logo.png',
        })

    def _activities(self, artwork, activity_type):
        return artwork.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)

    def _approved_artwork(self, order, product):
        artwork = self._artwork(order, product)
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        artwork.with_user(self.salesman).action_cl_approve()
        return artwork

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_send_to_designer(self):
        order = self._order(self.contact, self.mug)
        artwork = self._artwork(order, self.mug)
        # Artwork belongs to the customer company, and the order line uses it.
        self.assertEqual(artwork.partner_id, self.customer)
        self.assertEqual(artwork.cl_version, 1)
        self.assertEqual(order.order_line.cl_artwork_id, artwork)

        # Neither the salesperson nor the designer has an email address: the
        # chatter notes of the workflow must not need one.
        self.assertFalse(self.salesman.partner_id.email)
        self.assertFalse(self.designer.partner_id.email)
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        self.assertEqual(artwork.state, 'design')
        sent_note = artwork.message_ids.filtered(lambda m: 'Sent to' in (m.body or ''))
        self.assertEqual(sent_note.author_id, self.salesman.partner_id)
        self.assertEqual(self._activities(artwork, self.design_type).user_id, self.designer)
        self.assertIn(self.designer.partner_id, artwork.message_partner_ids)

        # The designer uploads the proof, but cannot change anything else or approve.
        with self.assertRaises(UserError):
            artwork.with_user(self.designer).write({'name': 'Renamed'})
        with self.assertRaises(AccessError):
            artwork.with_user(self.designer_2).write({'cl_proof_file': PROOF})
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        self.assertEqual(artwork.state, 'review')
        self.assertEqual(artwork.cl_proof_count, 1)
        self.assertFalse(self._activities(artwork, self.design_type))
        self.assertEqual(self._activities(artwork, self.review_type).user_id, self.salesman)
        with self.assertRaises(UserError):
            artwork.with_user(self.designer).action_cl_approve()
        # The status cannot be forced by a write.
        with self.assertRaises(UserError):
            artwork.with_user(self.salesman).write({'state': 'approved'})

    def test_rework(self):
        order = self._order(self.customer, self.mug)
        artwork = self._artwork(order, self.mug)
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        # No new proof while the current one is under review.
        with self.assertRaises(UserError):
            artwork.with_user(self.designer).write({'cl_proof_file': PROOF_2})

        wizard = self.env['cl.artwork.rework.wizard'].with_user(self.salesman).create({
            'cl_artwork_id': artwork.id, 'cl_comment': 'Make the logo bigger.'})
        wizard.action_cl_confirm()
        self.assertEqual(artwork.state, 'rework')
        self.assertEqual(artwork.cl_rework_note, 'Make the logo bigger.')
        self.assertFalse(self._activities(artwork, self.review_type))
        design = self._activities(artwork, self.design_type)
        self.assertEqual(design.user_id, self.designer)

        artwork.with_user(self.designer).write({'cl_proof_file': PROOF_2})
        artwork.with_user(self.designer).action_cl_submit_proof()
        self.assertEqual(artwork.state, 'review')
        self.assertEqual(artwork.cl_proof_count, 2)
        proofs = self.env['ir.attachment'].search([
            ('res_model', '=', 'cl.artwork'), ('res_id', '=', artwork.id), ('res_field', '=', False)])
        self.assertEqual(len(proofs), 2, "Every submitted proof is kept in the chatter.")

    def test_approve(self):
        order = self._order(self.customer, self.mug)
        artwork = self._artwork(order, self.mug)
        # No approval without a proof waiting for review.
        with self.assertRaises(UserError):
            artwork.with_user(self.salesman).action_cl_approve()
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        artwork.with_user(self.salesman).action_cl_approve()
        self.assertEqual(artwork.state, 'approved')
        self.assertEqual(artwork.cl_approved_by_id, self.salesman)
        self.assertTrue(artwork.cl_approved_date)
        self.assertFalse(artwork.activity_ids)

        # Approved artwork is frozen and cannot be deleted.
        with self.assertRaises(UserError):
            artwork.with_user(self.salesman).write({'cl_source_file': PROOF_2})
        with self.assertRaises(UserError):
            artwork.unlink()
        # Deleting the quotation keeps the artwork.
        order.unlink()
        self.assertTrue(artwork.exists())
        self.assertFalse(artwork.cl_sale_order_id)

    def test_reuse_on_next_order(self):
        order = self._order(self.contact, self.mug)
        waiting = self._order(self.customer, self.mug)
        self.assertFalse(waiting.order_line.cl_artwork_id)
        artwork = self._approved_artwork(order, self.mug)
        # An open quotation of the same customer picks it up on approval.
        self.assertEqual(waiting.order_line.cl_artwork_id, artwork)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

        # Next order (by the company itself): used automatically, and confirmable.
        next_order = self._order(self.customer, self.mug)
        self.assertEqual(next_order.order_line.cl_artwork_id, artwork)
        self.assertIn(artwork, next_order.cl_reused_artwork_ids)
        self.assertEqual(next_order.cl_artwork_status, 'approved')

        # A new version requested on the next order replaces it there only.
        action = artwork.with_user(self.salesman).with_context(
            cl_sale_order_id=next_order.id).action_cl_new_version()
        version_2 = self.env['cl.artwork'].browse(action['res_id'])
        self.assertEqual(version_2.cl_version, 2)
        self.assertEqual(version_2.state, 'draft')
        self.assertEqual(version_2.cl_source_file, LOGO)
        self.assertEqual(next_order.order_line.cl_artwork_id, version_2)
        self.assertEqual(order.order_line.cl_artwork_id, artwork)
        version_2.with_user(self.salesman).write({'cl_proof_file': PROOF_2, 'cl_proof_filename': 'v2.pdf'})
        version_2.with_user(self.salesman).action_cl_submit_proof()
        version_2.with_user(self.salesman).action_cl_approve()
        self.assertEqual(self._order(self.contact, self.mug).order_line.cl_artwork_id, version_2)
        self.assertEqual(artwork.state, 'approved', "Older versions stay valid for their orders.")

    def test_request_artwork_from_order_line(self):
        """The Artwork tab of the order works line by line."""
        order = self._order(self.contact, self.mug | self.lid)
        mug_line = order.order_line.filtered(lambda l: l.product_id == self.mug)
        # Only the line whose product requires artwork is listed.
        self.assertEqual(order.cl_artwork_line_ids, mug_line)

        action = mug_line.with_user(self.salesman).action_cl_request_artwork()
        artwork = self.env['cl.artwork'].browse(action['res_id'])
        self.assertEqual(artwork.state, 'draft')
        self.assertEqual(artwork.partner_id, self.customer)
        self.assertEqual(artwork.product_tmpl_id, self.mug.product_tmpl_id)
        self.assertEqual(artwork.cl_sale_order_id, order)
        self.assertEqual(artwork.user_id, self.salesman)
        self.assertEqual(mug_line.cl_artwork_id, artwork)
        self.assertIn(artwork, order.cl_artwork_ids)

        # Asking again carries on with the same artwork instead of piling up drafts.
        again = mug_line.with_user(self.salesman).action_cl_request_artwork()
        self.assertEqual(again['res_id'], artwork.id)
        self.assertEqual(mug_line.with_user(self.salesman).action_cl_open_artwork()['res_id'], artwork.id)

        # A new version can only start from approved artwork.
        with self.assertRaises(UserError):
            mug_line.with_user(self.salesman).action_cl_new_artwork_version()
        artwork.with_user(self.salesman).write({
            'cl_designer_id': self.designer.id, 'cl_brief': 'Logo on the front, one colour.'})
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        artwork.with_user(self.salesman).action_cl_approve()
        action = mug_line.with_user(self.salesman).action_cl_new_artwork_version()
        version_2 = self.env['cl.artwork'].browse(action['res_id'])
        self.assertEqual(version_2.cl_version, 2)
        self.assertEqual(version_2.cl_sale_order_id, order)
        self.assertEqual(mug_line.cl_artwork_id, version_2)

        # A cancelled request frees the line for a new one.
        version_2.with_user(self.salesman).action_cl_cancel()
        self.assertEqual(mug_line.cl_artwork_id, artwork, "The line falls back to the approved artwork.")

    def test_production_gets_approved_artwork(self):
        order = self._order(self.customer, self.mug)
        artwork = self._artwork(order, self.mug)
        production = self.env['mrp.production'].create({
            'product_id': self.mug.id, 'product_qty': 10, 'sale_line_id': order.order_line.id})
        self.assertEqual(production.cl_artwork_id, artwork)
        self.assertFalse(production.cl_artwork_attachment_id, "Nothing is attached before approval.")

        artwork.with_user(self.salesman).action_cl_send_to_designer()
        artwork.with_user(self.designer).write({'cl_proof_file': PROOF, 'cl_proof_filename': 'proof.pdf'})
        artwork.with_user(self.designer).action_cl_submit_proof()
        artwork.with_user(self.salesman).action_cl_approve()
        attachment = production.cl_artwork_attachment_id
        self.assertTrue(attachment)
        self.assertEqual((attachment.res_model, attachment.res_id), ('mrp.production', production.id))
        self.assertEqual(attachment.datas, PROOF, "Production gets the designer's proof, not the raw logo.")
        self.assertEqual(production.cl_artwork_proof_file, PROOF)

    def test_production_from_order_gets_artwork(self):
        self.env.ref('stock.route_warehouse0_mto').active = True
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        cup = self.env['product.product'].create({
            'name': 'Printed Cup', 'type': 'consu', 'is_storable': True, 'cl_artwork_required': True,
            'route_ids': [(6, 0, [warehouse.manufacture_pull_id.route_id.id,
                                  warehouse.mto_pull_id.route_id.id])],
        })
        component = self.env['product.product'].create({'name': 'Blank Cup', 'type': 'consu'})
        self.env['mrp.bom'].create({
            'product_tmpl_id': cup.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
        })
        order = self._order(self.contact, cup)
        artwork = self._approved_artwork(order, cup)
        order.action_confirm()
        production = self.env['mrp.production'].search([('product_id', '=', cup.id)])
        self.assertEqual(len(production), 1)
        self.assertEqual(production.cl_artwork_id, artwork)
        self.assertEqual(production.cl_artwork_attachment_id.datas, PROOF)

    def test_confirmation_blocked_without_approved_artwork(self):
        order = self._order(self.customer, self.mug | self.lid)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        artwork = self._artwork(order, self.mug)
        artwork.with_user(self.salesman).action_cl_send_to_designer()
        self.assertEqual(order.cl_artwork_status, 'missing')
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'draft')

        # Artwork on a product that does not require it never blocks.
        plain = self._order(self.customer, self.lid)
        self._artwork(plain, self.lid)
        plain.with_user(self.salesman).action_confirm()
        self.assertEqual(plain.state, 'sale')

        # A customer confirming online is not blocked; the salesperson gets a note.
        online = self._order(self.customer, self.mug)
        online.sudo().action_confirm()
        self.assertEqual(online.state, 'sale')

        # The block can be switched off.
        self.env.company.cl_artwork_block_sale = False
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_other_customers_cannot_see_artwork(self):
        order = self._order(self.customer, self.mug)
        artwork = self._approved_artwork(order, self.mug)

        # Another customer's order never reuses it.
        other_order = self._order(self.other_customer, self.mug)
        self.assertFalse(other_order.order_line.cl_artwork_id)
        with self.assertRaises(UserError):
            other_order.with_user(self.salesman).action_confirm()

        # Portal users and employees without sales, design or manufacturing rights cannot read it
        # or its files.
        files = self.env['ir.attachment'].search([
            ('res_model', '=', 'cl.artwork'), ('res_id', '=', artwork.id),
            ('res_field', 'in', ('cl_source_file', 'cl_proof_file'))])
        self.assertEqual(len(files), 2)
        for user in (self.portal_other, self.employee):
            with self.assertRaises(AccessError):
                artwork.with_user(user).read(['name'])
            for attachment in files:
                with self.assertRaises(AccessError):
                    attachment.with_user(user).check('read')
        # Files in the chatter are private to the artwork as well.
        proof_copy = self.env['ir.attachment'].search([
            ('res_model', '=', 'cl.artwork'), ('res_id', '=', artwork.id), ('res_field', '=', False)])
        with self.assertRaises(AccessError):
            proof_copy.with_user(self.portal_other).check('read')
