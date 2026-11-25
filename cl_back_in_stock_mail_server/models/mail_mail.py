# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models


class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model_create_multi
    def create(self, vals_list):
        # Set only while product.product._send_availability_email() runs.
        server_id = self.env.context.get('cl_back_in_stock_server_id')
        if server_id:
            for vals in vals_list:
                vals.setdefault('mail_server_id', server_id)
        return super().create(vals_list)
