# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import Form, tagged

SYNC = {'cl_payment_term_sync': True}


@tagged('post_install', '-at_install')
class TestPaymentTermDefault(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        # Fresh terms, so that none of them can be a database-wide default.
        cls.term_a, cls.term_b, cls.term_c = [
            cls.pay_terms_b.copy({'name': 'CL terms %s' % letter}) for letter in 'ABC']
        cls.company_2 = cls.setup_other_company()['company']
        cls.parent = cls.Partner.create({
            'name': 'Parent Co', 'is_company': True,
            'property_payment_term_id': cls.term_a.id,
            'property_supplier_payment_term_id': cls.term_b.id,
        })

    def _child(self, **vals):
        return self.Partner.create({'name': 'Child', 'parent_id': self.parent.id, **vals})

    def assertTerms(self, partner, customer, vendor, company=None):
        if company:
            partner = partner.with_company(company)
        partner.invalidate_recordset()
        self.assertEqual(partner.property_payment_term_id, customer)
        self.assertEqual(partner.property_supplier_payment_term_id, vendor)

    # ------------------------------------------------------------------
    # New contacts
    # ------------------------------------------------------------------

    def test_new_contact_gets_company_terms(self):
        child = self._child()
        self.assertTerms(child, self.term_a, self.term_b)
        self.assertFalse(child.cl_keep_own_payment_term)

    def test_new_contact_from_the_form_gets_company_terms(self):
        """The web client sends every field of the form, the empty payment
        terms included: they must not win over the company's terms."""
        child = self._child(
            property_payment_term_id=False, property_supplier_payment_term_id=False)
        self.assertTerms(child, self.term_a, self.term_b)
        self.assertFalse(child.cl_keep_own_payment_term)

    def test_new_contact_with_other_terms_keeps_them(self):
        child = self._child(property_payment_term_id=self.term_c.id)
        self.assertTrue(child.cl_keep_own_payment_term)
        self.assertEqual(child.property_payment_term_id, self.term_c)

    def test_new_contact_gets_company_terms_in_every_company(self):
        self.parent.with_company(self.company_2).property_payment_term_id = self.term_c
        child = self._child()
        self.assertTerms(child, self.term_a, self.term_b)
        self.assertEqual(
            child.with_company(self.company_2).property_payment_term_id, self.term_c)

    def test_child_company_is_its_own_entity(self):
        subsidiary = self._child(is_company=True)
        self.assertNotEqual(subsidiary.property_payment_term_id, self.term_a)
        self.parent.property_payment_term_id = self.term_c
        self.assertNotEqual(subsidiary.property_payment_term_id, self.term_c)

    # ------------------------------------------------------------------
    # Company changes
    # ------------------------------------------------------------------

    def test_company_change_goes_down_to_contacts(self):
        child = self._child()
        grandchild = self.Partner.create({'name': 'Grandchild', 'parent_id': child.id})
        self.parent.write({
            'property_payment_term_id': self.term_c.id,
            'property_supplier_payment_term_id': self.term_a.id,
        })
        self.assertTerms(child, self.term_c, self.term_a)
        self.assertTerms(grandchild, self.term_c, self.term_a)

    def test_company_terms_removed_goes_down_too(self):
        child = self._child()
        self.parent.property_supplier_payment_term_id = False
        child.invalidate_recordset()
        self.assertEqual(
            child.property_supplier_payment_term_id,
            self.parent.property_supplier_payment_term_id)

    def test_company_change_stays_in_its_company(self):
        child = self._child()
        self.parent.with_company(self.company_2).property_payment_term_id = self.term_c
        self.assertEqual(
            child.with_company(self.company_2).property_payment_term_id, self.term_c)
        self.assertTerms(child, self.term_a, self.term_b)

    def test_contact_keeping_own_terms_is_not_touched(self):
        child = self._child(
            cl_keep_own_payment_term=True, property_payment_term_id=self.term_b.id)
        self.parent.property_payment_term_id = self.term_c
        child.invalidate_recordset()
        self.assertEqual(child.property_payment_term_id, self.term_b)

    def test_archived_contact_follows_too(self):
        child = self._child()
        child.active = False
        self.parent.property_payment_term_id = self.term_c
        child.invalidate_recordset()
        self.assertEqual(child.property_payment_term_id, self.term_c)

    # ------------------------------------------------------------------
    # Contact changes
    # ------------------------------------------------------------------

    def test_terms_set_by_hand_on_a_contact_survive(self):
        child = self._child()
        child.property_payment_term_id = self.term_c
        self.assertTrue(child.cl_keep_own_payment_term)
        self.parent.property_payment_term_id = self.term_b
        child.invalidate_recordset()
        self.assertEqual(child.property_payment_term_id, self.term_c)

    def test_writing_the_company_terms_on_a_contact_does_not_detach_it(self):
        child = self._child()
        child.property_payment_term_id = self.term_a
        self.assertFalse(child.cl_keep_own_payment_term)

    def test_unticking_keep_own_brings_the_contact_back(self):
        child = self._child(
            cl_keep_own_payment_term=True, property_payment_term_id=self.term_c.id)
        child.cl_keep_own_payment_term = False
        self.assertTerms(child, self.term_a, self.term_b)

    def test_contact_moved_to_another_company_takes_its_terms(self):
        other = self.Partner.create({
            'name': 'Other Co', 'is_company': True,
            'property_payment_term_id': self.term_c.id})
        child = self._child()
        grandchild = self.Partner.create({'name': 'Grandchild', 'parent_id': child.id})
        child.parent_id = other
        child.invalidate_recordset()
        grandchild.invalidate_recordset()
        self.assertEqual(child.property_payment_term_id, self.term_c)
        self.assertEqual(grandchild.property_payment_term_id, self.term_c)
        self.assertFalse(child.cl_keep_own_payment_term)

    # ------------------------------------------------------------------
    # Form
    # ------------------------------------------------------------------

    def test_form_shows_company_terms_and_ticks_keep_own(self):
        with Form(self.Partner) as form:
            form.name = 'Typed In The Form'
            form.parent_id = self.parent
            self.assertEqual(form.property_payment_term_id, self.term_a)
            self.assertEqual(form.property_supplier_payment_term_id, self.term_b)
            self.assertFalse(form.cl_keep_own_payment_term)
            form.property_payment_term_id = self.term_c
            self.assertTrue(form.cl_keep_own_payment_term)
        contact = form.record
        self.assertTrue(contact.cl_keep_own_payment_term)
        self.assertEqual(contact.property_payment_term_id, self.term_c)

    # ------------------------------------------------------------------
    # Manual action
    # ------------------------------------------------------------------

    def test_action_repairs_contacts_in_every_company(self):
        child = self._child()
        kept = self._child(
            cl_keep_own_payment_term=True, property_payment_term_id=self.term_c.id)
        # Contacts that drifted before the app was installed.
        child.with_context(**SYNC).write({'property_payment_term_id': self.term_c.id})
        self.parent.with_company(self.company_2).with_context(**SYNC).write(
            {'property_payment_term_id': self.term_c.id})

        action = self.parent.action_cl_sync_payment_terms()

        self.assertEqual(action['tag'], 'display_notification')
        self.assertTerms(child, self.term_a, self.term_b)
        self.assertEqual(
            child.with_company(self.company_2).property_payment_term_id, self.term_c)
        kept.invalidate_recordset()
        self.assertEqual(kept.property_payment_term_id, self.term_c)
        self.assertIn('1 contact(s) updated', action['params']['message'])
        self.assertIn('1 contact(s) keep their own terms', action['params']['message'])

    def test_action_on_a_single_contact_only_touches_that_contact(self):
        child = self._child()
        sibling = self._child()
        (child | sibling).with_context(**SYNC).write(
            {'property_payment_term_id': self.term_c.id})

        child.action_cl_sync_payment_terms()

        child.invalidate_recordset()
        sibling.invalidate_recordset()
        self.assertEqual(child.property_payment_term_id, self.term_a)
        self.assertEqual(sibling.property_payment_term_id, self.term_c)
