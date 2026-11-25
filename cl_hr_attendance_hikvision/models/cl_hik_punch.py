# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import create_index, format_datetime

_logger = logging.getLogger(__name__)

CL_HIK_RETENTION_PARAM = 'cl_hr_attendance_hikvision.retention_days'
CL_HIK_RETENTION_DEFAULT = 365
CL_HIK_CLEANUP_BATCH = 10000


class ClHikPunch(models.Model):
    """One punch read from a device. Raw evidence: nobody edits it (no write/create/unlink
    access for any group), only the module changes its processing result, with sudo."""
    _name = 'cl.hik.punch'
    _description = 'Hikvision Punch'
    _order = 'timestamp desc, id desc'

    device_id = fields.Many2one('cl.hik.device', string='Device', required=True, readonly=True,
                                index=True, ondelete='restrict')
    company_id = fields.Many2one(related='device_id.company_id', store=True, index=True)
    hik_user_id = fields.Char(string='Device User ID', required=True, readonly=True, index=True,
                              help='Employee No. of the person on the device.')
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True, ondelete='set null')
    timestamp = fields.Datetime(string='Punch Time', required=True, readonly=True)
    raw_type = fields.Char(string='Event Type', readonly=True,
                           help='ISAPI major/minor event code, verification mode and attendance status '
                                'as sent by the device.')
    serial_no = fields.Integer(string='Event Serial', readonly=True)
    dedupe_key = fields.Char(required=True, readonly=True)
    state = fields.Selection(
        [('new', 'To Process'),
         ('processed', 'Processed'),
         ('duplicate', 'Double Swipe'),
         ('unmapped', 'Not Mapped'),
         ('review', 'To Review')],
        string='Result', required=True, readonly=True, default='new', index=True)
    role = fields.Selection([('check_in', 'Check-In'), ('check_out', 'Check-Out')], readonly=True)
    attendance_id = fields.Many2one('hr.attendance', string='Attendance', readonly=True,
                                    index='btree_not_null', ondelete='set null')
    note = fields.Char(readonly=True)

    _sql_constraints = [
        ('cl_hik_punch_device_key_uniq', 'unique (device_id, dedupe_key)',
         'This punch was already downloaded from this device.'),
    ]

    def init(self):
        super().init()
        create_index(self.env.cr, indexname='cl_hik_punch_employee_timestamp_idx',
                     tablename=self._table, expressions=['employee_id', 'timestamp'])
        create_index(self.env.cr, indexname='cl_hik_punch_device_serial_idx',
                     tablename=self._table, expressions=['device_id', 'serial_no'])

    @api.depends('employee_id', 'hik_user_id', 'timestamp')
    def _compute_display_name(self):
        for punch in self:
            who = punch.employee_id.name or punch.hik_user_id or ''
            when = format_datetime(self.env, punch.timestamp, dt_format=False) if punch.timestamp else ''
            punch.display_name = ' - '.join(filter(None, [who, when]))

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_cl_retry(self):
        """Process again punches set to review or not mapped (after HR fixed the cause)."""
        if not self.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
            raise AccessError(_('Only Attendance administrators can process punches again.'))
        self.check_access('read')
        punches = self.sudo().filtered(lambda p: p.state in ('review', 'unmapped'))
        with_employee = punches.filtered('employee_id')
        with_employee.write({'state': 'new', 'note': False})
        (punches - with_employee)._cl_map_employees()
        self._cl_process_pending(employees=punches.employee_id)
        done = punches.filtered(lambda p: p.state == 'processed')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Process Again'),
                'message': _('%(done)s of %(total)s punch(es) processed.', done=len(done), total=len(punches)),
                'type': 'success' if len(done) == len(punches) else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _cl_map_employees(self):
        """Give unmapped punches the employee that now has their device user ID (looked up
        at this moment, never cached). Returns the punches that found an employee."""
        mapped = self.browse()
        by_company = defaultdict(lambda: self.browse())
        for punch in self.filtered(lambda p: p.state == 'unmapped'):
            by_company[punch.company_id] |= punch
        for company, punches in by_company.items():
            employees = self.env['hr.employee'].sudo().search([
                ('company_id', '=', company.id),
                ('cl_hik_user_id', 'in', list(set(punches.mapped('hik_user_id')))),
            ])
            for employee in employees:
                found = punches.filtered(lambda p: p.hik_user_id == employee.cl_hik_user_id)
                found.write({'employee_id': employee.id, 'state': 'new', 'note': False})
                mapped |= found
        return mapped

    # ------------------------------------------------------------------
    # Pairing engine
    # ------------------------------------------------------------------

    @api.model
    def _cl_process_pending(self, devices=None, employees=None):
        """Turn every waiting punch of the concerned employees into attendances. All waiting
        punches of an employee are taken together, whatever device they come from, so the
        employee's punches are always paired in time order."""
        domain = [('state', '=', 'new'), ('employee_id', '!=', False)]
        if devices is not None:
            domain.append(('device_id', 'in', devices.ids))
        if employees is not None:
            domain.append(('employee_id', 'in', employees.ids))
        concerned = self.sudo().search(domain).employee_id
        if not concerned:
            return
        self.sudo().search([('state', '=', 'new'), ('employee_id', 'in', concerned.ids)])._cl_process()

    def _cl_process(self):
        punches = self.sudo().filtered(lambda p: p.state == 'new' and p.employee_id)
        by_employee = defaultdict(list)
        for punch in punches:
            by_employee[punch.employee_id].append(punch)
        for employee, employee_punches in by_employee.items():
            ordered = punches.browse([p.id for p in sorted(employee_punches, key=lambda p: (p.timestamp, p.id))])
            try:
                with self.env.cr.savepoint():
                    ordered._cl_pair_employee(employee)
            except Exception as error:  # one employee's problem never blocks the others
                _logger.exception('Hikvision: pairing the punches of employee %s failed', employee.id)
                ordered.filtered(lambda p: p.state == 'new').write({
                    'state': 'review',
                    'note': _('Could not be processed: %s', error)[:250],
                })

    def _cl_pair_employee(self, employee):
        """Pair the punches in self (one employee, chronological order) with the employee's
        existing attendances. Only creates attendances, or completes those it created itself
        and nobody edited; anything else is left alone and the punch goes to review."""
        company = employee.company_id
        threshold = timedelta(minutes=max(company.cl_hik_double_swipe_minutes or 0, 0))
        max_shift = timedelta(hours=company.cl_hik_max_shift_hours or 16.0)
        tz = employee._get_tz()
        kept = self._cl_skip_double_swipes(employee, threshold)
        Attendance = self.env['hr.attendance'].sudo().with_context(cl_hik_engine=True)
        now = fields.Datetime.now()

        def when(moment):
            return format_datetime(self.env, moment, tz=tz, dt_format=False)

        index = 0
        while index < len(kept):
            punch = kept[index]
            moment = punch.timestamp
            following_punch = kept[index + 1] if index + 1 < len(kept) else None
            last = Attendance.search([('employee_id', '=', employee.id), ('check_in', '<=', moment)],
                                     order='check_in desc, id desc', limit=1)
            following = Attendance.search([('employee_id', '=', employee.id), ('check_in', '>', moment)],
                                          order='check_in asc, id asc', limit=1)
            ours = bool(last) and last._cl_hik_is_editable()

            # 0. The punch that made this check-in or check-out, downloaded again after its
            #    record was removed by the retention clean-up: it is already booked.
            if last and last.cl_hik_generated and moment in (last.check_in, last.check_out):
                punch.write({
                    'state': 'processed',
                    'role': 'check_in' if moment == last.check_in else 'check_out',
                    'attendance_id': last.id,
                    'note': _('Already booked on this attendance (downloaded again).'),
                })
                index += 1
                continue

            # 1. The check-out of a check-in that was closed provisionally (missing check-out,
            #    or Odoo's automatic check-out) arrives later: put the real time in.
            if (ours and last.check_out and last._cl_hik_is_provisional()
                    and last.check_in < moment <= last.check_in + max_shift
                    and (not following or moment <= following.check_in)):
                self._cl_apply([(punch, 'check_out')], lambda: last._cl_hik_engine_write({
                    'check_out': moment, 'cl_hik_missing_checkout': False, 'out_mode': 'manual'}))
                index += 1
                continue

            # 2. The employee is checked in.
            if last and not last.check_out:
                if not ours:
                    punch._cl_set_review(_('The employee has an open attendance since %s that was not created '
                                           'from the device (or was edited): close it first.', when(last.check_in)))
                    index += 1
                    continue
                if moment - last.check_in <= max_shift:
                    self._cl_apply([(punch, 'check_out')],
                                   lambda: last._cl_hik_engine_write({'check_out': moment}))
                    index += 1
                    continue
                # Too long ago to be the same shift: the check-out was never punched.
                last._cl_hik_close_missing()
            elif last and last.check_out > moment:
                punch._cl_set_review(_('The punch falls inside the attendance %(start)s - %(end)s.',
                                       start=when(last.check_in), end=when(last.check_out)))
                index += 1
                continue

            # 3. A check-in.
            bound = following.check_in if following else None
            if following_punch and following_punch.timestamp - moment <= max_shift:
                if bound and following_punch.timestamp > bound:
                    (punch | following_punch)._cl_set_review(_(
                        'Another attendance starts at %s, between this check-in and its check-out.', when(bound)))
                    index += 2
                    continue
                vals = {'employee_id': employee.id, 'check_in': moment,
                        'check_out': following_punch.timestamp, 'cl_hik_generated': True}
                self._cl_apply([(punch, 'check_in'), (following_punch, 'check_out')],
                               lambda: Attendance.create(vals))
                index += 2
                continue
            vals = {'employee_id': employee.id, 'check_in': moment, 'cl_hik_generated': True}
            if bound or following_punch or now - moment > max_shift:
                # No check-out within the maximum shift length: closed with zero hours, flagged.
                vals.update(check_out=moment, cl_hik_missing_checkout=True)
            self._cl_apply([(punch, 'check_in')], lambda: Attendance.create(vals))
            index += 1

    def _cl_skip_double_swipes(self, employee, threshold):
        """Mark punches within the threshold of an accepted punch of the same employee (or at
        exactly the same second) as double swipes. Returns the punches to pair, in order."""
        kept = []
        if not self:
            return kept
        accepted = self.search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('processed', 'review')),
            ('timestamp', '>=', self[0].timestamp - threshold),
            ('timestamp', '<=', self[-1].timestamp + threshold),
            ('id', 'not in', self.ids),
        ]).mapped('timestamp')
        for punch in self:
            references = accepted + ([kept[-1].timestamp] if kept else [])
            if any(punch.timestamp == ref or abs(punch.timestamp - ref) < threshold for ref in references):
                punch.write({'state': 'duplicate', 'role': False, 'attendance_id': False,
                             'note': _('Double swipe: within %s minute(s) of another punch.',
                                       int(threshold.total_seconds() // 60))})
            else:
                kept.append(punch)
        return kept

    def _cl_apply(self, assignments, operation):
        """Run one attendance change in its own savepoint (operation is called at once and
        returns the attendance). If Odoo refuses it (overlap, other open attendance...), only
        these punches go to review, with Odoo's message."""
        try:
            with self.env.cr.savepoint():
                attendance = operation()
        except UserError as error:  # ValidationError and AccessError included
            for punch, _role in assignments:
                punch._cl_set_review(str(error.args[0] if error.args else error))
            return False
        for punch, role in assignments:
            punch.write({'state': 'processed', 'role': role, 'attendance_id': attendance.id, 'note': False})
        return attendance

    def _cl_set_review(self, note):
        self.write({'state': 'review', 'role': False, 'attendance_id': False, 'note': (note or '')[:250]})

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    @api.model
    def _cl_retention_days(self):
        """Days downloaded punches are kept; 0 keeps them for ever."""
        value = self.env['ir.config_parameter'].sudo().get_param(CL_HIK_RETENTION_PARAM)
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return CL_HIK_RETENTION_DEFAULT

    @api.model
    def _cl_cleanup(self):
        days = self._cl_retention_days()
        if days <= 0:
            return 0
        limit = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('timestamp', '<', limit), ('state', '!=', 'new')], limit=CL_HIK_CLEANUP_BATCH)
        count = len(old)
        old.unlink()
        return count
