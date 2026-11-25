# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_invoice_email_skip_followers = fields.Boolean(
        string='Invoice Emails: Skip Followers',
        help="An invoice sent by email reaches only the recipients listed "
             "when it is sent (the customer, plus anyone added in the Send "
             "window). The followers of the invoice do not get a copy.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_invoice_email_skip_followers = fields.Boolean(
        related='company_id.cl_invoice_email_skip_followers', readonly=False)
