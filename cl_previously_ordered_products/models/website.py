# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Website(models.Model):
    _inherit = 'website'

    # The options belong to the website: two shops of the same database can
    # behave differently.
    cl_reorder_orders_scanned = fields.Integer(
        string='Past Orders Looked At', default=20,
        help="How many of the customer's latest confirmed orders are read to "
             "build the Previously Ordered page. 0 hides the page's content.")
    cl_reorder_add_all = fields.Boolean(
        string='Add All to Cart Button', default=True,
        help="Offer a button that puts every listed product in the cart at once.")

    @api.constrains('cl_reorder_orders_scanned')
    def _check_cl_reorder_orders_scanned(self):
        for website in self:
            if website.cl_reorder_orders_scanned < 0:
                raise ValidationError(_(
                    "The number of past orders looked at cannot be negative."))
