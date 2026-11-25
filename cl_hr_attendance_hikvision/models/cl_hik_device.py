# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta

import pytz
import requests
from lxml import etree
from psycopg2 import errors as pgerrors
from requests.auth import HTTPDigestAuth

from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)

# The next download starts this much before the point the previous one reached, so a punch
# the device stored a little late is still picked up. Punches downloaded twice are skipped.
CL_HIK_OVERLAP = timedelta(minutes=10)
# Long periods are downloaded one day at a time; each completed day moves the download
# point forward, so a failure never throws away the days already read.
CL_HIK_SLICE = timedelta(days=1)
CL_HIK_MAX_SLICES_PER_RUN = 31
# One run (the scheduled job or "Sync Now") always reads one period per device, then goes on
# with older periods only while this many seconds have not passed. A long backlog is spread
# over several runs, each saved on its own, instead of one long transaction that a worker
# time limit would cancel as a whole, again and again.
CL_HIK_RUN_SECONDS = 60
# Many terminals answer at most 30 events per page whatever is asked; paging uses the
# number of events actually received, so any page size the device chooses works.
CL_HIK_PAGE_SIZE = 30
CL_HIK_MAX_PAGES = 2000
CL_HIK_TIMEOUT = 20
# A device that is switched off or unreachable is given up on sooner than a slow answer.
CL_HIK_CONNECT_TIMEOUT = 8
CL_HIK_CLOCK_TOLERANCE = 120  # seconds
CL_HIK_CONNECTION_FIELDS = {'host', 'port', 'use_https', 'verify_certificate', 'username', 'password'}
# ISAPI "major" type of access-control events (as opposed to alarms, exceptions, operations).
CL_HIK_MAJOR_EVENT = 5


class ClHikError(Exception):
    """The device could not be reached, refused the request or sent something unusable."""


class ClHikLoginError(ClHikError):
    """The device refused the user name / password. Not retried automatically: Hikvision
    devices lock the account after a few failed logins."""


def _cl_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cl_parse_device_time(value, tz_name):
    """Read an ISAPI time ("2026-11-02T08:15:00+05:00", "...Z" or without offset).

    Returns (naive UTC datetime, offset given by the device or None). A time without
    offset is read in the device time zone."""
    if not value or not isinstance(value, str):
        raise ClHikError(_('The device sent a punch without a time.'))
    text = value.strip()
    if text.endswith(('Z', 'z')):
        text = text[:-1] + '+00:00'
    text = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', text)  # +0500 -> +05:00
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ClHikError(_('Cannot read the time "%s" sent by the device.', value)) from None
    offset = moment.utcoffset()
    if moment.tzinfo is None:
        moment = pytz.timezone(tz_name or 'UTC').localize(moment)
    return moment.astimezone(pytz.utc).replace(tzinfo=None, microsecond=0), offset


def _cl_format_offset(offset):
    minutes = int(offset.total_seconds() // 60)
    sign = '+' if minutes >= 0 else '-'
    return 'UTC%s%02d:%02d' % (sign, abs(minutes) // 60, abs(minutes) % 60)


def _cl_xml_to_dict(element):
    children = [child for child in element if isinstance(child.tag, str)]
    if not children:
        return (element.text or '').strip()
    result = {}
    for child in children:
        key = etree.QName(child).localname
        value = _cl_xml_to_dict(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def _cl_parse_answer(content):
    """ISAPI answers in JSON (when asked with format=json and supported) or in XML."""
    text = (content or b'').lstrip(b'\xef\xbb\xbf').strip()
    if not text:
        return {}
    if text[:1] in (b'{', b'['):
        try:
            return json.loads(text)
        except ValueError:
            raise ClHikError(_('The device sent an answer that is not valid JSON.')) from None
    if text[:1] == b'<':
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        try:
            root = etree.fromstring(text, parser=parser)
        except etree.XMLSyntaxError:
            raise ClHikError(_('The device sent an answer that is not valid XML.')) from None
        return {etree.QName(root).localname: _cl_xml_to_dict(root)}
    raise ClHikError(_('The device sent an answer that is neither JSON nor XML. Is this a Hikvision ISAPI device?'))


def _cl_status_text(data):
    """Error details of an ISAPI ResponseStatus (JSON or XML)."""
    if not isinstance(data, dict):
        return ''
    status = data.get('ResponseStatus', data)
    if not isinstance(status, dict):
        return ''
    parts = [str(status[key]) for key in ('statusString', 'subStatusCode', 'errorMsg') if status.get(key)]
    return ' / '.join(parts)


class ClHikDevice(models.Model):
    _name = 'cl.hik.device'
    _description = 'Hikvision Device'
    _order = 'name, id'

    def _cl_default_tz(self):
        return self.env.user.tz or self.env.company.partner_id.tz or 'UTC'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company,
        help='Punches are matched with the employees of this company.')
    host = fields.Char(
        string='Address', required=True,
        help='IP address or host name of the device, as reached from the Odoo server '
             '(local network or VPN), for example 192.168.1.64.')
    port = fields.Integer(default=443, required=True)
    use_https = fields.Boolean(string='Use HTTPS', default=True)
    verify_certificate = fields.Boolean(
        default=True,
        help='Check the HTTPS certificate of the device. Devices ship with a self-signed certificate: '
             'either install a trusted certificate on the device or untick this to accept it.')
    username = fields.Char(string='User Name', required=True, default='admin')
    # Only system administrators can read it (also through export or RPC). Attendance
    # administrators set it with "Set Password" and run syncs, which read it with sudo.
    password = fields.Char(groups='base.group_system', copy=False)
    password_set = fields.Boolean(compute='_compute_password_set', compute_sudo=True)
    tz = fields.Selection(
        _tz_get, string='Device Time Zone', required=True, default=_cl_default_tz,
        help='Time zone the device clock runs in. Used for the download period and for punch times '
             'the device sends without a UTC offset.')
    event_minor_codes = fields.Char(
        string='Only Event Codes',
        help='Comma-separated ISAPI minor event codes to keep (see your device documentation). '
             'Leave empty to keep every access event that carries an Employee No.')
    sync_from = fields.Datetime(
        string='First Download From', required=True,
        default=lambda self: fields.Datetime.now() - timedelta(days=1),
        help='Punches are downloaded from this time on the first sync.')
    downloaded_until = fields.Datetime(
        string='Downloaded Up To', copy=False,
        help='Every punch up to this time has been downloaded. The next download starts 10 minutes '
             'earlier; punches already stored are skipped. Set an earlier time to download a period again.')
    last_event_time = fields.Datetime(string='Latest Punch', readonly=True, copy=False)
    state = fields.Selection(
        [('not_tested', 'Not Tested'), ('connected', 'Connected'), ('error', 'Error')],
        string='Status', default='not_tested', required=True, readonly=True, copy=False)
    last_error = fields.Text(readonly=True, copy=False)
    last_error_date = fields.Datetime(string='Last Error On', readonly=True, copy=False)
    login_refused = fields.Boolean(
        readonly=True, copy=False,
        help='The device refused the login. Automatic downloads pause until the connection is tested '
             'again, so the device account is not locked by repeated attempts.')
    last_sync_ok = fields.Datetime(string='Last Successful Sync', readonly=True, copy=False)
    device_model = fields.Char(string='Model', readonly=True, copy=False)
    device_serial = fields.Char(string='Serial Number', readonly=True, copy=False)
    firmware = fields.Char(readonly=True, copy=False)
    clock_note = fields.Char(string='Device Clock', readonly=True, copy=False)
    clock_warning = fields.Boolean(readonly=True, copy=False)
    punch_count = fields.Integer(compute='_compute_punch_counts')
    unmapped_count = fields.Integer(compute='_compute_punch_counts')
    review_count = fields.Integer(compute='_compute_punch_counts')

    @api.depends('password')
    def _compute_password_set(self):
        for device in self:
            device.password_set = bool(device.password)

    def _compute_punch_counts(self):
        counts = {}
        if self.ids:
            groups = self.env['cl.hik.punch']._read_group(
                [('device_id', 'in', self.ids)], ['device_id', 'state'], ['__count'])
            for device, state, count in groups:
                counts.setdefault(device.id, {})[state] = count
        for device in self:
            device_counts = counts.get(device.id, {})
            device.punch_count = sum(device_counts.values())
            device.unmapped_count = device_counts.get('unmapped', 0)
            device.review_count = device_counts.get('review', 0)

    @api.constrains('host', 'port')
    def _cl_check_address(self):
        for device in self:
            host = (device.host or '').strip()
            if not host or '://' in host or '/' in host or ' ' in host:
                raise ValidationError(_('Enter only the IP address or host name of the device, '
                                        'without "http://" and without a path.'))
            if not 0 < device.port < 65536:
                raise ValidationError(_('The port must be between 1 and 65535.'))

    @api.constrains('event_minor_codes')
    def _cl_check_event_codes(self):
        for device in self:
            for part in (device.event_minor_codes or '').replace(';', ',').split(','):
                if part.strip() and not part.strip().isdigit():
                    raise ValidationError(_('"Only Event Codes" must be numbers separated by commas.'))

    @api.onchange('use_https')
    def _onchange_cl_use_https(self):
        if self.port in (80, 443):
            self.port = 443 if self.use_https else 80

    def write(self, vals):
        if CL_HIK_CONNECTION_FIELDS & set(vals) and 'state' not in vals:
            vals = dict(vals, state='not_tested', login_refused=False)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _cl_unlink_except_punches(self):
        # The punches are the evidence behind the attendances: they keep their device.
        used = self.env['cl.hik.punch'].sudo().search([('device_id', 'in', self.ids)], limit=1).device_id
        if used:
            raise UserError(_(
                'The device "%s" has downloaded punches and cannot be deleted. Archive it instead: '
                'an archived device is no longer downloaded.', used.name))

    # ------------------------------------------------------------------
    # Device access
    # ------------------------------------------------------------------

    def _cl_check_manager(self):
        """Only users allowed to change the devices (Attendance administrators) may
        connect to them. The work itself then runs with sudo, which can read the password."""
        self.check_access('write')

    def _cl_base_url(self):
        self.ensure_one()
        host = self.host.strip()
        if ':' in host and not host.startswith('['):
            host = '[%s]' % host  # IPv6
        return '%s://%s:%s' % ('https' if self.use_https else 'http', host, self.port)

    def _cl_isapi_request(self, method, path, payload=None):
        """The only place that talks to the device. Returns the answer as a dict
        (JSON as is, XML converted) or raises ClHikError. Tests replace this method."""
        self.ensure_one()
        device = self.sudo()
        url = device._cl_base_url() + path
        try:
            response = requests.request(
                method, url, json=payload, timeout=(CL_HIK_CONNECT_TIMEOUT, CL_HIK_TIMEOUT),
                auth=HTTPDigestAuth(device.username or '', device.password or ''),
                verify=bool(device.verify_certificate))
        except requests.exceptions.SSLError as exc:
            raise ClHikError(_(
                'The HTTPS certificate of the device is not trusted (%s). Devices usually ship with a '
                'self-signed certificate: install a trusted one on the device, or untick "Verify Certificate".',
                exc)) from None
        except requests.exceptions.ConnectTimeout:
            raise ClHikError(_(
                'Cannot connect to %(url)s (no answer within %(seconds)s seconds). Check the address and '
                'the port, and that the device is switched on and reachable from the Odoo server.',
                url=device._cl_base_url(), seconds=CL_HIK_CONNECT_TIMEOUT)) from None
        except requests.exceptions.Timeout:
            raise ClHikError(_('No answer from %(url)s within %(seconds)s seconds.',
                               url=device._cl_base_url(), seconds=CL_HIK_TIMEOUT)) from None
        except requests.exceptions.RequestException as exc:
            raise ClHikError(_('Cannot reach the device at %(url)s: %(error)s',
                               url=device._cl_base_url(), error=exc)) from None
        if response.status_code == 401:
            raise ClHikLoginError(_('The device refused the login (HTTP 401). Check the user name and '
                                    'password; the device may lock the account after several failed attempts.'))
        try:
            data = _cl_parse_answer(response.content)
        except ClHikError:
            if response.status_code >= 400:
                raise ClHikError(_('The device answered HTTP %(code)s (%(reason)s).',
                                   code=response.status_code, reason=response.reason)) from None
            raise
        if response.status_code >= 400:
            raise ClHikError(_('The device answered HTTP %(code)s: %(detail)s',
                               code=response.status_code,
                               detail=_cl_status_text(data) or response.reason))
        return data

    def _cl_set_error(self, error):
        self.ensure_one()
        message = str(error) or error.__class__.__name__
        _logger.warning('Hikvision device %s (%s): %s', self.name, self.id, message)
        self.sudo().write({
            'state': 'error',
            'last_error': message,
            'last_error_date': fields.Datetime.now(),
            'login_refused': isinstance(error, ClHikLoginError),
        })

    def _cl_lock(self):
        """Lock the device row for this transaction, so two downloads (cron and button)
        never run for the same device at the same time."""
        self.ensure_one()
        try:
            # A busy device is an expected answer here, not an error for the server log.
            with self.env.cr.savepoint(flush=False), mute_logger('odoo.sql_db'):
                self.env.cr.execute('SELECT id FROM cl_hik_device WHERE id = %s FOR UPDATE NOWAIT', [self.id])
        except pgerrors.LockNotAvailable:
            return False
        return True

    # ------------------------------------------------------------------
    # Test connection
    # ------------------------------------------------------------------

    def action_cl_test_connection(self):
        self._cl_check_manager()
        for device in self.sudo():
            try:
                data = device._cl_isapi_request('GET', '/ISAPI/System/deviceInfo')
                info = data.get('DeviceInfo') if isinstance(data, dict) else None
                if not isinstance(info, dict):
                    raise ClHikError(_('The device did not return its device information: %s',
                                       _cl_status_text(data) or str(data)[:200]))
                clock_note, clock_warning = device._cl_read_clock()
                device.write({
                    'state': 'connected',
                    'last_error': False,
                    'login_refused': False,
                    'device_model': info.get('model') or info.get('deviceName') or False,
                    'device_serial': info.get('serialNumber') or False,
                    'firmware': ' '.join(filter(None, [info.get('firmwareVersion'),
                                                       info.get('firmwareReleasedDate')])) or False,
                    'clock_note': clock_note,
                    'clock_warning': clock_warning,
                })
            except ClHikError as error:
                device._cl_set_error(error)
        if len(self) == 1:
            if self.state == 'connected':
                message = _('Connected to %(model)s %(serial)s.', model=self.device_model or '',
                            serial=self.device_serial or '')
                if self.clock_warning:
                    message += ' ' + self.clock_note
                return self._cl_notify(_('Test Connection'), message, 'warning' if self.clock_warning else 'success')
            return self._cl_notify(_('Test Connection'), self.last_error, 'danger')
        return self._cl_notify(_('Test Connection'), _('%(ok)s of %(total)s device(s) connected.',
                                                       ok=len(self.filtered(lambda d: d.state == 'connected')),
                                                       total=len(self)), 'info')

    def _cl_read_clock(self):
        """Compare the device clock and UTC offset with the server and this record. A wrong
        clock or time zone silently shifts every punch, so it is worth a warning."""
        self.ensure_one()
        try:
            data = self._cl_isapi_request('GET', '/ISAPI/System/time')
        except ClHikError as error:
            if isinstance(error, ClHikLoginError):
                raise
            return _('Could not read the device clock (%s).', error), False
        info = data.get('Time') if isinstance(data, dict) else None
        local_time = info.get('localTime') if isinstance(info, dict) else None
        if not local_time:
            return _('The device did not report its clock.'), False
        try:
            device_utc, offset = _cl_parse_device_time(local_time, self.tz)
        except ClHikError:
            return _('Could not read the device clock "%s".', local_time), False
        now = fields.Datetime.now()
        skew = int((device_utc - now).total_seconds())
        notes, warning = [], False
        if abs(skew) > CL_HIK_CLOCK_TOLERANCE:
            warning = True
            notes.append(_('The device clock is %(minutes)s minute(s) %(direction)s the server. '
                           'Enable NTP on the device.', minutes=abs(skew) // 60,
                           direction=_('ahead of') if skew > 0 else _('behind')))
        else:
            notes.append(_('Device clock in time (%s s).', skew))
        if offset is not None:
            expected = pytz.utc.localize(now).astimezone(pytz.timezone(self.tz or 'UTC')).utcoffset()
            if offset != expected:
                warning = True
                notes.append(_('The device runs in %(device)s but the time zone here is %(tz)s (%(expected)s): '
                               'correct one of them.', device=_cl_format_offset(offset), tz=self.tz,
                               expected=_cl_format_offset(expected)))
        return ' '.join(notes), warning

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def action_cl_sync_now(self):
        self._cl_check_manager()
        deadline = time.monotonic() + CL_HIK_RUN_SECONDS
        results = []
        for device in self.sudo():
            results.append((device, device._cl_sync(deadline=deadline)))
        self.env['cl.hik.punch'].sudo()._cl_process_pending(devices=self.sudo())
        errors = [_('%(device)s: %(error)s', device=device.name, error=result['error'])
                  for device, result in results if result.get('error')]
        new = sum(result.get('new', 0) for _device, result in results)
        if errors:
            return self._cl_notify(_('Sync Now'), '\n'.join(errors), 'danger')
        message = _('%s new punch(es) downloaded.', new)
        if any(result.get('more') for _device, result in results):
            message += ' ' + _('Older punches are still being downloaded; the next sync continues.')
        return self._cl_notify(_('Sync Now'), message, 'success')

    def _cl_sync(self, deadline=None):
        """Download new punches of one device. Never raises for device problems: the device
        is set to Error with the message and the download point stays where it was.

        deadline (time.monotonic() value): once passed, older periods still to read are left
        to the next run. The first period is always read, so every run makes progress."""
        self.ensure_one()
        if not self._cl_lock():
            return {'error': _('A download from this device is already running.'), 'new': 0}
        now = fields.Datetime.now()
        if self.downloaded_until:
            start = self.downloaded_until - CL_HIK_OVERLAP
        else:
            start = self.sync_from or now - timedelta(days=1)
        # A download point in the future (clock change) must not block the download.
        start = min(start, now - CL_HIK_OVERLAP)
        created = 0
        try:
            for number in range(CL_HIK_MAX_SLICES_PER_RUN):
                if start >= now:
                    break
                if number and deadline is not None and time.monotonic() >= deadline:
                    break
                end = min(start + CL_HIK_SLICE, now)
                with self.env.cr.savepoint():
                    created += self._cl_download_window(start, end)
                    # Only once the whole period was read, empty or not.
                    self.downloaded_until = end
                start = end
        except ClHikError as error:
            self._cl_set_error(error)
            return {'error': str(error), 'new': created}
        self.write({'state': 'connected', 'last_error': False, 'login_refused': False, 'last_sync_ok': now})
        return {'new': created, 'more': start < now}

    def _cl_minor_codes(self):
        return {int(part) for part in (self.event_minor_codes or '').replace(';', ',').split(',')
                if part.strip().isdigit()}

    def _cl_download_window(self, start, end):
        """Read every page of the event search between start and end (naive UTC) and store
        the punches. Returns the number of new punches."""
        self.ensure_one()
        tz = pytz.timezone(self.tz or 'UTC')

        def device_time(moment):
            return pytz.utc.localize(moment).astimezone(tz).isoformat(timespec='seconds')

        search_id = uuid.uuid4().hex
        position = 0
        created = 0
        minor_codes = self._cl_minor_codes()
        for _page in range(CL_HIK_MAX_PAGES):
            payload = {'AcsEventCond': {
                'searchID': search_id,
                'searchResultPosition': position,
                'maxResults': CL_HIK_PAGE_SIZE,
                'major': CL_HIK_MAJOR_EVENT,
                'minor': 0,
                'startTime': device_time(start),
                'endTime': device_time(end),
            }}
            data = self._cl_isapi_request('POST', '/ISAPI/AccessControl/AcsEvent?format=json', payload)
            answer = data.get('AcsEvent') if isinstance(data, dict) else None
            if not isinstance(answer, dict):
                raise ClHikError(_('Unexpected answer to the punch search: %s',
                                   _cl_status_text(data) or str(data)[:200]))
            events = answer.get('InfoList') or []
            if isinstance(events, dict):
                events = [events]
            if not isinstance(events, list):
                raise ClHikError(_('Unexpected list of punches in the answer of the device.'))
            created += self._cl_store_events(events, minor_codes)
            position += len(events)
            status = (answer.get('responseStatusStrg') or '').upper()
            if status == 'MORE':
                if not events:
                    raise ClHikError(_('The device announced more punches but sent none (position %s).', position))
                continue
            if status in ('OK', 'NO MATCH', 'NO_MATCH'):
                return created
            raise ClHikError(_('Unexpected search status "%s" from the device.', status))
        raise ClHikError(_('More than %(pages)s pages of punches between %(start)s and %(end)s (UTC). '
                           'The download stopped there and will try again.',
                           pages=CL_HIK_MAX_PAGES, start=start, end=end))

    def _cl_store_events(self, events, minor_codes):
        self.ensure_one()
        Punch = self.env['cl.hik.punch'].sudo()
        vals_by_key = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            user_id = event.get('employeeNoString') or event.get('employeeNo')
            user_id = str(user_id).strip() if user_id not in (None, False) else ''
            if not user_id or user_id == '0':
                continue  # door, alarm and other events without a person
            minor = _cl_int(event.get('minor'))
            if minor_codes and minor not in minor_codes:
                continue
            try:
                timestamp, _offset = _cl_parse_device_time(event.get('time'), self.tz)
            except ClHikError as error:
                # One unreadable event must not block every later download of the device.
                _logger.warning('Hikvision device %s (%s): punch of user %s skipped: %s',
                                self.name, self.id, user_id, error)
                continue
            serial = _cl_int(event.get('serialNo'))
            key = '%s|%s|%s' % (serial if serial is not None else '-', user_id, fields.Datetime.to_string(timestamp))
            raw_type = '/'.join(str(part) for part in (event.get('major'), minor) if part is not None)
            extra = [str(event[name]) for name in ('currentVerifyMode', 'attendanceStatus')
                     if event.get(name) and event.get(name) != 'undefined']
            vals_by_key[key] = {
                'device_id': self.id,
                'hik_user_id': user_id,
                'timestamp': timestamp,
                'serial_no': serial or 0,
                'dedupe_key': key,
                'raw_type': ' '.join([raw_type] + extra).strip() or False,
            }
        if not vals_by_key:
            return 0
        existing = set(Punch.search([('device_id', '=', self.id),
                                     ('dedupe_key', 'in', list(vals_by_key))]).mapped('dedupe_key'))
        new_vals = [vals for key, vals in vals_by_key.items() if key not in existing]
        employees = self._cl_employee_map({vals['hik_user_id'] for vals in new_vals})
        for vals in new_vals:
            employee = employees.get(vals['hik_user_id'])
            vals['employee_id'] = employee.id if employee else False
            vals['state'] = 'new' if employee else 'unmapped'
        if new_vals:
            Punch.create(new_vals)
        # A device clock set in the future must not push this into the future.
        latest = min(max(vals['timestamp'] for vals in vals_by_key.values()), fields.Datetime.now())
        if not self.last_event_time or latest > self.last_event_time:
            self.last_event_time = latest
        return len(new_vals)

    def _cl_employee_map(self, user_ids):
        self.ensure_one()
        if not user_ids:
            return {}
        employees = self.env['hr.employee'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('cl_hik_user_id', 'in', list(user_ids)),
        ])
        return {employee.cl_hik_user_id: employee for employee in employees}

    @api.model
    def _cl_cron_sync(self):
        # Devices that refused the login wait for a manual Test Connection or Sync Now.
        devices = self.sudo().search([('login_refused', '=', False)])
        deadline = time.monotonic() + CL_HIK_RUN_SECONDS
        for device in devices:
            try:
                with self.env.cr.savepoint():
                    device._cl_sync(deadline=deadline)
            except Exception as error:  # never let one device stop the others
                _logger.exception('Hikvision sync of device %s failed', device.id)
                device._cl_set_error(error)
        Punch = self.env['cl.hik.punch'].sudo()
        Punch._cl_process_pending()
        self.env['hr.attendance'].sudo()._cl_hik_close_stale()
        Punch._cl_cleanup()

    # ------------------------------------------------------------------
    # Other buttons
    # ------------------------------------------------------------------

    def action_cl_reprocess_unmapped(self):
        self._cl_check_manager()
        Punch = self.env['cl.hik.punch'].sudo()
        unmapped = Punch.search([('device_id', 'in', self.ids), ('state', '=', 'unmapped')])
        mapped = unmapped._cl_map_employees()
        Punch._cl_process_pending(employees=mapped.employee_id)
        return self._cl_notify(
            _('Reprocess Unmapped'),
            _('%(mapped)s of %(total)s unmapped punch(es) now match an employee and were processed.',
              mapped=len(mapped), total=len(unmapped)),
            'success' if mapped or not unmapped else 'warning')

    def action_cl_set_password(self):
        self.ensure_one()
        self._cl_check_manager()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Set Device Password'),
            'res_model': 'cl.hik.device.password',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_device_id': self.id},
        }

    def _cl_open_punches(self, state=None):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('cl_hr_attendance_hikvision.cl_hik_punch_action')
        domain = [('device_id', '=', self.id)]
        if state:
            domain.append(('state', '=', state))
        action['domain'] = domain
        action['context'] = {'default_device_id': self.id}
        return action

    def action_cl_open_punches(self):
        return self._cl_open_punches()

    def action_cl_open_unmapped(self):
        return self._cl_open_punches('unmapped')

    def action_cl_open_review(self):
        return self._cl_open_punches('review')

    def _cl_notify(self, title, message, kind):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': kind,
                'sticky': kind == 'danger',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
