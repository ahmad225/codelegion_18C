# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_pin_max_attempts = fields.Integer(
        string='Collection PIN Attempts', default=5,
        help="Number of wrong PIN entries allowed before the collection PIN "
             "is locked. Only an Inventory Administrator can then issue a new PIN.")

    @api.constrains('cl_pin_max_attempts')
    def _check_cl_pin_max_attempts(self):
        for company in self:
            if not 1 <= company.cl_pin_max_attempts <= 99:
                raise ValidationError(_("The number of collection PIN attempts must be between 1 and 99."))
