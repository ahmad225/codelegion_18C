# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import datetime, timedelta
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.cl_hr_attendance_hikvision.models.cl_hik_device import ClHikError

DEVICE_MODULE = 'odoo.addons.cl_hr_attendance_hikvision.models.cl_hik_device'


class FakeHikDevice:
    """Plays a Hikvision terminal: answers deviceInfo, time and the paged AcsEvent search.
    Replaces the module's HTTP helper, so no test ever touches the network."""

    def __init__(self):
        self.events = []
        self.searches = []
        self.page_size = 2
        self.fail_on_search = None
        self.serial = 0

    def add(self, user_id, moment, tz='UTC'):
        """Add a punch at moment (naive UTC), sent in the device time zone with its offset."""
        self.serial += 1
        local = pytz.utc.localize(moment).astimezone(pytz.timezone(tz))
        event = {
            'major': 5, 'minor': 75, 'time': local.isoformat(timespec='seconds'),
            'employeeNoString': user_id, 'serialNo': self.serial,
            'currentVerifyMode': 'face', 'attendanceStatus': 'undefined',
        }
        self.events.append(event)
        return event

    def request(self, device, method, path, payload=None):
        if path.startswith('/ISAPI/System/deviceInfo'):
            return {'DeviceInfo': {'deviceName': 'Entrance', 'model': 'DS-K1T341', 'serialNumber': 'SN0001',
                                   'firmwareVersion': 'V3.2.30'}}
        if path.startswith('/ISAPI/System/time'):
            local = pytz.utc.localize(fields.Datetime.now()).astimezone(pytz.timezone(device.tz))
            return {'Time': {'timeMode': 'NTP', 'localTime': local.isoformat(timespec='seconds')}}
        if path.startswith('/ISAPI/AccessControl/AcsEvent'):
            cond = payload['AcsEventCond']
            self.searches.append(cond)
            if self.fail_on_search and len(self.searches) == self.fail_on_search:
                raise ClHikError('Cannot reach the device at https://10.0.0.5:443: timed out')
            start = datetime.fromisoformat(cond['startTime'])
            end = datetime.fromisoformat(cond['endTime'])
            matches = sorted((event for event in self.events
                              if start <= datetime.fromisoformat(event['time']) <= end),
                             key=lambda event: datetime.fromisoformat(event['time']))
            answer = {'searchID': cond['searchID'], 'totalMatches': len(matches)}
            if not matches:
                answer.update(responseStatusStrg='NO MATCH', numOfMatches=0)
                return {'AcsEvent': answer}
            position = cond['searchResultPosition']
            page = matches[position:position + min(cond['maxResults'], self.page_size)]
            answer.update(InfoList=page, numOfMatches=len(page),
                          responseStatusStrg='MORE' if position + len(page) < len(matches) else 'OK')
            return {'AcsEvent': answer}
        raise AssertionError('Unexpected ISAPI call %s %s' % (method, path))


@tagged('post_install', '-at_install')
class TestHikvisionSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'cl_hik_double_swipe_minutes': 2, 'cl_hik_max_shift_hours': 16})
        cls.now = fields.Datetime.now()
        # Midnight UTC three days ago: every test punch is in the past.
        cls.base = (cls.now - timedelta(days=3)).replace(hour=0, minute=0, second=0)
        cls.device = cls.env['cl.hik.device'].create({
            'name': 'Main Entrance',
            'host': '10.0.0.5',
            'port': 443,
            'username': 'admin',
            'password': 'device-secret',
            'tz': 'UTC',
            'company_id': cls.company.id,
            'sync_from': cls.base - timedelta(hours=1),
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Ayesha Khan', 'cl_hik_user_id': '101', 'company_id': cls.company.id})
        group_user = cls.env.ref('base.group_user')
        cls.officer = cls.env['res.users'].create({
            'name': 'HR Officer', 'login': 'cl_hik_officer',
            'groups_id': [(6, 0, [group_user.id, cls.env.ref('hr.group_hr_user').id,
                                  cls.env.ref('hr_attendance.group_hr_attendance_officer').id])]})
        cls.att_manager = cls.env['res.users'].create({
            'name': 'Attendance Admin', 'login': 'cl_hik_att_admin',
            'groups_id': [(6, 0, [group_user.id, cls.env.ref('hr_attendance.group_hr_attendance_manager').id])]})

    def setUp(self):
        super().setUp()
        self.fake = FakeHikDevice()
        fake = self.fake
        patcher = patch.object(
            type(self.env['cl.hik.device']), '_cl_isapi_request',
            new=lambda device, method, path, payload=None: fake.request(device, method, path, payload))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _at(self, hours, seconds=0):
        return self.base + timedelta(hours=hours, seconds=seconds)

    def _punches(self, device=None):
        return self.env['cl.hik.punch'].search([('device_id', '=', (device or self.device).id)], order='timestamp, id')

    def _attendances(self, employee=None):
        return self.env['hr.attendance'].search([('employee_id', '=', (employee or self.employee).id)],
                                                order='check_in')

    def _redownload(self):
        """Start the next download again from 'First Download From'."""
        self.device.downloaded_until = False

    # ------------------------------------------------------------------

    def test_incremental_sync_stores_punches_and_moves_watermark(self):
        self.device.tz = 'Asia/Karachi'
        self.fake.add('101', self._at(8), tz='Asia/Karachi')
        self.fake.add('999', self._at(9), tz='Asia/Karachi')
        self.fake.add('101', self._at(17), tz='Asia/Karachi')

        self.device.action_cl_sync_now()

        punches = self._punches()
        self.assertEqual(len(punches), 3)
        # 13:00 in Karachi (+05:00) is stored as 08:00 UTC.
        self.assertEqual(punches[0].timestamp, self._at(8))
        self.assertEqual(punches.mapped('state'), ['processed', 'unmapped', 'processed'])
        self.assertTrue(self.fake.searches[0]['startTime'].endswith('+05:00'))
        # The busy day needed two pages of the same search.
        self.assertEqual([cond['searchResultPosition'] for cond in self.fake.searches[:2]], [0, 2])
        self.assertEqual(self.fake.searches[0]['searchID'], self.fake.searches[1]['searchID'])
        self.assertEqual(self.device.state, 'connected')
        self.assertTrue(self.device.last_sync_ok)
        watermark = self.device.downloaded_until
        self.assertGreaterEqual(watermark, self.now)

        attendance = self._attendances()
        self.assertEqual(len(attendance), 1)
        self.assertEqual((attendance.check_in, attendance.check_out), (self._at(8), self._at(17)))
        self.assertTrue(attendance.cl_hik_generated)

        # Next run starts at the watermark minus the overlap and only stores the new punch.
        self.fake.searches.clear()
        self.fake.add('101', watermark - timedelta(minutes=5), tz='Asia/Karachi')
        self.device.action_cl_sync_now()
        expected_start = pytz.utc.localize(watermark - timedelta(minutes=10)).astimezone(
            pytz.timezone('Asia/Karachi')).isoformat(timespec='seconds')
        self.assertEqual(self.fake.searches[0]['startTime'], expected_start)
        self.assertEqual(len(self._punches()), 4)
        self.assertGreaterEqual(self.device.downloaded_until, watermark)

    def test_empty_window_does_not_stop_later_pages_or_syncs(self):
        # Only the last day has punches: the empty days before must not stop the download.
        self.fake.add('101', self.now - timedelta(hours=3))
        self.device.action_cl_sync_now()
        self.assertEqual(len(self._punches()), 1)
        self.assertGreater(len(self.fake.searches), 2, 'every day of the period is searched')

        # A run with nothing new still succeeds and moves the download point.
        first_watermark = self.device.downloaded_until
        self.env['cl.hik.device']._cl_cron_sync()
        self.assertEqual(self.device.state, 'connected')
        self.assertGreaterEqual(self.device.downloaded_until, first_watermark)

        # A punch arriving after the empty run is still downloaded.
        self.fake.add('101', self.device.downloaded_until - timedelta(minutes=2))
        self.env['cl.hik.device']._cl_cron_sync()
        self.assertEqual(len(self._punches()), 2)

    def test_duplicate_download_is_ignored(self):
        event = self.fake.add('101', self._at(8))
        self.fake.events.append(dict(event))  # the device sends the same event twice
        self.fake.add('101', self._at(17))
        self.device.action_cl_sync_now()
        self.assertEqual(len(self._punches()), 2)

        self._redownload()
        self.env['cl.hik.device']._cl_cron_sync()
        self.assertEqual(len(self._punches()), 2)
        self.assertEqual(len(self._attendances()), 1)

    def test_connection_error_keeps_watermark_and_sets_error(self):
        watermark = self._at(24)
        self.device.downloaded_until = watermark
        self.device.flush_recordset()
        for hours in (26, 27, 28):
            self.fake.add('101', self._at(hours))
        self.fake.fail_on_search = 2  # second page of the first day

        result = self.device.action_cl_sync_now()

        self.assertEqual(result['params']['type'], 'danger')
        self.assertEqual(self.device.state, 'error')
        self.assertIn('Cannot reach', self.device.last_error)
        self.assertEqual(self.device.downloaded_until, watermark)
        self.assertFalse(self._punches(), 'the half-read page is rolled back, nothing is half-stored')

        self.fake.fail_on_search = None
        self.device.action_cl_sync_now()
        self.assertEqual(self.device.state, 'connected')
        self.assertEqual(len(self._punches()), 3)

    def test_unmapped_punches_become_attendances_when_id_is_set(self):
        self.fake.add('202', self._at(8))
        self.fake.add('202', self._at(16))
        self.device.action_cl_sync_now()
        punches = self._punches()
        self.assertEqual(punches.mapped('state'), ['unmapped', 'unmapped'])

        employee = self.env['hr.employee'].create({'name': 'Bilal Ahmed', 'company_id': self.company.id})
        employee.with_user(self.officer).write({'cl_hik_user_id': ' 202 '})

        self.assertEqual(employee.cl_hik_user_id, '202')
        self.assertEqual(punches.mapped('state'), ['processed', 'processed'])
        attendance = self._attendances(employee)
        self.assertEqual((attendance.check_in, attendance.check_out), (self._at(8), self._at(16)))

    def test_double_swipe_is_ignored(self):
        self.fake.add('101', self._at(8))
        self.fake.add('101', self._at(8, seconds=40))
        self.fake.add('101', self._at(17))
        self.device.action_cl_sync_now()
        self.assertEqual(self._punches().mapped('state'), ['processed', 'duplicate', 'processed'])
        attendance = self._attendances()
        self.assertEqual(len(attendance), 1)
        self.assertEqual((attendance.check_in, attendance.check_out), (self._at(8), self._at(17)))

    def test_night_shift_across_midnight(self):
        for hours in (22, 30, 46, 54):  # 22:00 -> 06:00 next day, twice
            self.fake.add('101', self._at(hours))
        self.device.action_cl_sync_now()
        attendances = self._attendances()
        self.assertEqual([(a.check_in, a.check_out) for a in attendances],
                         [(self._at(22), self._at(30)), (self._at(46), self._at(54))])
        self.assertFalse(any(attendances.mapped('cl_hik_missing_checkout')))

    def test_missing_checkout_then_late_checkout_fills_it(self):
        self.fake.add('101', self._at(8))
        self.device.action_cl_sync_now()
        attendance = self._attendances()
        self.assertEqual(attendance.check_out, attendance.check_in)
        self.assertTrue(attendance.cl_hik_missing_checkout)

        # The device was offline; its check-out punch arrives later.
        self.fake.add('101', self._at(17))
        self._redownload()
        self.device.action_cl_sync_now()
        self.assertEqual(len(self._attendances()), 1)
        self.assertEqual(attendance.check_out, self._at(17))
        self.assertFalse(attendance.cl_hik_missing_checkout)

    def test_manual_attendance_is_never_modified(self):
        manual = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': self._at(8), 'check_out': self._at(12)})
        for hours in (9, 13, 17):
            self.fake.add('101', self._at(hours))
        self.device.action_cl_sync_now()

        self.assertEqual((manual.check_in, manual.check_out), (self._at(8), self._at(12)))
        self.assertFalse(manual.cl_hik_generated)
        punches = self._punches()
        self.assertEqual(punches.mapped('state'), ['review', 'processed', 'processed'])
        generated = self._attendances() - manual
        self.assertEqual((generated.check_in, generated.check_out), (self._at(13), self._at(17)))

        # HR corrects the generated attendance: the sync never touches it again.
        generated.with_user(self.att_manager).write({'check_out': self._at(18)})
        self.assertTrue(generated.cl_hik_user_edited)
        for hours in (17.5, 19, 20):
            self.fake.add('101', self._at(hours))
        self._redownload()
        self.device.action_cl_sync_now()
        self.assertEqual((manual.check_in, manual.check_out), (self._at(8), self._at(12)))
        self.assertEqual((generated.check_in, generated.check_out), (self._at(13), self._at(18)))
        self.assertEqual(len(self._attendances()), 3)
        self.assertEqual(self._punches().filtered(lambda p: p.timestamp == self._at(17.5)).state, 'review')

    def test_officer_cannot_read_device_password(self):
        device_as_officer = self.device.with_user(self.officer)
        self.assertEqual(device_as_officer.read(['name'])[0]['name'], 'Main Entrance')
        with self.assertRaises(AccessError):
            device_as_officer.read(['password'])
        with self.assertRaises(AccessError):
            device_as_officer.action_cl_sync_now()
        with self.assertRaises(AccessError):
            self.env['cl.hik.punch'].with_user(self.officer).create({
                'device_id': self.device.id, 'hik_user_id': '101', 'timestamp': self._at(8), 'dedupe_key': 'x'})

        # The Attendance administrator runs syncs and sets the password, but cannot read it.
        device_as_manager = self.device.with_user(self.att_manager)
        with self.assertRaises(AccessError):
            device_as_manager.read(['password'])
        self.fake.add('101', self._at(8))
        result = device_as_manager.action_cl_sync_now()
        self.assertEqual(result['params']['type'], 'success')
        wizard = self.env['cl.hik.device.password'].with_user(self.att_manager).create({
            'device_id': self.device.id, 'password': 'new-secret'})
        wizard.action_cl_apply()
        self.assertEqual(self.device.sudo().password, 'new-secret')
        self.assertEqual(self.device.state, 'connected')
        self.assertEqual(self.device.device_serial, 'SN0001')

    def test_long_backlog_is_spread_over_several_runs(self):
        for day in range(3):
            self.fake.add('101', self._at(8 + 24 * day))
        # No time left after the first period: one run reads exactly one period.
        with patch(DEVICE_MODULE + '.CL_HIK_RUN_SECONDS', 0):
            result = self.device.action_cl_sync_now()
            self.assertEqual(len(self.fake.searches), 1)
            self.assertEqual(len(self._punches()), 1)
            self.assertEqual(self.device.state, 'connected')
            self.assertLess(self.device.downloaded_until, self.now)
            self.assertIn('next sync', result['params']['message'])
            # Each later run goes on where the previous one stopped.
            for _run in range(6):
                self.env['cl.hik.device']._cl_cron_sync()
        self.assertEqual(len(self._punches()), 3)
        self.assertGreaterEqual(self.device.downloaded_until, self.now)

    def test_unreadable_punch_time_is_skipped(self):
        good = self.fake.add('101', self._at(8))
        bad = dict(good, serialNo=99, time='yesterday at eight')
        with self.assertLogs(DEVICE_MODULE, level='WARNING'):
            created = self.device._cl_store_events([bad, good], set())
        self.assertEqual(created, 1, 'one unreadable punch does not block the others')
        self.assertEqual(self._punches().timestamp, self._at(8))

    def test_redownload_after_cleanup_books_nothing_twice(self):
        self.fake.add('101', self._at(8))
        self.fake.add('101', self._at(17))
        self.device.action_cl_sync_now()
        attendance = self._attendances()
        self.assertEqual(len(attendance), 1)

        # The retention clean-up removed the punches; the period is downloaded again.
        self._punches().unlink()
        self._redownload()
        self.device.action_cl_sync_now()

        punches = self._punches()
        self.assertEqual(punches.mapped('state'), ['processed', 'processed'])
        self.assertEqual(punches.mapped('role'), ['check_in', 'check_out'])
        self.assertEqual(punches.attendance_id, attendance)
        self.assertEqual(self._attendances(), attendance, 'no second attendance is created')
        self.assertEqual((attendance.check_in, attendance.check_out), (self._at(8), self._at(17)))
        self.assertFalse(attendance.cl_hik_missing_checkout)

    def test_retention_zero_keeps_punches_for_ever(self):
        Punch = self.env['cl.hik.punch']
        Settings = self.env['res.config.settings']
        old = Punch.create({
            'device_id': self.device.id, 'hik_user_id': '101', 'dedupe_key': 'old-punch',
            'timestamp': self.now - timedelta(days=400), 'state': 'processed'})
        waiting = Punch.create({
            'device_id': self.device.id, 'hik_user_id': '999', 'dedupe_key': 'old-waiting',
            'timestamp': self.now - timedelta(days=400), 'state': 'new'})

        Settings.create({'cl_hik_retention_days': 0}).set_values()
        self.assertEqual(Punch._cl_retention_days(), 0)
        self.assertEqual(Settings.create({}).cl_hik_retention_days, 0, '0 is kept, not replaced by the default')
        self.assertEqual(Punch._cl_cleanup(), 0)
        self.assertTrue(old.exists())

        Settings.create({'cl_hik_retention_days': 30}).set_values()
        self.assertEqual(Punch._cl_cleanup(), 1)
        self.assertFalse(old.exists())
        self.assertTrue(waiting.exists(), 'a punch still to process is never cleaned up')

    def test_download_interval_follows_the_scheduled_action(self):
        cron = self.env.ref('cl_hr_attendance_hikvision.cl_hik_ir_cron_sync')
        Settings = self.env['res.config.settings']
        cron.write({'interval_number': 1, 'interval_type': 'hours'})
        settings = Settings.create({})
        self.assertEqual(settings.cl_hik_sync_interval, 60)
        # Saving the settings without touching the interval leaves the scheduled action alone.
        settings.set_values()
        self.assertEqual((cron.interval_number, cron.interval_type), (1, 'hours'))
        Settings.create({'cl_hik_sync_interval': 10}).set_values()
        self.assertEqual((cron.interval_number, cron.interval_type), (10, 'minutes'))

    def test_device_with_punches_cannot_be_deleted(self):
        self.fake.add('101', self._at(8))
        self.device.action_cl_sync_now()
        with self.assertRaises(UserError):
            self.device.unlink()
        spare = self.env['cl.hik.device'].create({'name': 'Spare Terminal', 'host': '10.0.0.6'})
        spare.unlink()
        self.assertFalse(spare.exists())

    def test_unmapped_punches_group_by_device_user(self):
        for user_id, hours in (('301', 8), ('301', 17), ('302', 9)):
            self.fake.add(user_id, self._at(hours))
        self.device.action_cl_sync_now()
        groups = self.env['cl.hik.punch']._read_group(
            [('state', '=', 'unmapped')], ['hik_user_id'], ['__count'])
        self.assertEqual(dict(groups), {'301': 2, '302': 1})
