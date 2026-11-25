# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_statement_auto_send = fields.Boolean(
        string='Send Monthly Statements',
        help="Email last month's account statement to every customer with an "
             "open balance or activity in that month.")
    cl_statement_send_day = fields.Integer(
        string='Send On Day', default=1,
        help="Day of the month (1-28) from which last month's statements are sent.")

    @api.constrains('cl_statement_send_day')
    def _check_cl_statement_send_day(self):
        for company in self:
            if not 1 <= company.cl_statement_send_day <= 28:
                raise ValidationError(_("The statement send day must be between 1 and 28."))
