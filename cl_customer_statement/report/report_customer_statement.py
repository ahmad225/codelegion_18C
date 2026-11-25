# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models

from ..models.res_partner import AGEING_BUCKETS


class ReportCustomerStatement(models.AbstractModel):
    _name = 'report.cl_customer_statement.report_customer_statement'
    _description = 'Customer Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        company = (self.env['res.company'].browse(data['company_id'])
                   if data.get('company_id') else self.env.company)
        statement_type = data.get('statement_type') or 'account'
        today = fields.Date.context_today(self)
        date_to = fields.Date.to_date(data['date_to']) if data.get('date_to') else today
        date_from = (fields.Date.to_date(data['date_from']) if data.get('date_from')
                     else date_to.replace(day=1))
        # Printed from the wizard, the web client passes the options only
        # (no ids in the URL): the customers then come with the options.
        partner_ids = docids or data.get('partner_ids') or []
        if not partner_ids and self.env.context.get('active_model') == 'res.partner':
            partner_ids = self.env.context.get('active_ids') or []
        partners = self.env['res.partner'].browse(partner_ids).commercial_partner_id
        statements = []
        for partner in partners:
            # each statement is worded in the language of its customer
            lang = partner.lang or self.env.lang
            partner = partner.with_context(lang=lang)
            if statement_type == 'overdue':
                statement = partner._cl_overdue_data(company, date_to)
            else:
                statement = partner._cl_statement_data(company, date_from, date_to)
            statements.append(dict(statement, lang=lang))
        return {
            'doc_ids': partners.ids,
            'doc_model': 'res.partner',
            'docs': partners,
            'company': company,
            'statements': statements,
            'statement_type': statement_type,
            'ageing_buckets': AGEING_BUCKETS,
        }
