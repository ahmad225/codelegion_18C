# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_credit_block_overdue = fields.Boolean(
        string="Block Orders for Overdue Invoices",
        help="Quotations cannot be confirmed without approval when the customer "
             "has invoices overdue by more than the allowed number of days.",
    )
    cl_credit_grace_days = fields.Integer(
        string="Allowed Overdue Days",
        default=30,
        help="An invoice counts against the customer once it is overdue by more "
             "than this number of days. 0 means from the day after the due date.",
    )
    cl_credit_min_overdue_amount = fields.Monetary(
        string="Ignore Overdue Up To",
        currency_field='currency_id',
        help="The customer is only blocked when the total overdue amount is "
             "higher than this. Use it to ignore small leftovers.",
    )
    cl_credit_block_limit = fields.Boolean(
        string="Block Orders Over the Credit Limit",
        help="Quotations cannot be confirmed without approval when the order "
             "would take the customer over the credit limit. Needs Odoo's "
             "'Sales Credit Limit' setting, which is switched on automatically.",
    )
    cl_credit_skip_automatic = fields.Boolean(
        string="Let Automatic Confirmations Through",
        default=True,
        help="Orders confirmed by the system (online payment, customer signature, "
             "other automations) are confirmed even if the customer is blocked, "
             "and a note is logged on the order. Untick to block those too.",
    )

    @api.constrains('cl_credit_grace_days', 'cl_credit_min_overdue_amount')
    def _check_cl_credit_settings(self):
        for company in self:
            if company.cl_credit_grace_days < 0:
                raise ValidationError(_("Allowed Overdue Days cannot be negative."))
            if company.cl_credit_min_overdue_amount < 0:
                raise ValidationError(_("'Ignore Overdue Up To' cannot be negative."))
