# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, http
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.res_partner import AGEING_BUCKETS, REPORT_XMLID


class ClStatementPortal(CustomerPortal):
    """The logged-in customer's own statement only. Everything is computed
    live with sudo for that one commercial partner - no stored rows and no
    public files."""

    def _cl_dates(self, date_from, date_to):
        today = fields.Date.context_today(request.env.user)
        try:
            end = fields.Date.to_date(date_to) if date_to else today
        except ValueError:
            end = today
        try:
            start = fields.Date.to_date(date_from) if date_from else end.replace(month=1, day=1)
        except ValueError:
            start = end.replace(month=1, day=1)
        if start > end:
            start, end = end, start
        return start, end

    def _cl_partner(self):
        return request.env.user.partner_id.commercial_partner_id.sudo()

    @http.route(['/my/statement'], type='http', auth='user', website=True)
    def cl_portal_statement(self, date_from=None, date_to=None, **kw):
        partner = self._cl_partner()
        company = request.env.company
        start, end = self._cl_dates(date_from, date_to)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'cl_statement',
            'st': partner._cl_statement_data(company, start, end),
            'overdue': partner._cl_overdue_data(company, fields.Date.context_today(request.env.user)),
            'ageing_buckets': AGEING_BUCKETS,
            'date_from': fields.Date.to_string(start),
            'date_to': fields.Date.to_string(end),
        })
        return request.render('cl_customer_statement.portal_my_statement', values)

    @http.route(['/my/statement/pdf'], type='http', auth='user', website=True)
    def cl_portal_statement_pdf(self, statement_type='account', date_from=None, date_to=None, **kw):
        partner = self._cl_partner()
        start, end = self._cl_dates(date_from, date_to)
        if statement_type != 'overdue':
            statement_type = 'account'
        data = {
            'company_id': request.env.company.id,
            'statement_type': statement_type,
            'date_from': fields.Date.to_string(start),
            'date_to': fields.Date.to_string(
                end if statement_type == 'account' else fields.Date.context_today(request.env.user)),
        }
        pdf, _fmt = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            REPORT_XMLID, partner.ids, data=data)
        filename = 'Statement.pdf' if statement_type == 'account' else 'Overdue Statement.pdf'
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', content_disposition(filename)),
        ])
