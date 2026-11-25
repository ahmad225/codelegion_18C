# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_back_in_stock_mail_server_id = fields.Many2one(
        'ir.mail_server', string='Back-in-Stock Mail Server',
        help="Outgoing mail server used for 'product is back in stock' emails. "
             "Leave empty to use Odoo's normal server selection.")
