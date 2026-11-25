# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    cl_courier_formula_id = fields.Many2one(
        'cl.courier.formula', string='Courier Cost Formula', ondelete='restrict',
        domain="[('state', '=', 'validated')]",
        help="Internal estimate of what the courier will charge you for a delivery with this method. "
             "It never changes the price charged to the customer.")
