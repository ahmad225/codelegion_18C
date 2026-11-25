# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_promo_auto_apply = fields.Boolean(
        string='Automatic Promotions on Quotations',
        help="Claim the automatic promotions a quotation qualifies for each "
             "time it is created or its lines change.")
    cl_promo_expiry_notice_days = fields.Integer(
        string='Promotion End Notice', default=3,
        help="A quotation shows a notice when a promotion used on it ends "
             "within this many days. 0 only warns on the last day.")

    _sql_constraints = [
        ('cl_promo_expiry_notice_days_positive',
         'CHECK(cl_promo_expiry_notice_days >= 0)',
         "The promotion end notice must be 0 days or more."),
    ]
