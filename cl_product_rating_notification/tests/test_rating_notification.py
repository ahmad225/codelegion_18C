# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests import TransactionCase, tagged

LOGGER = 'odoo.addons.cl_product_rating_notification.models.rating_rating'


@tagged('post_install', '-at_install')
class TestRatingNotification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].get_current_website()
        # Reviews of a shared product notify the team of the website's company.
        cls.company = cls.website.company_id
        cls.mail_template = cls.env.ref(
            'cl_product_rating_notification.mail_template_product_rating')
        cls.manager = cls.env['res.partner'].create(
            {'name': 'Shop Manager', 'email': 'shop.manager@example.com'})
        cls.company.write({
            'email': 'shop@mycompany.example',
            'cl_rating_partner_ids': [(6, 0, cls.manager.ids)],
            'cl_rating_template_id': cls.mail_template.id,
        })
        cls.template = cls.env['product.template'].create({'name': 'Reviewed Mug'})
        cls.customer = cls.env['res.partner'].create(
            {'name': 'Happy Customer', 'email': 'happy.customer@example.com'})

    def _mails(self, rating):
        return self.env['mail.mail'].search(
            [('model', '=', 'rating.rating'), ('res_id', '=', rating.id)])

    def _rating(self, res_model='product.template', res_id=None, user=None, **vals):
        Rating = self.env['rating.rating']
        if user:
            # Like Odoo itself: saved with sudo inside the customer's session.
            Rating = Rating.with_user(user)
        return Rating.sudo().create(dict({
            'res_model_id': self.env['ir.model']._get_id(res_model),
            'res_id': res_id or self.template.id,
            'partner_id': self.customer.id,
            'rating': 5,
            'feedback': 'Great mug',
            'consumed': True,
        }, **vals))

    def test_new_review_notifies_team(self):
        rating = self._rating()
        mails = self._mails(rating)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.recipient_ids, self.manager)
        self.assertIn('New review', mails.subject)
        self.assertIn('Great mug', mails.body_html)
        # Queued, not sent while the customer waits.
        self.assertEqual(mails.state, 'outgoing')

    def test_edited_review_notifies_again(self):
        rating = self._rating()
        rating.write({'rating': 2, 'feedback': 'Cracked after a week'})
        mails = self._mails(rating)
        self.assertEqual(len(mails), 2)
        self.assertTrue(any('Updated review' in subject for subject in mails.mapped('subject')))

    def test_saving_without_a_change_is_silent(self):
        rating = self._rating()
        rating.write({'rating': 5, 'feedback': 'Great mug'})
        rating.write({'publisher_comment': 'Thank you!'})
        self.assertEqual(len(self._mails(rating)), 1)

    def test_request_filled_in_later_counts_as_new(self):
        rating = self._rating(rating=0, feedback=False, consumed=False)
        self.assertFalse(self._mails(rating))
        rating.write({'rating': 4, 'feedback': 'Nice', 'consumed': True})
        mails = self._mails(rating)
        self.assertEqual(len(mails), 1)
        self.assertIn('New review', mails.subject)

    def test_other_models_ignored(self):
        rating = self._rating(res_model='res.partner', res_id=self.customer.id)
        self.assertFalse(self._mails(rating))
        rating.write({'rating': 1})
        self.assertFalse(self._mails(rating))

    def test_no_recipients_no_email(self):
        self.company.cl_rating_partner_ids = False
        self.assertFalse(self._mails(self._rating()))

    def test_sender_is_the_company_not_the_reviewer(self):
        public_user = self.env.ref('base.public_user')
        mails = self._mails(self._rating(user=public_user))
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_from, self.company.email_formatted)

    def test_template_without_sender_uses_the_company(self):
        self.mail_template.email_from = False
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Reviewer', 'login': 'cl_portal_reviewer',
            'email': 'portal.reviewer@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        mails = self._mails(self._rating(user=portal_user))
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_from, self.company.email_formatted)

    def test_broken_template_never_blocks_the_review(self):
        self.mail_template.subject = '{{ object.cl_field_that_does_not_exist }}'
        with self.assertLogs(LOGGER, level='ERROR'):
            rating = self._rating()
        self.assertTrue(rating.exists())
        self.assertFalse(self._mails(rating))

    def test_product_company_team_is_notified(self):
        company_b = self.env['res.company'].create({
            'name': 'CL Second Company', 'email': 'shop-b@example.com'})
        manager_b = self.env['res.partner'].create(
            {'name': 'Second Manager', 'email': 'manager.b@example.com'})
        company_b.cl_rating_partner_ids = [(6, 0, manager_b.ids)]
        # A new company picks the shipped template by default.
        self.assertEqual(company_b.cl_rating_template_id, self.mail_template)
        product_b = self.env['product.template'].create(
            {'name': 'Second Mug', 'company_id': company_b.id})
        mails = self._mails(self._rating(res_id=product_b.id))
        self.assertEqual(mails.recipient_ids, manager_b)
        self.assertEqual(mails.email_from, company_b.email_formatted)

    def test_company_without_setup_falls_back_to_the_shop(self):
        company_c = self.env['res.company'].create({'name': 'CL Third Company'})
        product_c = self.env['product.template'].create(
            {'name': 'Third Mug', 'company_id': company_c.id})
        mails = self._mails(self._rating(res_id=product_c.id))
        self.assertEqual(mails.recipient_ids, self.manager)

    def test_setting_is_stored_on_the_website_company(self):
        other = self.env['res.partner'].create(
            {'name': 'Other Manager', 'email': 'other.manager@example.com'})
        settings = self.env['res.config.settings'].create({'website_id': self.website.id})
        self.assertEqual(settings.cl_rating_partner_ids, self.manager)
        settings.cl_rating_partner_ids = [(4, other.id)]
        self.assertEqual(self.company.cl_rating_partner_ids, self.manager | other)
