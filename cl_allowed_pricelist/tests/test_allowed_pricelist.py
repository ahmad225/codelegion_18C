# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestAllowedPricelist(TransactionCase):
    """Run with:  odoo-bin -d <db> -i cl_allowed_pricelist --test-tags /cl_allowed_pricelist

    The rule is about what a person may choose, and the system itself
    (superuser) is exempt, so the orders are made here by a real salesperson.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Pricelist = cls.env['product.pricelist']
        cls.pl_other = Pricelist.create({'name': 'CL Not Allowed'})
        cls.pl_trade = Pricelist.create({'name': 'CL Trade'})
        cls.pl_promo = Pricelist.create({'name': 'CL Promo'})
        cls.pl_own = Pricelist.create({'name': 'CL Negotiated'})
        cls.allowed = cls.pl_trade | cls.pl_promo

        cls.restricted = cls.env['res.partner'].create({
            'name': 'Restricted Co', 'is_company': True,
            'cl_order_pricelist_ids': [(6, 0, cls.allowed.ids)],
        })
        cls.buyer = cls.env['res.partner'].create({
            'name': 'Buyer at Restricted Co', 'parent_id': cls.restricted.id})
        cls.free = cls.env['res.partner'].create({
            'name': 'Unrestricted Co', 'is_company': True})

        cls.salesperson = new_test_user(
            cls.env, login='cl_pricelist_salesperson',
            groups='sales_team.group_sale_salesman_all_leads')
        cls.Order = cls.env['sale.order'].with_user(cls.salesperson)

    # ------------------------------------------------------------------
    # default pricelist of a new quotation
    # ------------------------------------------------------------------
    def test_new_quotation_starts_on_an_allowed_pricelist(self):
        order = self.Order.create({'partner_id': self.restricted.id})
        self.assertIn(order.pricelist_id, self.allowed)

    def test_customer_own_pricelist_stays_usable_and_is_the_default(self):
        self.restricted.specific_property_product_pricelist = self.pl_own
        order = self.Order.create({'partner_id': self.restricted.id})
        self.assertEqual(order.pricelist_id, self.pl_own)
        order.pricelist_id = self.pl_trade  # and the listed ones still are
        self.assertEqual(order.pricelist_id, self.pl_trade)

    def test_changing_the_customer_moves_the_quotation_to_an_allowed_pricelist(self):
        order = self.Order.create({'partner_id': self.free.id})
        order.partner_id = self.restricted
        self.assertIn(order.pricelist_id, self.allowed)

    # ------------------------------------------------------------------
    # the check
    # ------------------------------------------------------------------
    def test_disallowed_pricelist_is_refused_on_create(self):
        with self.assertRaises(ValidationError):
            self.Order.create({
                'partner_id': self.restricted.id, 'pricelist_id': self.pl_other.id})

    def test_disallowed_pricelist_is_refused_on_write(self):
        order = self.Order.create({
            'partner_id': self.restricted.id, 'pricelist_id': self.pl_promo.id})
        with self.assertRaises(ValidationError):
            order.pricelist_id = self.pl_other
            order.flush_recordset()

    def test_contacts_follow_their_company(self):
        order = self.Order.create({'partner_id': self.buyer.id})
        self.assertIn(order.pricelist_id, self.allowed)
        with self.assertRaises(ValidationError):
            self.Order.create({
                'partner_id': self.buyer.id, 'pricelist_id': self.pl_other.id})

    def test_unrestricted_customer_takes_any_pricelist(self):
        order = self.Order.create({
            'partner_id': self.free.id, 'pricelist_id': self.pl_other.id})
        self.assertEqual(order.pricelist_id, self.pl_other)

    def test_list_of_another_company_does_not_restrict(self):
        other_company = self.env['res.company'].create({'name': 'CL Pricelist Other Co'})
        foreign = self.env['product.pricelist'].create(
            {'name': 'CL Foreign', 'company_id': other_company.id})
        self.free.cl_order_pricelist_ids = foreign
        order = self.Order.create({
            'partner_id': self.free.id, 'pricelist_id': self.pl_other.id})
        self.assertEqual(order.pricelist_id, self.pl_other)

    # ------------------------------------------------------------------
    # exemptions
    # ------------------------------------------------------------------
    def test_skip_key(self):
        order = self.Order.with_context(cl_skip_pricelist_check=True).create({
            'partner_id': self.restricted.id, 'pricelist_id': self.pl_other.id})
        self.assertEqual(order.pricelist_id, self.pl_other)

    def test_system_orders_are_not_checked(self):
        """Connectors and scheduled jobs run as the superuser."""
        order = self.env['sale.order'].sudo().create({
            'partner_id': self.restricted.id, 'pricelist_id': self.pl_other.id})
        self.assertEqual(order.pricelist_id, self.pl_other)

    # ------------------------------------------------------------------
    # what the form offers
    # ------------------------------------------------------------------
    def test_form_domain(self):
        restricted_order = self.Order.create({'partner_id': self.restricted.id})
        id_leaves = [leaf for leaf in restricted_order.cl_pricelist_domain if leaf[0] == 'id']
        self.assertEqual(len(id_leaves), 1)
        self.assertEqual(set(id_leaves[0][2]), set(self.allowed.ids))

        free_order = self.Order.create({'partner_id': self.free.id})
        self.assertFalse([leaf for leaf in free_order.cl_pricelist_domain if leaf[0] == 'id'])
        # both keep the standard company filter
        self.assertTrue([leaf for leaf in free_order.cl_pricelist_domain if leaf[0] == 'company_id'])
