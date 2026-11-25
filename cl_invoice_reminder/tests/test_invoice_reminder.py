# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestInvoiceReminder(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env['account.move']
        cls.Stage = cls.env['cl.invoice.reminder.stage']
        cls.Mail = cls.env['mail.mail'].sudo()
        cls.today = fields.Date.context_today(cls.Move)
        cls.customer = cls.env['res.partner'].create({
            'name': 'Customer With Email', 'email': 'customer@example.com'})
        cls.customer_2 = cls.env['res.partner'].create({
            'name': 'Second Customer', 'email': 'second@example.com'})
        cls.customer_no_email = cls.env['res.partner'].create({
            'name': 'Customer Without Email'})

    @classmethod
    def _overdue_invoice(cls, partner, days, amount=100.0,
                         move_type='out_invoice', company_data=None):
        """Posted, unpaid invoice whose due date is ``days`` days ago."""
        company_data = company_data or cls.company_data
        move = cls.Move.with_company(company_data['company']).create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': cls.today - timedelta(days=days + 5),
            'invoice_date_due': cls.today - timedelta(days=days),
            'invoice_payment_term_id': False,
            'invoice_line_ids': [(0, 0, {
                'name': 'Service',
                'quantity': 1,
                'price_unit': amount,
                'account_id': company_data['default_account_revenue'].id,
                'tax_ids': [],
            })],
        })
        move.action_post()
        return move

    @classmethod
    def _stage(cls, days, company=None):
        vals = {'name': 'After %s days' % days, 'delay_days': days}
        if company:
            vals['company_id'] = company.id
        return cls.Stage.create(vals)

    def _run_job(self):
        self.Move._cron_cl_send_invoice_reminders()

    # ---- schedule ------------------------------------------------------
    def test_stage_defaults_and_constraints(self):
        stage = self._stage(15)
        self.assertEqual(
            stage.template_id,
            self.env.ref('cl_invoice_reminder.email_template_overdue_invoices'))
        with self.assertRaises(ValidationError):
            self._stage(0)
        with self.assertRaises(ValidationError):
            self._stage(15)  # same delay twice in one company
        # an archived stage frees its slot
        stage.active = False
        self._stage(15)

    # ---- days overdue --------------------------------------------------
    def test_days_overdue_search_matches_displayed_value(self):
        """Every operator must agree with the number shown on the record."""
        invoice = self._overdue_invoice(self.customer, 10)
        self.assertEqual(invoice.cl_days_overdue, 10)
        # A vendor bill with a past due date is not "overdue" for us.
        bill = self._overdue_invoice(self.customer, 20, move_type='in_invoice')
        self.assertEqual(bill.cl_days_overdue, 0)
        both = (invoice | bill).ids

        def found(operator, value):
            return self.Move.search(
                [('id', 'in', both), ('cl_days_overdue', operator, value)])

        self.assertEqual(found('>', 0), invoice)
        self.assertEqual(found('>=', 10), invoice)
        self.assertEqual(found('>', 10), self.Move)
        self.assertEqual(found('=', 10), invoice)
        self.assertEqual(found('=', 0), bill)
        self.assertEqual(found('<', 5), bill)
        self.assertEqual(found('<=', 10), invoice | bill)
        self.assertEqual(found('!=', 10), bill)
        self.assertEqual(found('!=', 0), invoice)
        self.assertEqual(found('>=', 0), invoice | bill)
        with self.assertRaises(UserError):
            found('ilike', 'x')

    # ---- job -----------------------------------------------------------
    def test_job_sends_and_records(self):
        stage = self._stage(10)
        invoice = self._overdue_invoice(self.customer, 20)
        before = self.Mail.search([])
        # The job must neither commit nor roll back the test transaction: the
        # test framework forbids both on its cursor.
        self._run_job()
        log = invoice.cl_reminder_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.stage_id, stage)
        self.assertEqual(log.email, 'customer@example.com')
        self.assertEqual(log.amount_due, 100.0)
        self.assertEqual(log.days_overdue, 20)
        self.assertEqual(log.partner_id, self.customer)
        self.assertEqual(log.company_id, self.env.company)
        self.assertEqual(invoice.cl_reminder_count, 1)
        self.assertEqual(invoice.cl_reminder_stage_id, stage)
        self.assertEqual(invoice.cl_reminder_date, log.sent_date)
        mail = self.Mail.search([]) - before
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.customer)
        self.assertIn(invoice.name, mail.body_html)
        # the button on the invoice opens exactly these lines
        action = invoice.action_cl_view_reminders()
        self.assertEqual(
            self.env['cl.invoice.reminder.log'].search(action['domain']), log)

    def test_job_one_email_per_customer_and_no_repeat(self):
        self._stage(10)
        first = self._overdue_invoice(self.customer, 20)
        second = self._overdue_invoice(self.customer, 25)
        before = self.Mail.search_count([])
        self._run_job()
        self.assertEqual(self.Mail.search_count([]) - before, 1,
                         "Two invoices of one customer: one email.")
        self.assertEqual(first.cl_reminder_count, 1)
        self.assertEqual(second.cl_reminder_count, 1)
        self._run_job()
        self._run_job()
        self.assertEqual(self.Mail.search_count([]) - before, 1,
                         "A stage is sent once per invoice.")
        self.assertEqual(first.cl_reminder_count, 1)

    def test_job_skips_customer_without_email(self):
        self._stage(10)
        invoice = self._overdue_invoice(self.customer_no_email, 20)
        self._run_job()
        self.assertFalse(invoice.cl_reminder_log_ids,
                         "Nothing may be recorded when no email could be sent.")
        self.assertFalse(invoice.cl_reminder_stage_id)
        # the "No Email Address" filter of the work list finds it
        self.assertIn(invoice, self.Move.search([
            ('cl_days_overdue', '>', 0),
            ('partner_id.email', '=', False),
            ('commercial_partner_id.email', '=', False)]))
        # as soon as the customer has an address, the reminder goes out
        self.customer_no_email.email = 'late@example.com'
        self._run_job()
        self.assertEqual(invoice.cl_reminder_log_ids.email, 'late@example.com')

    def test_job_uses_company_email_for_invoice_address(self):
        """An invoice address without email is reminded through the company
        it belongs to."""
        self._stage(10)
        address = self.env['res.partner'].create({
            'name': 'Invoice Address', 'type': 'invoice',
            'parent_id': self.customer.id, 'email': False})
        invoice = self._overdue_invoice(address, 20)
        before = self.Mail.search([])
        self._run_job()
        self.assertEqual(invoice.cl_reminder_log_ids.email, 'customer@example.com')
        self.assertEqual(invoice.cl_reminder_log_ids.partner_id, address)
        self.assertEqual((self.Mail.search([]) - before).recipient_ids, self.customer)

    def test_job_sends_latest_stage_only(self):
        """An invoice already 40 days overdue gets the 30-day reminder, not
        the 7, 15 and 30-day ones one after the other."""
        self._stage(7)
        stage_15 = self._stage(15)
        stage_30 = self._stage(30)
        old = self._overdue_invoice(self.customer, 40)
        recent = self._overdue_invoice(self.customer_2, 16)
        self.assertFalse(old.cl_reminder_final)
        before = self.Mail.search_count([])
        self._run_job()
        self.assertEqual(old.cl_reminder_stage_id, stage_30)
        self.assertEqual(recent.cl_reminder_stage_id, stage_15)
        self.assertEqual(self.Mail.search_count([]) - before, 2)
        # later runs never go back to an earlier stage
        self._run_job()
        self.assertEqual(self.Mail.search_count([]) - before, 2)
        self.assertEqual(old.cl_reminder_count, 1)
        self.assertEqual(recent.cl_reminder_count, 1)
        # "final reminder sent" follows the last stage of the schedule
        (old | recent).invalidate_recordset(['cl_reminder_final'])
        self.assertTrue(old.cl_reminder_final)
        self.assertFalse(recent.cl_reminder_final)
        both = [('id', 'in', (old | recent).ids)]
        self.assertEqual(
            self.Move.search(both + [('cl_reminder_final', '=', True)]), old)
        self.assertEqual(
            self.Move.search(both + [('cl_reminder_final', '=', False)]), recent)
        # an archived stage still counts: re-creating it does not send the
        # same reminder a second time
        stage_30.active = False
        self._stage(30)
        self._run_job()
        self.assertEqual(old.cl_reminder_count, 1)
        self.assertEqual(old.cl_reminder_stage_id, stage_30)

    def test_job_escalates_over_time(self):
        """The normal life of an invoice: one stage after the other."""
        stage_7 = self._stage(7)
        stage_15 = self._stage(15)
        invoice = self._overdue_invoice(self.customer, 8)
        self._run_job()
        self.assertEqual(invoice.cl_reminder_stage_id, stage_7)
        # a week later the invoice is 15 days overdue
        with freeze_time(self.today + timedelta(days=7)):
            self._run_job()
        self.assertEqual(invoice.cl_reminder_stage_id, stage_15)
        self.assertEqual(invoice.cl_reminder_count, 2)
        self.assertEqual(invoice.cl_reminder_log_ids.stage_id, stage_7 | stage_15)

    def test_job_batch_size(self):
        stage = self._stage(10)
        self.env.company.sudo().cl_reminder_batch_size = 1
        first = self._overdue_invoice(self.customer, 20)
        second = self._overdue_invoice(self.customer_2, 20)
        Move = self.Move.sudo().with_company(self.env.company)
        self.assertEqual(Move._cl_send_company_reminders(stage.sudo()), (1, 1))
        self.assertEqual(first.cl_reminder_count + second.cl_reminder_count, 1)
        # the next run serves the customer that was left over
        self.assertEqual(Move._cl_send_company_reminders(stage.sudo()), (1, 0))
        self.assertEqual(first.cl_reminder_count, 1)
        self.assertEqual(second.cl_reminder_count, 1)

    def test_job_failure_does_not_block_other_customers(self):
        self._stage(10)
        bad = self._overdue_invoice(self.customer, 20)
        good = self._overdue_invoice(self.customer_2, 20)
        MailTemplate = type(self.env['mail.template'])
        original = MailTemplate.send_mail
        failing_partner = self.customer

        def send_mail(template, res_id, *args, **kwargs):
            if res_id == failing_partner.id:
                raise UserError("Cannot render")
            return original(template, res_id, *args, **kwargs)

        with patch.object(MailTemplate, 'send_mail', send_mail), \
                self.assertLogs('odoo.addons.cl_invoice_reminder', level='ERROR'):
            self._run_job()
        self.assertEqual(good.cl_reminder_count, 1)
        self.assertFalse(bad.cl_reminder_log_ids)
        self.assertFalse(bad.cl_reminder_stage_id)

    def test_job_multi_company(self):
        """One run serves every company, each with its own schedule and its
        own sender address."""
        company_data_2 = self.setup_other_company()
        company_2 = company_data_2['company']
        company_2.sudo().partner_id.email = 'billing@company2.example.com'
        self._stage(10)
        stage_2 = self._stage(5, company=company_2)
        invoice_1 = self._overdue_invoice(self.customer, 20)
        invoice_2 = self._overdue_invoice(
            self.customer_2, 8, company_data=company_data_2)
        before = self.Mail.search([])
        self._run_job()
        self.assertEqual(invoice_1.cl_reminder_count, 1)
        self.assertEqual(invoice_2.cl_reminder_stage_id, stage_2)
        mail_2 = (self.Mail.search([]) - before).filtered(
            lambda m: m.recipient_ids == self.customer_2)
        self.assertEqual(len(mail_2), 1)
        self.assertIn('billing@company2.example.com', mail_2.email_from)
