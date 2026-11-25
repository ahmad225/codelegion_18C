# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging
import threading
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

REPORT_XMLID = 'cl_customer_statement.action_report_customer_statement'
AGEING_BUCKETS = [
    ('not_due', 'Not due'),
    ('days_1_30', '1-30 days'),
    ('days_31_60', '31-60 days'),
    ('days_61_90', '61-90 days'),
    ('days_90_plus', 'Over 90 days'),
]


def _bucket(days_overdue):
    if days_overdue <= 0:
        return 'not_due'
    if days_overdue <= 30:
        return 'days_1_30'
    if days_overdue <= 60:
        return 'days_31_60'
    if days_overdue <= 90:
        return 'days_61_90'
    return 'days_90_plus'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cl_statement_contact_ids = fields.Many2many(
        'res.partner', 'cl_partner_statement_contact_rel', 'partner_id', 'contact_id',
        string='Statement Recipients',
        help="Contacts who receive this customer's statements. If empty, the "
             "statement goes to the customer's own email address.")
    cl_statement_opt_out = fields.Boolean(
        string='No Automatic Statements',
        help="Leave this customer out of the monthly automatic statements.")

    # ------------------------------------------------------------------
    # Statement engine - everything is computed live from the ledger
    # ------------------------------------------------------------------
    def _cl_receivable_domain(self, company):
        self.ensure_one()
        return [
            ('partner_id', 'child_of', self.commercial_partner_id.id),
            ('company_id', '=', company.id),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
        ]

    @api.model
    def _cl_line_label(self, line):
        move = line.move_id
        if move.move_type == 'out_invoice':
            return _("Invoice")
        if move.move_type == 'out_refund':
            return _("Credit Note")
        # a bank line reconciled straight on the receivable account (journals
        # without outstanding accounts) is a payment for the customer too
        if move.origin_payment_id or move.statement_line_id:
            return _("Payment")
        return _("Journal Entry")

    def _cl_open_items(self, company):
        self.ensure_one()
        return self.env['account.move.line'].search(
            self._cl_receivable_domain(company) + [
                ('reconciled', '=', False),
                ('amount_residual', '!=', 0.0),
            ], order='date_maturity, date, id')

    def _cl_ageing(self, company, as_of=None):
        self.ensure_one()
        as_of = as_of or fields.Date.context_today(self)
        ageing = dict.fromkeys([key for key, _label in AGEING_BUCKETS], 0.0)
        for line in self._cl_open_items(company):
            due = line.date_maturity or line.date
            ageing[_bucket((as_of - due).days)] += line.amount_residual
        ageing['total'] = sum(ageing[key] for key, _label in AGEING_BUCKETS)
        ageing['as_of'] = as_of
        return ageing

    def _cl_statement_data(self, company, date_from, date_to):
        """Account statement for [date_from, date_to], in company currency."""
        self.ensure_one()
        AML = self.env['account.move.line']
        domain = self._cl_receivable_domain(company)
        [(opening,)] = AML._read_group(domain + [('date', '<', date_from)], aggregates=['balance:sum'])
        opening = opening or 0.0
        lines = AML.search(
            domain + [('date', '>=', date_from), ('date', '<=', date_to)],
            order='date, move_name, id')
        rows, running = [], opening
        for line in lines:
            running += line.balance
            rows.append({
                'date': line.date,
                'type': self._cl_line_label(line),
                'name': line.move_id.name,
                'ref': line.move_id.ref or (line.name if line.name != line.move_id.name else ''),
                'due': line.date_maturity,
                'debit': line.debit,
                'credit': line.credit,
                'balance': running,
            })
        return {
            'type': 'account',
            'partner': self.commercial_partner_id,
            'company': company,
            'currency': company.currency_id,
            'date_from': date_from,
            'date_to': date_to,
            'opening': opening,
            'rows': rows,
            'total_debit': sum(r['debit'] for r in rows),
            'total_credit': sum(r['credit'] for r in rows),
            'closing': running,
            'ageing': self._cl_ageing(company),
        }

    def _cl_overdue_data(self, company, as_of):
        """Open items past their due date at ``as_of``, in company currency."""
        self.ensure_one()
        rows = []
        for line in self._cl_open_items(company):
            due = line.date_maturity or line.date
            if line.amount_residual <= 0 or due >= as_of:
                continue
            rows.append({
                'date': line.date,
                'type': self._cl_line_label(line),
                'name': line.move_id.name,
                'ref': line.move_id.ref or '',
                'due': due,
                'days': (as_of - due).days,
                'original': line.balance,
                'open': line.amount_residual,
            })
        return {
            'type': 'overdue',
            'partner': self.commercial_partner_id,
            'company': company,
            'currency': company.currency_id,
            'date_to': as_of,
            'rows': rows,
            'total': sum(r['open'] for r in rows),
            'ageing': self._cl_ageing(company, as_of),
        }

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _cl_statement_recipients(self):
        self.ensure_one()
        commercial = self.commercial_partner_id
        recipients = commercial.cl_statement_contact_ids.filtered('email')
        if not recipients and commercial.email:
            recipients = commercial
        return recipients

    def _cl_statement_email_labels(self, statement_type, date_from, date_to):
        """(statement name, period) worded in the language of ``self.env``."""
        selection = self.env['cl.customer.statement.log']._fields['statement_type']
        type_label = dict(selection._description_selection(self.env))[statement_type]
        if statement_type == 'account':
            period = _("%(start)s to %(end)s",
                       start=format_date(self.env, date_from),
                       end=format_date(self.env, date_to))
        else:
            period = _("as of %s", format_date(self.env, date_to))
        return type_label, period

    def _cl_send_statement(self, company, statement_type, date_from, date_to, auto=False):
        """Render the statement PDF, email it as an attachment and log the result."""
        self.ensure_one()
        partner = self.commercial_partner_id
        Log = self.env['cl.customer.statement.log'].sudo()
        log_vals = {
            'partner_id': partner.id,
            'company_id': company.id,
            'statement_type': statement_type,
            'date_from': date_from if statement_type == 'account' else False,
            'date_to': date_to,
            'auto': auto,
        }
        recipients = partner._cl_statement_recipients()
        if not recipients:
            # _message_log: a plain note, also when the user has no email address
            partner._message_log(body=_(
                "Statement not sent: no email address on the customer or its "
                "statement recipients."))
            return Log.create(dict(log_vals, state='failed',
                                   note=_("No recipient with an email address.")))

        data = {
            'company_id': company.id,
            'statement_type': statement_type,
            'date_from': fields.Date.to_string(date_from) if date_from else False,
            'date_to': fields.Date.to_string(date_to),
        }
        pdf, _fmt = self.env['ir.actions.report'].sudo().with_company(company)._render_qweb_pdf(
            REPORT_XMLID, partner.ids, data=data)
        # the customer reads the email: word it in the customer's language
        type_label, period = partner.with_context(
            lang=partner.lang or self.env.lang)._cl_statement_email_labels(
                statement_type, date_from, date_to)
        # Private attachment linked to the customer - never a public file.
        attachment = self.env['ir.attachment'].sudo().create({
            'name': "%s - %s - %s.pdf" % (type_label, partner.name, fields.Date.to_string(date_to)),
            'type': 'binary',
            'raw': pdf,
            'mimetype': 'application/pdf',
            'res_model': 'res.partner',
            'res_id': partner.id,
        })
        template = self.env.ref('cl_customer_statement.mail_template_customer_statement')
        template.sudo().with_company(company).with_context(
            cl_type_label=type_label,
            cl_period=period,
            cl_company_name=company.name,
            cl_email_from=company.email_formatted,
        ).send_mail(partner.id, email_values={
            'recipient_ids': [(6, 0, recipients.ids)],
            'attachment_ids': [(4, attachment.id)],
        })
        emails = ', '.join(recipients.mapped('email'))
        # the note in the chatter is for our own staff: their language
        type_label, period = partner._cl_statement_email_labels(
            statement_type, date_from, date_to)
        partner._message_log(
            body=_("%(type)s (%(period)s) emailed to %(emails)s.",
                   type=type_label, period=period, emails=emails),
            attachment_ids=attachment.ids)
        return Log.create(dict(log_vals, state='sent', note=emails))

    def action_cl_open_statement_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Customer Statement"),
            'res_model': 'cl.customer.statement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_ids': [(6, 0, self.commercial_partner_id.ids)]},
        }

    # ------------------------------------------------------------------
    # Monthly automatic statements
    # ------------------------------------------------------------------
    @api.model
    def _cl_monthly_statement_partners(self, company, period_start, period_end):
        """Customers that still have to get the automatic statement of the
        period, and the failed attempts already logged for it.

        A customer is concerned when it owes (or is owed) something at the end
        of the period or had any movement during it. It is left out when:

        * it opted out, or its statement of the period was already sent;
        * an attempt failed today (one attempt per customer per day);
        * an earlier attempt failed and it still has nobody to email.
        """
        AML = self.env['account.move.line'].sudo()
        Log = self.env['cl.customer.statement.log'].sudo()
        base = [
            ('company_id', '=', company.id),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('parent_state', '=', 'posted'),
            ('partner_id', '!=', False),
        ]
        # Balances are added up per commercial entity: an invoice on the
        # company settled by a payment booked on one of its contacts is zero.
        balances = defaultdict(float)
        for partner, balance in AML._read_group(
                base + [('date', '<=', period_end)], ['partner_id'], ['balance:sum']):
            balances[partner.commercial_partner_id.id] += balance or 0.0
        partner_ids = {
            partner_id for partner_id, balance in balances.items()
            if not company.currency_id.is_zero(balance)}
        for (partner,) in AML._read_group(
                base + [('date', '>=', period_start), ('date', '<=', period_end)],
                ['partner_id']):
            partner_ids.add(partner.commercial_partner_id.id)

        logs = Log.search([
            ('company_id', '=', company.id),
            ('statement_type', '=', 'account'),
            ('auto', '=', True),
            ('date_from', '=', period_start),
        ])
        failed_logs = logs.filtered(lambda log: log.state == 'failed')
        today_start = fields.Datetime.to_datetime(fields.Date.context_today(self))
        waiting = failed_logs.filtered(
            lambda log: log.create_date >= today_start
            or not log.partner_id._cl_statement_recipients())
        skip = (logs - failed_logs).partner_id | waiting.partner_id
        partners = self.sudo().browse(sorted(partner_ids - set(skip.ids))).filtered(
            lambda partner: not partner.cl_statement_opt_out)
        return partners, failed_logs

    def _cl_send_monthly_statement(self, company, period_start, period_end, failed_logs):
        """Send the automatic statement of one customer, on its own savepoint.
        Whatever happens, exactly one log line describes the outcome."""
        self.ensure_one()
        Log = self.env['cl.customer.statement.log'].sudo()
        try:
            with self.env.cr.savepoint():
                log = self._cl_send_statement(
                    company, 'account', period_start, period_end, auto=True)
        except Exception:
            _logger.exception("Monthly statement for %s (%s) failed.",
                              self.display_name, company.name)
            log = Log.create({
                'partner_id': self.id, 'company_id': company.id,
                'statement_type': 'account', 'date_from': period_start,
                'date_to': period_end, 'auto': True, 'state': 'failed',
                'note': _("Error while generating or sending the statement."),
            })
        # the new line replaces what earlier attempts said
        failed_logs.filtered(lambda old: old.partner_id == self).unlink()
        return log

    @api.model
    def _cron_cl_send_monthly_statements(self, batch_size=50):
        """Daily job. From the configured day of the month on, emails last
        month's account statement to the customers of every company that has
        the option on.

        Customers are committed one by one (rendering a PDF takes time, and a
        worker stopped half-way must not start again from the first customer)
        and at most ``batch_size`` are handled per company and run; when more
        are waiting, the scheduler is told and runs the job again right away."""
        today = fields.Date.context_today(self)
        period_end = today.replace(day=1) - timedelta(days=1)
        period_start = period_end.replace(day=1)
        # Never commit inside a test: the test cursor must stay untouched.
        commit = not getattr(threading.current_thread(), 'testing', False)
        done = remaining = 0

        for company in self.env['res.company'].sudo().search([('cl_statement_auto_send', '=', True)]):
            if today.day < (company.cl_statement_send_day or 1):
                continue
            partners, failed_logs = self._cl_monthly_statement_partners(
                company, period_start, period_end)
            for partner in partners[:batch_size]:
                partner._cl_send_monthly_statement(
                    company, period_start, period_end, failed_logs)
                done += 1
                if commit:
                    self.env.cr.commit()
            remaining += max(len(partners) - batch_size, 0)

        self.env['ir.cron']._notify_progress(done=done, remaining=remaining)
