# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.cl_contact_approval import _cl_post_init_hook


@tagged('post_install', '-at_install')
class TestContactApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.cl_contact_approval_enabled = True
        partner_manager = cls.env.ref('base.group_partner_manager')
        all_leads = cls.env.ref('sales_team.group_sale_salesman_all_leads')
        cls.approver = cls.env['res.users'].create({
            'name': 'Customer Approver', 'login': 'cl_customer_approver',
            'email': 'approver@example.com',
            'groups_id': [(6, 0, [cls.env.ref('cl_contact_approval.group_cl_contact_approver').id,
                                  all_leads.id, partner_manager.id])]})
        cls.salesman = cls.env['res.users'].create({
            'name': 'Plain Salesman', 'login': 'cl_approval_salesman',
            'email': 'salesman@example.com',
            'groups_id': [(6, 0, [all_leads.id, partner_manager.id])]})
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Customer', 'login': 'cl_approval_portal',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.product = cls.env['product.product'].create({'name': 'Cup', 'list_price': 10})
        cls.email_field = cls.env['ir.model.fields']._get('res.partner', 'email')

    def _new_customer(self, user=None, **vals):
        vals.setdefault('name', 'New Customer')
        return self.env['res.partner'].with_user(user or self.salesman).create(vals)

    def _quotation(self, partner):
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    def _approval_activities(self, record, xmlid='cl_contact_approval.mail_act_cl_customer_approval'):
        activity_type = self.env.ref(xmlid)
        return record.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)

    # ---- install and defaults ----

    def test_install_hook_approves_existing_partners(self):
        partner = self._new_customer()
        self.env.cr.execute("UPDATE res_partner SET cl_approval_state = 'draft'")
        self.env['res.partner'].invalidate_model(['cl_approval_state'])
        self.assertEqual(partner.cl_approval_state, 'draft')
        _cl_post_init_hook(self.env)
        self.assertEqual(partner.cl_approval_state, 'approved')
        self.assertFalse(self.env['res.partner'].with_context(active_test=False).search_count(
            [('cl_approval_state', '!=', 'approved')]))

    def test_new_partner_draft_when_enabled_approved_when_disabled(self):
        self.assertEqual(self._new_customer().cl_approval_state, 'draft')
        self.company.cl_contact_approval_enabled = False
        self.assertEqual(self._new_customer().cl_approval_state, 'approved')

    # ---- rights ----

    def test_non_approver_cannot_approve_by_write_or_create(self):
        partner = self._new_customer()
        with self.assertRaises(AccessError):
            partner.with_user(self.salesman).write({'cl_approval_state': 'approved'})
        with self.assertRaises(AccessError):
            self._new_customer(cl_approval_state='approved')
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.salesman).with_context(
                default_cl_approval_state='approved').create({'name': 'Sneaky Default'})
        with self.assertRaises(AccessError):
            partner.with_user(self.salesman).action_cl_approve()
        self.assertEqual(partner.cl_approval_state, 'draft')

    # ---- workflow ----

    def test_send_for_approval_lists_missing_fields(self):
        self.company.cl_contact_mandatory_field_ids = self.email_field
        partner = self._new_customer()
        with self.assertRaises(UserError) as error:
            partner.with_user(self.salesman).action_cl_send_for_approval()
        self.assertIn(self.email_field.field_description, str(error.exception))
        self.assertEqual(partner.cl_approval_state, 'draft')

    def test_approve_flow(self):
        self.company.cl_contact_mandatory_field_ids = self.email_field
        partner = self._new_customer(email='buyer@example.com')
        partner.with_user(self.salesman).action_cl_send_for_approval()
        self.assertEqual(partner.cl_approval_state, 'pending')
        self.assertEqual(partner.cl_approval_requested_by_id, self.salesman)
        self.assertIn(self.approver, self._approval_activities(partner).user_id)

        partner.with_user(self.approver).action_cl_approve()
        self.assertEqual(partner.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(partner))
        self.assertTrue(partner.message_ids.filtered(lambda m: self.salesman.partner_id in m.partner_ids))

    def test_reject_flow(self):
        partner = self._new_customer()
        partner.with_user(self.salesman).action_cl_send_for_approval()
        partner.with_user(self.approver).action_cl_reject()
        self.assertEqual(partner.cl_approval_state, 'draft')
        self.assertFalse(self._approval_activities(partner))
        self.assertTrue(partner.message_ids.filtered(lambda m: self.salesman.partner_id in m.partner_ids))

    def test_mass_approve_skips_missing_fields(self):
        self.company.cl_contact_mandatory_field_ids = self.email_field
        complete = self._new_customer(name='Complete', email='complete@example.com')
        incomplete = self._new_customer(name='Incomplete')
        action = (complete | incomplete).with_user(self.approver).action_cl_mass_approve()
        self.assertEqual(complete.cl_approval_state, 'approved')
        self.assertEqual(incomplete.cl_approval_state, 'draft')
        self.assertEqual(action['params']['type'], 'warning')
        self.assertIn('Incomplete', action['params']['message'])

    # ---- contacts follow their company ----

    def test_contacts_follow_commercial_partner(self):
        company = self._new_customer(name='Buyer Ltd', is_company=True)
        contact = self._new_customer(name='Jane Buyer', parent_id=company.id)
        self.assertEqual(contact.cl_approval_state, 'draft')
        company.with_user(self.approver).action_cl_approve()
        self.assertEqual(contact.cl_approval_state, 'approved')
        # a contact created later under the approved company is approved as well
        late_contact = self._new_customer(name='John Buyer', parent_id=company.id)
        self.assertEqual(late_contact.cl_approval_state, 'approved')
        # taken out of the company by a non-approver: needs its own approval
        late_contact.with_user(self.salesman).write({'parent_id': False})
        self.assertEqual(late_contact.cl_approval_state, 'draft')

    # ---- sales orders ----

    def test_order_blocked_for_unapproved_customer(self):
        partner = self._new_customer()
        order = self._quotation(partner)
        self.assertTrue(order.cl_customer_approval_warning)
        with self.assertRaises(UserError):
            order.with_user(self.salesman).action_confirm()
        partner.with_user(self.approver).action_cl_approve()
        self.assertFalse(order.cl_customer_approval_warning)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_order_for_contact_of_approved_company_confirms(self):
        company = self._new_customer(name='Approved Ltd', is_company=True)
        company.with_user(self.approver).action_cl_approve()
        contact = self._new_customer(name='Ordering Person', parent_id=company.id)
        order = self._quotation(contact)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_order_not_blocked_when_disabled(self):
        partner = self._new_customer()
        self.company.cl_contact_approval_enabled = False
        order = self._quotation(partner)
        order.with_user(self.salesman).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_online_confirmation_not_blocked_but_reviewed(self):
        partner = self._new_customer()
        order = self._quotation(partner)
        order.with_user(self.portal_user).sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        review = self._approval_activities(order, 'cl_contact_approval.mail_act_cl_unapproved_order')
        self.assertIn(self.approver, review.user_id)
        self.assertTrue(order.cl_customer_approval_warning)
        # approving the customer closes the review activities
        partner.with_user(self.approver).action_cl_approve()
        self.assertFalse(self._approval_activities(order, 'cl_contact_approval.mail_act_cl_unapproved_order'))

    # ---- revoking an approval ----

    def test_revoke_approval(self):
        company = self._new_customer(name='Revoked Ltd', is_company=True)
        contact = self._new_customer(name='Revoked Contact', parent_id=company.id)
        company.with_user(self.approver).action_cl_approve()
        self.assertEqual(contact.cl_approval_state, 'approved')
        with self.assertRaises(AccessError):
            company.with_user(self.salesman).action_cl_revoke_approval()
        company.with_user(self.approver).action_cl_revoke_approval()
        self.assertEqual(company.cl_approval_state, 'draft')
        self.assertEqual(contact.cl_approval_state, 'draft')
        with self.assertRaises(UserError):
            self._quotation(contact).with_user(self.salesman).action_confirm()
        # a pending customer is rejected, not revoked
        company.with_user(self.salesman).action_cl_send_for_approval()
        company.with_user(self.approver).action_cl_revoke_approval()
        self.assertEqual(company.cl_approval_state, 'pending')

    # ---- activities ----

    def test_one_done_message_whatever_the_number_of_approvers(self):
        partner = self._new_customer()
        partner.with_user(self.salesman).action_cl_send_for_approval()
        self.assertGreaterEqual(len(self._approval_activities(partner)), 2)
        partner.with_user(self.approver).action_cl_approve()
        self.assertFalse(self._approval_activities(partner))
        done = partner.message_ids.filtered(lambda m: m.subtype_id == self.env.ref('mail.mt_activities'))
        self.assertEqual(len(done), 1)

    def test_workflow_works_for_users_without_email(self):
        self.assertFalse(self.salesman.email)
        self.assertFalse(self.approver.email)
        partner = self._new_customer()
        partner.with_user(self.salesman).action_cl_send_for_approval()
        partner.with_user(self.approver).action_cl_reject()
        partner.with_user(self.salesman).action_cl_send_for_approval()
        partner.with_user(self.approver).action_cl_approve()
        self.assertEqual(partner.cl_approval_state, 'approved')

    # ---- list actions ----

    def test_mass_send_for_approval(self):
        first, second = self._new_customer(name='First'), self._new_customer(name='Second')
        approved = self._new_customer(name='Already Approved')
        approved.with_user(self.approver).action_cl_approve()
        action = (first | second | approved).with_user(self.salesman).action_cl_mass_send_for_approval()
        self.assertEqual((first | second).mapped('cl_approval_state'), ['pending', 'pending'])
        self.assertEqual(approved.cl_approval_state, 'approved')
        self.assertEqual(action['params']['type'], 'success')
        action = approved.with_user(self.salesman).action_cl_mass_send_for_approval()
        self.assertEqual(action['params']['type'], 'warning')
