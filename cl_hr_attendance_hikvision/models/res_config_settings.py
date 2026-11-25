# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models

from .cl_hik_punch import CL_HIK_RETENTION_DEFAULT, CL_HIK_RETENTION_PARAM

CL_HIK_CRON_XMLID = 'cl_hr_attendance_hikvision.cl_hik_ir_cron_sync'
# Minutes in each interval unit of a scheduled action (a month counted as 30 days).
CL_HIK_UNIT_MINUTES = {'minutes': 1, 'hours': 60, 'days': 1440, 'weeks': 10080, 'months': 43200}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_hik_double_swipe_minutes = fields.Integer(
        related='company_id.cl_hik_double_swipe_minutes', readonly=False)
    cl_hik_max_shift_hours = fields.Float(
        related='company_id.cl_hik_max_shift_hours', readonly=False)
    # Not a plain "config_parameter" field: Odoo removes the parameter of a number set to
    # 0, and the default would come back. 0 (keep for ever) has to be stored as such.
    cl_hik_retention_days = fields.Integer(
        string='Hikvision Punch Retention (days)', default=CL_HIK_RETENTION_DEFAULT,
        help='Downloaded punches older than this are deleted. Attendances are never deleted. 0 = keep forever.')
    # Read from and written to the scheduled action itself, so the setting can never
    # disagree with what actually runs.
    cl_hik_sync_interval = fields.Integer(string='Hikvision Download Interval (minutes)', default=5)

    @api.model
    def _cl_hik_cron_minutes(self, cron):
        return cron.interval_number * CL_HIK_UNIT_MINUTES.get(cron.interval_type, 1)

    @api.model
    def get_values(self):
        res = super().get_values()
        res['cl_hik_retention_days'] = self.env['cl.hik.punch']._cl_retention_days()
        cron = self.env.ref(CL_HIK_CRON_XMLID, raise_if_not_found=False)
        if cron:
            # Whatever unit the scheduled action was given, shown here in minutes.
            res['cl_hik_sync_interval'] = self._cl_hik_cron_minutes(cron.sudo())
        return res

    def set_values(self):
        super().set_values()
        parameters = self.env['ir.config_parameter'].sudo()
        retention = str(max(self.cl_hik_retention_days or 0, 0))
        if parameters.get_param(CL_HIK_RETENTION_PARAM) != retention:
            parameters.set_param(CL_HIK_RETENTION_PARAM, retention)
        cron = self.env.ref(CL_HIK_CRON_XMLID, raise_if_not_found=False)
        if cron:
            interval = max(self.cl_hik_sync_interval or 0, 1)
            cron = cron.sudo()
            # Only when the number of minutes really changes: an interval set in hours or
            # days on the scheduled action itself is left as it is.
            if self._cl_hik_cron_minutes(cron) != interval:
                cron.write({'interval_number': interval, 'interval_type': 'minutes'})
