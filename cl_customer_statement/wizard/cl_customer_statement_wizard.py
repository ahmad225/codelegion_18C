# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.cl_customer_statement_log import STATEMENT_TYPES
from ..models.res_partner import REPORT_XMLID


def _default_partners(self):
    if self.env.context.get('active_model') == 'res.partner':
        return self.env['res.partner'].browse(self.env.context.get('active_ids', []))
    return self.env['res.partner']


class ClCustomerStatementWizard(models.TransientModel):
    _name = 'cl.customer.statement.wizard'
    _description = 'Print / Send Customer Statements'

    partner_ids = fields.Many2many(
        'res.partner', string='Customers', required=True, default=_default_partners)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
        # journal items of a company that is not ticked in the company
        # switcher are invisible: the statement would silently come out empty
        domain=lambda self: [('id', 'in', self.env.companies.ids)])
    statement_type = fields.Selection(
        STATEMENT_TYPES, string='Statement', required=True, default='account')
    date_from = fields.Date(
        string='From', default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='To', required=True, default=fields.Date.context_today,
        help="End of the period for an account statement; 'as of' date for an "
             "overdue statement.")

    def _check_dates(self):
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise UserError(_(
                "Select %s in the company switcher to prepare its statements.",
                self.company_id.display_name))
        if self.statement_type == 'account':
            if not self.date_from:
                raise UserError(_("Set the start date of the statement period."))
            if self.date_from > self.date_to:
                raise UserError(_("The start date must be before the end date."))

    def _report_data(self):
        self.ensure_one()
        return {
            # with options the web client sends no record ids to the report
            'partner_ids': self.partner_ids.commercial_partner_id.ids,
            'company_id': self.company_id.id,
            'statement_type': self.statement_type,
            'date_from': fields.Date.to_string(self.date_from) if self.date_from else False,
            'date_to': fields.Date.to_string(self.date_to),
        }

    def action_print(self):
        self.ensure_one()
        self._check_dates()
        partners = self.partner_ids.commercial_partner_id
        return self.env.ref(REPORT_XMLID).report_action(partners, data=self._report_data())

    def action_send(self):
        self.ensure_one()
        self._check_dates()
        sent, failed = 0, []
        for partner in self.partner_ids.commercial_partner_id:
            log = partner._cl_send_statement(
                self.company_id, self.statement_type, self.date_from, self.date_to)
            if log.state == 'sent':
                sent += 1
            else:
                failed.append(partner.display_name)
        message = _("%s statement(s) sent.", sent)
        if failed:
            message += ' ' + _("Not sent (no email address): %s.", ', '.join(failed))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Customer Statements"),
                'message': message,
                'type': 'warning' if failed else 'success',
                'sticky': bool(failed),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
