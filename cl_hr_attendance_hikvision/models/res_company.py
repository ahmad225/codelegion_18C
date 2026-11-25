# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_hik_double_swipe_minutes = fields.Integer(
        string='Hikvision Double-Swipe Threshold (minutes)', default=2,
        help='A punch of the same person within this many minutes of the previous one is ignored. '
             '0 only ignores punches at exactly the same second.')
    cl_hik_max_shift_hours = fields.Float(
        string='Hikvision Maximum Shift Length (hours)', default=16.0,
        help='A punch is taken as the check-out of the open check-in up to this many hours after it, '
             'also across midnight. A check-in left without a check-out for longer is closed as '
             '"Missing Check-Out".')

    @api.constrains('cl_hik_double_swipe_minutes', 'cl_hik_max_shift_hours')
    def _cl_check_hik_pairing_settings(self):
        for company in self:
            if company.cl_hik_double_swipe_minutes < 0:
                raise ValidationError(_('The double-swipe threshold cannot be negative.'))
            if not 1 <= company.cl_hik_max_shift_hours <= 48:
                raise ValidationError(_('The maximum shift length must be between 1 and 48 hours.'))
