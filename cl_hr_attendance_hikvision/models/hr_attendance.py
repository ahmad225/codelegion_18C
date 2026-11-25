# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError

CL_HIK_USER_FIELDS = ('employee_id', 'check_in', 'check_out')


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Worked hours are deliberately NOT overridden: Odoo's own computation (with the lunch
    # break of the working schedule) applies to these attendances like to any other.
    cl_hik_generated = fields.Boolean(
        string='From Hikvision', readonly=True, copy=False,
        help='Created from Hikvision punches.')
    cl_hik_user_edited = fields.Boolean(
        string='Edited by User', readonly=True, copy=False,
        help='Created from punches, then changed by a user: the sync never touches it again.')
    cl_hik_missing_checkout = fields.Boolean(
        string='Missing Check-Out', readonly=True, copy=False,
        help='No check-out was punched within the maximum shift length: closed with zero hours. '
             'Enter the real check-out time, or it is filled in if the punch still arrives.')
    cl_hik_punch_ids = fields.One2many(
        'cl.hik.punch', 'attendance_id', string='Hikvision Punches', readonly=True,
        groups='hr_attendance.group_hr_attendance_officer')

    def write(self, vals):
        # A change by a real user (not the sync, not the system / scheduled actions) to an
        # attendance created from punches: remember it, the sync will never touch it again.
        user_change = (not self.env.su and not self.env.context.get('cl_hik_engine')
                       and any(name in vals for name in CL_HIK_USER_FIELDS))
        touched = self.filtered(lambda a: a.cl_hik_generated and not a.cl_hik_user_edited) if user_change else self.browse()
        result = super().write(vals)
        if touched:
            flags = {'cl_hik_user_edited': True}
            if 'check_out' in vals:
                flags['cl_hik_missing_checkout'] = False
            super(HrAttendance, touched.sudo()).write(flags)
        return result

    def _cl_hik_is_editable(self):
        """Created by the sync and never changed by a user since."""
        self.ensure_one()
        return self.cl_hik_generated and not self.cl_hik_user_edited

    def _cl_hik_is_provisional(self):
        """Closed without a punched check-out: by the sync (missing check-out) or by Odoo's
        automatic check-out."""
        self.ensure_one()
        return self.cl_hik_missing_checkout or self.out_mode == 'auto_check_out'

    def _cl_hik_engine_write(self, vals):
        self.with_context(cl_hik_engine=True).sudo().write(vals)
        return self

    def _cl_hik_close_missing(self):
        """Close open check-ins created by the sync with zero hours and flag them.

        hr.attendance allows only one open attendance per employee and refuses overlaps, so an
        open check-in cannot stay open once a later punch must become a new check-in.
        check_out = check_in is the only value that invents no worked time."""
        for attendance in self.filtered(lambda a: not a.check_out and a._cl_hik_is_editable()):
            try:
                with self.env.cr.savepoint():
                    attendance._cl_hik_engine_write({'check_out': attendance.check_in,
                                                     'cl_hik_missing_checkout': True})
            except UserError:
                continue

    def _cl_hik_close_stale(self):
        """Scheduled: close the sync's open check-ins older than the maximum shift length."""
        now = fields.Datetime.now()
        open_attendances = self.sudo().search([
            ('cl_hik_generated', '=', True),
            ('cl_hik_user_edited', '=', False),
            ('check_out', '=', False),
        ])
        stale = open_attendances.filtered(lambda a: a.check_in < now - timedelta(
            hours=a.employee_id.company_id.cl_hik_max_shift_hours or 16.0))
        stale._cl_hik_close_missing()
        return stale
