# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging
import threading
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.sql import column_exists, create_column

_logger = logging.getLogger(__name__)

# A customer invoice that still waits for money.
UNPAID_INVOICE_DOMAIN = [
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('payment_state', 'in', ('not_paid', 'partial')),
]
DEFAULT_BATCH_SIZE = 200


class AccountMove(models.Model):
    _inherit = 'account.move'

    cl_reminder_log_ids = fields.One2many(
        'cl.invoice.reminder.log', 'move_id',
        string='Reminders Sent', readonly=True, copy=False,
        # same audience as the log itself: reading an invoice must not fail
        # for a salesperson who has no access to the reminder log
        groups='account.group_account_invoice,account.group_account_readonly')
    # The three fields below only summarise the lines above.
    cl_reminder_count = fields.Integer(
        string='Reminders',
        compute='_compute_cl_reminder_summary', store=True,
        help="Number of reminder emails sent for this invoice.")
    cl_reminder_stage_id = fields.Many2one(
        'cl.invoice.reminder.stage',
        string='Reminder Stage',
        compute='_compute_cl_reminder_summary', store=True,
        index='btree_not_null',
        help="Strongest reminder sent for this invoice so far.")
    cl_reminder_date = fields.Datetime(
        string='Last Reminder',
        compute='_compute_cl_reminder_summary', store=True,
        help="When the most recent reminder was sent.")
    cl_days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_cl_days_overdue',
        search='_search_cl_days_overdue',
        help="Days since the due date, for posted customer invoices that are "
             "not fully paid. 0 for everything else.")
    cl_reminder_final = fields.Boolean(
        string='Final Reminder Sent',
        compute='_compute_cl_reminder_final',
        search='_search_cl_reminder_final',
        help="The last stage of the company's reminder schedule has been "
             "sent: no further reminder will follow automatically.")

    def _auto_init(self):
        # Invoices that exist before the module is installed have no reminder
        # yet: create the summary columns empty instead of letting the ORM
        # compute them invoice by invoice on a large database.
        for column, column_type in (
                ('cl_reminder_count', 'int4'),
                ('cl_reminder_stage_id', 'int4'),
                ('cl_reminder_date', 'timestamp')):
            if not column_exists(self.env.cr, 'account_move', column):
                create_column(self.env.cr, 'account_move', column, column_type)
        return super()._auto_init()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    @api.depends('cl_reminder_log_ids.sent_date',
                 'cl_reminder_log_ids.stage_id.delay_days')
    def _compute_cl_reminder_summary(self):
        for move in self:
            logs = move.cl_reminder_log_ids
            strongest = max(
                logs, key=lambda log: (log.stage_id.delay_days, log.sent_date),
                default=logs)
            move.cl_reminder_count = len(logs)
            move.cl_reminder_stage_id = strongest.stage_id
            move.cl_reminder_date = max(logs.mapped('sent_date'), default=False)

    @api.depends('invoice_date_due', 'move_type', 'state', 'payment_state')
    def _compute_cl_days_overdue(self):
        today = fields.Date.context_today(self)
        unpaid = self.filtered_domain(UNPAID_INVOICE_DOMAIN)
        for move in unpaid:
            due = move.invoice_date_due
            move.cl_days_overdue = max((today - due).days, 0) if due else 0
        (self - unpaid).cl_days_overdue = 0

    @api.model
    def _cl_last_stage_delays(self, companies):
        """{company id: delay of the last active stage of its schedule}"""
        Stage = self.env['cl.invoice.reminder.stage'].sudo()
        return {
            company.id: delay
            for company, delay in Stage._read_group(
                [('company_id', 'in', companies.ids)],
                ['company_id'], ['delay_days:max'])
        }

    @api.depends('cl_reminder_stage_id', 'company_id')
    def _compute_cl_reminder_final(self):
        last_delay = self._cl_last_stage_delays(self.company_id)
        for move in self:
            stage = move.cl_reminder_stage_id
            move.cl_reminder_final = bool(
                stage and stage.delay_days >= last_delay.get(move.company_id.id, 0))

    def _search_cl_days_overdue(self, operator, value):
        """The search follows the displayed number, including its zeros: a
        paid invoice or a vendor bill is "0 days overdue", never more."""
        if operator not in ('=', '!=', '<', '<=', '>', '>='):
            raise UserError(_(
                "Days Overdue cannot be searched with the operator '%s'.",
                operator))
        try:
            value = int(value or 0)
        except (TypeError, ValueError):
            raise UserError(_("Days Overdue must be compared to a number."))
        today = fields.Date.context_today(self)

        def at_least(days):
            # the invoices that are `days` days overdue or more
            if days <= 0:
                return expression.TRUE_DOMAIN
            return expression.AND([UNPAID_INVOICE_DOMAIN, [
                ('invoice_date_due', '<=', today - timedelta(days=days))]])

        def below(days):
            # everything else: the exact complement of at_least(days)
            if days <= 0:
                return expression.FALSE_DOMAIN
            return expression.OR([
                [('move_type', '!=', 'out_invoice')],
                [('state', '!=', 'posted')],
                [('payment_state', 'not in', ('not_paid', 'partial'))],
                [('invoice_date_due', '=', False)],
                [('invoice_date_due', '>', today - timedelta(days=days))],
            ])

        # Days are whole numbers, so every comparison is a combination of
        # "at least N" and "below N".
        if operator == '>':
            return at_least(value + 1)
        if operator == '>=':
            return at_least(value)
        if operator == '<':
            return below(value)
        if operator == '<=':
            return below(value + 1)
        if operator == '=':
            return expression.AND([at_least(value), below(value + 1)])
        return expression.OR([below(value), at_least(value + 1)])

    def _search_cl_reminder_final(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError(_(
                "Final Reminder Sent can only be searched with '=' or '!='."))
        wanted = bool(value) if operator == '=' else not value
        Stage = self.env['cl.invoice.reminder.stage'].sudo().with_context(
            active_test=False)
        final_stage_ids = []
        for company_id, delay in self._cl_last_stage_delays(
                self.env.companies).items():
            # archived stages that were at least as late count as final too
            final_stage_ids += Stage.search([
                ('company_id', '=', company_id),
                ('delay_days', '>=', delay),
            ]).ids
        return [('cl_reminder_stage_id', 'in' if wanted else 'not in',
                 final_stage_ids)]

    def action_cl_view_reminders(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_invoice_reminder.action_reminder_log')
        action['domain'] = [('move_id', '=', self.id)]
        action['context'] = {}
        return action

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _cl_reminder_recipient(self):
        """Contact the reminder of this invoice is emailed to: the invoice
        contact or, when that contact has no email (typically a plain invoice
        address), the company it belongs to. Empty when neither has one."""
        self.ensure_one()
        for partner in (self.partner_id, self.commercial_partner_id):
            if partner.email:
                return partner
        return self.env['res.partner']

    def _cl_send_reminder(self, stage, recipient):
        """Queue one email to ``recipient`` about all the invoices in ``self``
        and record it on each of them. Call it inside a savepoint, so that the
        email and its records are kept or dropped together."""
        stage.template_id.with_context(
            cl_invoices=self,
            cl_stage=stage,
            cl_company=stage.company_id,
        ).send_mail(recipient.id)
        now = fields.Datetime.now()
        self.env['cl.invoice.reminder.log'].create([{
            'move_id': move.id,
            'stage_id': stage.id,
            'sent_date': now,
            'email': recipient.email,
            'amount_due': move.amount_residual,
            'days_overdue': move.cl_days_overdue,
        } for move in self])

    @api.model
    def _cron_cl_send_invoice_reminders(self):
        """Scheduled job: send the reminders that are due, company by company.

        A company emails at most its batch size of customers per run. When
        customers are left over, the job says so to the scheduler, which runs
        it again right away instead of waiting for the next day."""
        Move = self.sudo()
        done = remaining = 0
        for company, stages in Move.env['cl.invoice.reminder.stage']._read_group(
                [], ['company_id'], ['id:recordset']):
            if not company.active:
                continue
            company_env = Move.with_company(company).env
            sent, left = company_env['account.move']._cl_send_company_reminders(
                stages.with_env(company_env))
            done += sent
            remaining += left
        self.env['ir.cron']._notify_progress(done=done, remaining=remaining)

    @api.model
    def _cl_send_company_reminders(self, stages):
        """Send the due reminders of one company, given its active stages.

        The schedule is walked from its last stage to its first one, and an
        invoice only ever receives a stage later than the one it already got.
        An invoice that is already 40 days overdue when reminders are switched
        on therefore gets the 30-day reminder once, not the 7, 15 and 30-day
        reminders one after the other.

        :return: (customers emailed, customers left for the next run)
        """
        company = stages.company_id
        company.ensure_one()
        today = fields.Date.context_today(self)
        batch_size = company.cl_reminder_batch_size
        if batch_size <= 0:
            batch_size = DEFAULT_BATCH_SIZE
        # Never commit inside a test: the test cursor must stay untouched.
        commit = not getattr(threading.current_thread(), 'testing', False)
        every_stage = stages.with_context(active_test=False).search(
            [('company_id', '=', company.id)])
        sent = remaining = 0
        handled_ids = []

        for stage in stages.sorted('delay_days', reverse=True):
            earlier = every_stage.filtered(
                lambda s: s.delay_days < stage.delay_days)
            invoices = self.search(UNPAID_INVOICE_DOMAIN + [
                ('company_id', '=', company.id),
                ('invoice_date_due', '<=',
                 today - timedelta(days=stage.delay_days)),
                ('id', 'not in', handled_ids),
                '|',
                ('cl_reminder_stage_id', '=', False),
                ('cl_reminder_stage_id', 'in', earlier.ids),
            ], order='invoice_date_due, id')
            # Whatever happens to these invoices below, they are not offered
            # an earlier (milder) stage during the same run.
            handled_ids += invoices.ids

            mailing = defaultdict(self.browse)
            for invoice in invoices:
                recipient = invoice._cl_reminder_recipient()
                if recipient:
                    mailing[recipient] += invoice
                else:
                    # Nothing is recorded, so the invoice is picked up as soon
                    # as the customer gets an email address.
                    _logger.info(
                        "No reminder for invoice %s: %s has no email address.",
                        invoice.name, invoice.partner_id.display_name)

            for recipient, recipient_invoices in mailing.items():
                if sent >= batch_size:
                    remaining += 1
                    continue
                try:
                    with self.env.cr.savepoint():
                        recipient_invoices._cl_send_reminder(stage, recipient)
                except Exception:
                    # The savepoint has undone this customer only; the others
                    # still get their reminder.
                    _logger.exception(
                        "Reminder '%s' could not be sent to %s.",
                        stage.name, recipient.display_name)
                    continue
                sent += 1
                if commit:
                    # Keep what is done, whatever happens to the next customer
                    # or to the worker running the job.
                    self.env.cr.commit()
        return sent, remaining
