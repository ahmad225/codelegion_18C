# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

STATEMENT_TYPES = [
    ('account', 'Account Statement'),
    ('overdue', 'Overdue Statement'),
]


class ClCustomerStatementLog(models.Model):
    """One line per statement sent (or that could not be sent)."""
    _name = 'cl.customer.statement.log'
    _description = 'Customer Statement Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    statement_type = fields.Selection(STATEMENT_TYPES, string='Statement', required=True)
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To / As Of')
    auto = fields.Boolean(string='Automatic')
    state = fields.Selection(
        [('sent', 'Sent'), ('failed', 'Not Sent')], string='Status', required=True)
    note = fields.Char(string='Details')
    user_id = fields.Many2one(
        'res.users', string='Sent By', default=lambda self: self.env.user)
