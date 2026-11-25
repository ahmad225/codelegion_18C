# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class InvoiceReminderLog(models.Model):
    """A reminder that was emailed for an invoice. The invoice derives its
    reminder status from these lines; nothing else is stored about it."""
    _name = 'cl.invoice.reminder.log'
    _description = 'Invoice Reminder Sent'
    _order = 'sent_date desc, id desc'
    _rec_name = 'move_id'

    move_id = fields.Many2one(
        'account.move', string='Invoice',
        required=True, ondelete='cascade', index=True)
    stage_id = fields.Many2one(
        'cl.invoice.reminder.stage', string='Stage',
        required=True, ondelete='restrict', index=True)
    sent_date = fields.Datetime(
        string='Sent On', required=True, default=fields.Datetime.now)
    email = fields.Char(
        string='Sent To', help="Address the reminder was emailed to.")
    # What the customer was told at the time; the invoice itself moves on.
    amount_due = fields.Monetary(string='Amount Due', currency_field='currency_id')
    days_overdue = fields.Integer(string='Days Overdue')
    # Taken from the invoice, stored for the record rule, search and grouping.
    partner_id = fields.Many2one(
        related='move_id.partner_id', string='Customer', store=True, index=True)
    company_id = fields.Many2one(
        related='move_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='move_id.currency_id', store=True)

    _sql_constraints = [
        ('move_stage_uniq', 'unique(move_id, stage_id)',
         "This reminder stage was already sent for this invoice."),
    ]
