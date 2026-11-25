# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_statement_auto_send = fields.Boolean(
        related='company_id.cl_statement_auto_send', readonly=False)
    cl_statement_send_day = fields.Integer(
        related='company_id.cl_statement_send_day', readonly=False)
