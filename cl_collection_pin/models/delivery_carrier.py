# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    cl_is_collection = fields.Boolean(
        string='Customer Collection',
        help="The customer collects the order in store (click & collect). "
             "Orders using this delivery method get a collection PIN, and their "
             "deliveries can only be validated once the customer's PIN is verified.")
