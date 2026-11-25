# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import (
    AccountTestInvoicingCommon, AccountTestInvoicingHttpCommon)

REPORT = 'cl_customer_statement.action_report_customer_statement'


class StatementCommon:
    """Helpers shared by the back-office and the portal tests."""

    @classmethod
    def _invoice(cls, partner, amount, inv_date, due_date, company_data=None):
        company_data = company_data or cls.company_data
        move = cls.env['account.move'].with_company(company_data['company']).create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': inv_date,
            'invoice_date_due': due_date,
            'invoice_payment_term_id': False,
            'invoice_line_ids': [(0, 0, {
                'name': 'Service', 'quantity': 1, 'price_unit': amount,
                'account_id': company_data['default_account_revenue'].id,
                'tax_ids': []})],
        })
        move.action_post()
        return move


@tagged('post_install', '-at_install')
class TestCustomerStatement(StatementCommon, AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Log = cls.env['cl.customer.statement.log']
        cls.customer = cls.env['res.partner'].create(
            {'name': 'Statement Customer', 'email': 'ar@customer.example'})
        cls.inv1 = cls._invoice(cls.customer, 100.0, date(2026, 1, 10), date(2026, 2, 9))
        cls.inv2 = cls._invoice(cls.customer, 50.0, date(2026, 2, 5), date(2026, 3, 7))

    def _auto_logs(self, partner=None):
        domain = [('auto', '=', True)]
        if partner:
            domain.append(('partner_id', '=', partner.id))
        return self.Log.search(domain)

    def _run_job(self):
        self.env['res.partner']._cron_cl_send_monthly_statements()

    # ---- statement engine ---------------------------------------------
    def test_account_statement_balances(self):
        jan = self.customer._cl_statement_data(self.company, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(jan['opening'], 0.0)
        self.assertAlmostEqual(jan['closing'], 100.0)
        feb = self.customer._cl_statement_data(self.company, date(2026, 2, 1), date(2026, 2, 28))
        self.assertAlmostEqual(feb['opening'], 100.0)
        self.assertAlmostEqual(feb['closing'], 150.0)
        self.assertEqual(len(feb['rows']), 1)
        self.assertAlmostEqual(feb['rows'][0]['debit'], 50.0)

    def test_child_contact_resolves_to_company(self):
        contact = self.env['res.partner'].create(
            {'name': 'AP Clerk', 'parent_id': self.customer.id})
        data = contact._cl_statement_data(self.company, date(2026, 1, 1), date(2026, 2, 28))
        self.assertEqual(data['partner'], self.customer)
        self.assertAlmostEqual(data['closing'], 150.0)

    def test_overdue_and_ageing_by_due_date(self):
        as_of = date(2026, 3, 15)
        overdue = self.customer._cl_overdue_data(self.company, as_of)
        names = [row['name'] for row in overdue['rows']]
        self.assertIn(self.inv1.name, names)   # due 9 Feb -> 34 days
        self.assertIn(self.inv2.name, names)   # due 7 Mar -> 8 days
        ageing = overdue['ageing']
        self.assertAlmostEqual(ageing['days_31_60'], 100.0)
        self.assertAlmostEqual(ageing['days_1_30'], 50.0)
        self.assertAlmostEqual(ageing['total'], 150.0)

    # ---- printing ------------------------------------------------------
    def test_print_from_wizard_carries_the_customers(self):
        """With options, the web client calls the report without record ids:
        the customers must travel with the options or the PDF is empty."""
        wizard = self.env['cl.customer.statement.wizard'].create({
            'partner_ids': [(6, 0, self.customer.ids)],
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 2, 28),
        })
        action = wizard.action_print()
        self.assertEqual(action['data']['partner_ids'], self.customer.ids)
        report_model = self.env['report.cl_customer_statement.report_customer_statement']
        values = report_model._get_report_values(None, data=action['data'])
        self.assertEqual(len(values['statements']), 1)
        self.assertAlmostEqual(values['statements'][0]['closing'], 150.0)

    def test_report_renders(self):
        for statement_type in ('account', 'overdue'):
            html = self.env['ir.actions.report']._render_qweb_html(REPORT, self.customer.ids, data={
                'company_id': self.company.id,
                'statement_type': statement_type,
                'date_from': '2026-01-01',
                'date_to': '2026-03-15',
            })[0]
            if isinstance(html, bytes):
                html = html.decode()
            self.assertIn(self.inv1.name, html)

    def test_wizard_refuses_company_not_selected(self):
        other = self.setup_other_company()['company']
        wizard = self.env['cl.customer.statement.wizard'].with_context(
            allowed_company_ids=self.company.ids).create({
                'partner_ids': [(6, 0, self.customer.ids)],
                'company_id': other.id,
                'date_from': date(2026, 1, 1),
                'date_to': date(2026, 2, 28),
            })
        with self.assertRaises(UserError):
            wizard.action_print()

    # ---- sending -------------------------------------------------------
    def test_recipients(self):
        self.assertEqual(self.customer._cl_statement_recipients(), self.customer)
        ap = self.env['res.partner'].create({
            'name': 'Accounts Payable', 'parent_id': self.customer.id,
            'email': 'ap@customer.example'})
        self.customer.cl_statement_contact_ids = [(6, 0, ap.ids)]
        self.assertEqual(self.customer._cl_statement_recipients(), ap)

    def test_send_attaches_pdf_and_logs(self):
        log = self.customer._cl_send_statement(
            self.company, 'account', date(2026, 1, 1), date(2026, 2, 28))
        self.assertEqual(log.state, 'sent')
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.customer.id)])
        self.assertTrue(attachment)
        self.assertFalse(attachment.filtered('public'), "Statements must never be public files.")
        mail = self.env['mail.mail'].sudo().search([('attachment_ids', 'in', attachment.ids)])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.customer)

    def test_no_email_is_logged_as_failed(self):
        silent = self.env['res.partner'].create({'name': 'No Email Co'})
        log = silent._cl_send_statement(
            self.company, 'account', date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(log.state, 'failed')

    # ---- monthly job (10 March 2026: the period is February 2026) -------
    @freeze_time('2026-03-10')
    def test_job_sends_last_month_once(self):
        self.company.sudo().write({'cl_statement_auto_send': True, 'cl_statement_send_day': 5})
        # The job must neither commit nor roll back the test transaction.
        self._run_job()
        log = self._auto_logs()
        self.assertEqual(len(log), 1)
        self.assertEqual(log.partner_id, self.customer)
        self.assertEqual(log.state, 'sent')
        self.assertEqual((log.date_from, log.date_to), (date(2026, 2, 1), date(2026, 2, 28)))
        self._run_job()
        self.assertEqual(self._auto_logs(), log, "One statement per customer and period.")

    @freeze_time('2026-03-10')
    def test_job_waits_for_send_day_and_respects_opt_out(self):
        self.company.sudo().write({'cl_statement_auto_send': True, 'cl_statement_send_day': 15})
        self._run_job()
        self.assertFalse(self._auto_logs())
        self.company.sudo().cl_statement_send_day = 10
        self.customer.cl_statement_opt_out = True
        self._run_job()
        self.assertFalse(self._auto_logs())

    @freeze_time('2026-03-10')
    def test_job_retries_once_the_customer_has_an_email(self):
        self.company.sudo().write({'cl_statement_auto_send': True, 'cl_statement_send_day': 1})
        self.customer.email = False
        self._run_job()
        failed = self._auto_logs()
        self.assertEqual(failed.state, 'failed')
        # same day: one attempt only
        self._run_job()
        self.assertEqual(self._auto_logs(), failed)
        # later days, still nobody to email: nothing new is logged
        self.env.cr.execute(
            "UPDATE cl_customer_statement_log SET create_date = '2026-03-01' WHERE id = %s",
            [failed.id])
        failed.invalidate_recordset(['create_date'])
        self._run_job()
        self.assertEqual(self._auto_logs(), failed)
        # the address is filled in: the statement goes out, one line remains
        self.customer.email = 'ar@customer.example'
        self._run_job()
        log = self._auto_logs()
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'sent')

    @freeze_time('2026-03-10')
    def test_job_ignores_customer_settled_through_a_contact(self):
        """Invoice on the company, settlement booked on one of its contacts,
        nothing in the period: no statement."""
        self.company.sudo().write({'cl_statement_auto_send': True, 'cl_statement_send_day': 1})
        settled = self.env['res.partner'].create(
            {'name': 'Settled Customer', 'email': 'settled@customer.example'})
        contact = self.env['res.partner'].create(
            {'name': 'Their Cashier', 'parent_id': settled.id})
        invoice = self._invoice(settled, 80.0, date(2025, 12, 1), date(2025, 12, 31))
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable').account_id
        self.env['account.move'].create({
            'move_type': 'entry',
            'date': date(2025, 12, 20),
            'line_ids': [
                (0, 0, {'name': 'Settlement', 'partner_id': contact.id,
                        'account_id': receivable.id, 'credit': 80.0}),
                (0, 0, {'name': 'Settlement', 'debit': 80.0,
                        'account_id': self.company_data['default_account_revenue'].id}),
            ],
        }).action_post()
        self._run_job()
        self.assertFalse(self._auto_logs(settled))
        self.assertEqual(self._auto_logs(self.customer).state, 'sent')

    @freeze_time('2026-03-10')
    def test_job_per_company(self):
        """Only the companies with the option on send, each for its own books."""
        company_data_2 = self.setup_other_company()
        company_2 = company_data_2['company']
        company_2.sudo().write({'cl_statement_auto_send': True, 'cl_statement_send_day': 1})
        other_customer = self.env['res.partner'].create(
            {'name': 'Customer Of Company 2', 'email': 'c2@customer.example'})
        self._invoice(other_customer, 70.0, date(2026, 2, 10), date(2026, 3, 12),
                      company_data=company_data_2)
        self._run_job()
        log = self._auto_logs()
        self.assertEqual(log.partner_id, other_customer)
        self.assertEqual(log.company_id, company_2)


@tagged('post_install', '-at_install')
class TestCustomerStatementPortal(StatementCommon, AccountTestInvoicingHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create(
            {'name': 'Portal Customer', 'email': 'portal@customer.example'})
        cls.stranger = cls.env['res.partner'].create(
            {'name': 'Another Customer', 'email': 'other@customer.example'})
        cls.own_invoice = cls._invoice(
            cls.customer, 100.0, date(2026, 1, 10), date(2026, 2, 9))
        cls.other_invoice = cls._invoice(
            cls.stranger, 999.0, date(2026, 1, 11), date(2026, 2, 10))
        cls.portal_user = new_test_user(
            cls.env, login='cl_statement_portal', groups='base.group_portal',
            name='Portal Customer', partner_id=cls.customer.id)

    def test_portal_shows_own_statement_only(self):
        self.authenticate('cl_statement_portal', 'cl_statement_portal')
        page = self.url_open('/my/statement?date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.own_invoice.name, page.text)
        self.assertNotIn(self.other_invoice.name, page.text)
        for statement_type in ('account', 'overdue'):
            pdf = self.url_open(
                '/my/statement/pdf?statement_type=%s&date_from=2026-01-01&date_to=2026-12-31'
                % statement_type)
            self.assertEqual(pdf.status_code, 200)
            self.assertNotIn(self.other_invoice.name, pdf.text)

    def test_portal_user_cannot_print_another_customer(self):
        """The generic report route must not be a way around the portal."""
        self.authenticate('cl_statement_portal', 'cl_statement_portal')
        response = self.url_open(
            '/report/html/cl_customer_statement.report_customer_statement'
            '?options={"partner_ids":[%s],"company_id":%s}'
            % (self.stranger.id, self.env.company.id))
        self.assertNotIn(self.other_invoice.name, response.text)
