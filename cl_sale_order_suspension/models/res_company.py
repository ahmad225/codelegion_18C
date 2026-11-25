# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_suspension_followup_days = fields.Integer(
        string='Suspension Follow-up (days)', default=1,
        help='Default number of days before the follow-up activity of a suspended quotation is due.')
