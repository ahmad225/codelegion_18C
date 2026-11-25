# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    cl_handover_collection = fields.Boolean(
        string='Customer Collection',
        help='The customer collects the goods. When the delivery order is ready the '
             'customer gets a "Ready for Collection" email, then reminders until collected.')
