# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ClHikDevicePassword(models.TransientModel):
    """Lets Attendance administrators set the device password without ever being able to
    read it (the field on the device is restricted to system administrators)."""
    _name = 'cl.hik.device.password'
    _description = 'Set Hikvision Device Password'

    device_id = fields.Many2one('cl.hik.device', string='Device', required=True, ondelete='cascade')
    password = fields.Char(required=True)

    def action_cl_apply(self):
        self.ensure_one()
        self.device_id._cl_check_manager()
        self.device_id.sudo().write({'password': self.password})
        # Do not leave the password in the wizard table until the transient cleanup.
        self.password = '*'
        return self.device_id.action_cl_test_connection()
