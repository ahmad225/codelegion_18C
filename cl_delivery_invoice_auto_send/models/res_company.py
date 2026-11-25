# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_send_invoices_when_delivered = fields.Boolean(
        string='Auto-send Invoice on Delivery',
        help="Send the posted customer invoices of a sale order to the "
             "customer automatically once an outgoing delivery of that order "
             "is validated. An invoice posted after the delivery is sent when "
             "it is posted.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_send_invoices_when_delivered = fields.Boolean(
        related='company_id.cl_send_invoices_when_delivered', readonly=False)
