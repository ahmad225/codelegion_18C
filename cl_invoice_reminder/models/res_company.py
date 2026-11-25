# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_reminder_batch_size = fields.Integer(
        string='Reminder Emails Per Run',
        default=200,
        help="How many customers the reminder job emails in one go. When more "
             "customers are waiting, the job is run again straight away.",
    )
