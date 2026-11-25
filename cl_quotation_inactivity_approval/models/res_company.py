# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_quotation_inactivity_days = fields.Integer(
        string='Quotation Inactivity (days)', default=14,
        help='Quotations with no activity for longer than this need approval before confirmation. '
             '0 switches the check off.')
