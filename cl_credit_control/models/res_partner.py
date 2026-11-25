# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import formatLang

MANAGER_GROUP_XMLID = 'cl_credit_control.group_cl_credit_manager'
# Customer settings only a Credit Manager may change
CREDIT_SETTING_FIELDS = (
    'cl_credit_hold', 'cl_credit_exempt', 'cl_credit_custom_grace', 'cl_credit_grace_days')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Settings per customer (stored per company, on the commercial entity)
    # ------------------------------------------------------------------
    cl_credit_hold = fields.Boolean(
        string="Credit Hold",
        company_dependent=True, copy=False,
        help="Quotations for this customer cannot be confirmed without a "
             "Credit Manager's approval, whatever the invoices look like.",
    )
    cl_credit_exempt = fields.Boolean(
        string="Exempt from Credit Control",
        company_dependent=True, copy=False,
        help="This customer is never blocked by credit control.",
    )
    cl_credit_custom_grace = fields.Boolean(
        string="Own Overdue Allowance",
        company_dependent=True, copy=False,
        help="Use a specific number of allowed overdue days for this customer "
             "instead of the company setting.",
    )
    cl_credit_grace_days = fields.Integer(
        string="Allowed Overdue Days",
        company_dependent=True, copy=False,
        help="Invoices count against this customer once they are overdue by "
             "more than this number of days.",
    )

    # ------------------------------------------------------------------
    # Live figures for the current company (never stored, so never stale)
    # ------------------------------------------------------------------
    cl_credit_overdue_amount = fields.Monetary(
        string="Overdue Amount",
        compute='_compute_cl_credit_figures',
        currency_field='currency_id',
        help="Unpaid receivable amount that is overdue by more than the allowed days.",
    )
    cl_credit_overdue_days = fields.Integer(
        string="Oldest Overdue (Days)",
        compute='_compute_cl_credit_figures',
        help="Number of days the oldest counted item is past its due date.",
    )
    cl_credit_status = fields.Selection(
        selection=[
            ('ok', "OK"),
            ('overdue', "Overdue Invoices"),
            ('limit', "Over Credit Limit"),
            ('hold', "On Credit Hold"),
            ('exempt', "Exempt"),
        ],
        string="Credit Status",
        compute='_compute_cl_credit_figures',
    )
    cl_credit_has_overdue = fields.Boolean(
        string="Has Overdue Beyond Allowance",
        compute='_compute_cl_credit_figures',
        search='_search_cl_credit_has_overdue',
    )

    # ------------------------------------------------------------------
    # Only Credit Managers change the credit settings of a customer
    # ------------------------------------------------------------------
    def _cl_credit_check_settings_access(self):
        if not (self.env.su or self.env.user.has_group(MANAGER_GROUP_XMLID)):
            raise AccessError(_(
                "Only a Credit Manager can change the credit hold, exemption "
                "and overdue allowance of a customer."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get(name) for vals in vals_list for name in CREDIT_SETTING_FIELDS):
            self._cl_credit_check_settings_access()
        return super().create(vals_list)

    def write(self, vals):
        if any(name in vals for name in CREDIT_SETTING_FIELDS):
            self._cl_credit_check_settings_access()
        return super().write(vals)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _cl_credit_commercial(self, company):
        """Commercial entity of this contact, in the given company, with full
        read access (salespeople may not have accounting rights)."""
        self.ensure_one()
        commercial = self.commercial_partner_id._origin or self._origin
        return commercial.sudo().with_company(company)

    def _cl_credit_allowed_days(self, company):
        """Number of overdue days tolerated for this customer."""
        commercial = self._cl_credit_commercial(company)
        if commercial and commercial.cl_credit_custom_grace:
            return max(commercial.cl_credit_grace_days, 0)
        return max(company.cl_credit_grace_days, 0)

    @api.model
    def _cl_credit_overdue_base_domain(self, company, limit_date):
        """Open receivable items of the company that fell due before limit_date."""
        return [
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('date_maturity', '<', limit_date),
        ]

    def _cl_credit_overdue_lines(self, company):
        """Receivable items of this customer overdue by more than the allowance."""
        self.ensure_one()
        commercial = self._cl_credit_commercial(company)
        MoveLine = self.env['account.move.line'].sudo()
        if not commercial:
            return MoveLine
        limit_date = fields.Date.context_today(self) - timedelta(
            days=self._cl_credit_allowed_days(company))
        domain = self._cl_credit_overdue_base_domain(company, limit_date)
        domain.append(('partner_id', 'child_of', commercial.id))
        return MoveLine.search(domain, order='date_maturity, id')

    def _cl_credit_overdue_summary(self, company):
        """Return (lines, total overdue amount, days the oldest one is overdue)."""
        lines = self._cl_credit_overdue_lines(company)
        if not lines:
            return lines, 0.0, 0
        amount = sum(lines.mapped('amount_residual'))
        days = (fields.Date.context_today(self) - lines[0].date_maturity).days
        return lines, amount, days

    def _cl_credit_evaluate(self, company, extra_amount=0.0):
        """Work out why this customer should be blocked, if at all.

        :param company: the company the order belongs to
        :param float extra_amount: amount of the order being confirmed, in the
            company currency, added to the customer's exposure
        :return: list of dicts with keys ``code`` ('hold', 'overdue' or
            'limit') and ``message``; 'overdue' also carries ``lines``,
            ``amount`` and ``days``. An empty list means: no block.
        """
        self.ensure_one()
        issues = []
        commercial = self._cl_credit_commercial(company)
        if not commercial or commercial.cl_credit_exempt:
            return issues
        currency = company.currency_id

        if commercial.cl_credit_hold:
            issues.append({
                'code': 'hold',
                'message': _("%(customer)s is on credit hold.",
                             customer=commercial.display_name),
            })

        if company.cl_credit_block_overdue:
            lines, amount, days = commercial._cl_credit_overdue_summary(company)
            if lines and currency.compare_amounts(amount, company.cl_credit_min_overdue_amount) > 0:
                issues.append({
                    'code': 'overdue',
                    'message': _(
                        "%(customer)s has %(amount)s overdue by more than %(allowed)s "
                        "day(s). The oldest item is %(days)s day(s) past its due date.",
                        customer=commercial.display_name,
                        amount=formatLang(self.env, amount, currency_obj=currency),
                        allowed=commercial._cl_credit_allowed_days(company),
                        days=days,
                    ),
                    'lines': lines,
                    'amount': amount,
                    'days': days,
                })

        if company.cl_credit_block_limit and company.account_use_credit_limit and commercial.credit_limit:
            exposure = commercial.credit + commercial.credit_to_invoice + extra_amount
            if currency.compare_amounts(exposure, commercial.credit_limit) > 0:
                issues.append({
                    'code': 'limit',
                    'message': _(
                        "%(customer)s would be at %(exposure)s against a credit limit "
                        "of %(limit)s.",
                        customer=commercial.display_name,
                        exposure=formatLang(self.env, exposure, currency_obj=currency),
                        limit=formatLang(self.env, commercial.credit_limit, currency_obj=currency),
                    ),
                })
        return issues

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends_context('company')
    @api.depends('commercial_partner_id', 'cl_credit_hold', 'cl_credit_exempt',
                 'cl_credit_custom_grace', 'cl_credit_grace_days')
    def _compute_cl_credit_figures(self):
        company = self.env.company
        currency = company.currency_id
        for partner in self:
            commercial = partner._cl_credit_commercial(company)
            if not commercial:
                partner.cl_credit_overdue_amount = 0.0
                partner.cl_credit_overdue_days = 0
                partner.cl_credit_has_overdue = False
                partner.cl_credit_status = 'ok'
                continue
            _lines, amount, days = commercial._cl_credit_overdue_summary(company)
            partner.cl_credit_overdue_amount = amount
            partner.cl_credit_overdue_days = days
            partner.cl_credit_has_overdue = currency.compare_amounts(
                amount, company.cl_credit_min_overdue_amount) > 0
            if commercial.cl_credit_exempt:
                partner.cl_credit_status = 'exempt'
                continue
            codes = {issue['code'] for issue in commercial._cl_credit_evaluate(company)}
            if 'hold' in codes:
                partner.cl_credit_status = 'hold'
            elif 'overdue' in codes:
                partner.cl_credit_status = 'overdue'
            elif 'limit' in codes:
                partner.cl_credit_status = 'limit'
            else:
                partner.cl_credit_status = 'ok'

    def _search_cl_credit_has_overdue(self, operator, value):
        """Customers with overdue items beyond the company allowance.

        The search uses the company's allowed overdue days for everyone; a
        customer's own allowance is only applied on the customer form and
        when an order is checked.
        """
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_("This filter can only be used as 'is set' or 'is not set'."))
        company = self.env.company
        limit_date = fields.Date.context_today(self) - timedelta(
            days=max(company.cl_credit_grace_days, 0))
        groups = self.env['account.move.line'].sudo()._read_group(
            self._cl_credit_overdue_base_domain(company, limit_date),
            groupby=['partner_id'],
            aggregates=['amount_residual:sum'],
        )
        totals = defaultdict(float)
        for partner, amount in groups:
            if partner:
                totals[partner.commercial_partner_id.id] += amount
        currency = company.currency_id
        minimum = company.cl_credit_min_overdue_amount
        partner_ids = [
            partner_id for partner_id, amount in totals.items()
            if currency.compare_amounts(amount, minimum) > 0
        ]
        positive = (operator == '=') == value
        return [('id', 'in' if positive else 'not in', partner_ids)]
