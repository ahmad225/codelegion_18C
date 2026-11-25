# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBackInStockServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].get_current_website()
        # The company a shared product follows when the job runs.
        cls.company = cls.website.company_id
        cls.server = cls.env['ir.mail_server'].create({
            'name': 'Marketing SMTP', 'smtp_host': 'smtp.marketing.example'})
        cls.company.cl_back_in_stock_mail_server_id = cls.server

    def _mail(self, **ctx):
        return self.env['mail.mail'].with_context(**ctx).create({
            'subject': 'Hello', 'email_to': 'someone@example.com', 'body_html': '<p>x</p>'})

    def _waiting_product(self, email, **vals):
        partner = self.env['res.partner'].create({'name': email, 'email': email})
        # A consumable that is not tracked in stock is never "sold out", so
        # the job sends its email straight away.
        return self.env['product.product'].create(dict({
            'name': 'Popular Mug', 'type': 'consu',
            'stock_notification_partner_ids': [(6, 0, partner.ids)]}, **vals))

    def _mails_to(self, email):
        return self.env['mail.mail'].search([('email_to', 'ilike', email)])

    def test_flagged_mail_uses_dedicated_server(self):
        mail = self._mail(cl_back_in_stock_server_id=self.server.id)
        self.assertEqual(mail.mail_server_id, self.server)

    def test_other_mail_untouched(self):
        self.assertFalse(self._mail().mail_server_id)
        self.assertFalse(self._mail(cl_back_in_stock_server_id=False).mail_server_id)

    def test_availability_email_uses_server(self):
        product = self._waiting_product('waiting@example.com')
        self.env['product.product']._send_availability_email()
        mail = self._mails_to('waiting@example.com')
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.mail_server_id, self.server)
        self.assertFalse(product.stock_notification_partner_ids)

    def test_no_server_keeps_odoo_behaviour(self):
        self.company.cl_back_in_stock_mail_server_id = False
        product = self._waiting_product('plain@example.com')
        self.env['product.product']._send_availability_email()
        mail = self._mails_to('plain@example.com')
        self.assertEqual(len(mail), 1)
        self.assertFalse(mail.mail_server_id)
        self.assertFalse(product.stock_notification_partner_ids)

    def test_archived_server_is_ignored(self):
        # Odoo refuses to send through an archived server: the email would
        # fail and the customer would still be dropped from the waiting list.
        self.server.active = False
        self._waiting_product('archived@example.com')
        self.env['product.product']._send_availability_email()
        mail = self._mails_to('archived@example.com')
        self.assertEqual(len(mail), 1)
        self.assertFalse(mail.mail_server_id)

    def test_each_company_uses_its_own_server(self):
        company_b = self.env['res.company'].create({
            'name': 'CL Second Company', 'email': 'shop-b@example.com'})
        server_b = self.env['ir.mail_server'].create({
            'name': 'Second SMTP', 'smtp_host': 'smtp.second.example'})
        company_b.cl_back_in_stock_mail_server_id = server_b
        company_c = self.env['res.company'].create({
            'name': 'CL Third Company', 'email': 'shop-c@example.com'})

        shared = self._waiting_product('shared@example.com')
        product_b = self._waiting_product('b-waiting@example.com', company_id=company_b.id)
        product_c = self._waiting_product('c-waiting@example.com', company_id=company_c.id)
        self.env['product.product']._send_availability_email()

        # One email each: the per-server runs never send a product twice.
        for email, server in (
            ('shared@example.com', self.server),
            ('b-waiting@example.com', server_b),
            # No server of its own: follows the website's company.
            ('c-waiting@example.com', self.server),
        ):
            mail = self._mails_to(email)
            self.assertEqual(len(mail), 1, email)
            self.assertEqual(mail.mail_server_id, server, email)
        self.assertFalse((shared + product_b + product_c).stock_notification_partner_ids)

    def test_sold_out_untouched_outside_the_job(self):
        product = self._waiting_product('shopper@example.com')
        self.assertFalse(product._is_sold_out())

    def test_setting_is_stored_on_the_website_company(self):
        other = self.env['ir.mail_server'].create({
            'name': 'Other SMTP', 'smtp_host': 'smtp.other.example'})
        settings = self.env['res.config.settings'].create({'website_id': self.website.id})
        self.assertEqual(settings.cl_back_in_stock_mail_server_id, self.server)
        settings.cl_back_in_stock_mail_server_id = other
        self.assertEqual(self.company.cl_back_in_stock_mail_server_id, other)
