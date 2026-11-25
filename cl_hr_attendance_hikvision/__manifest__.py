# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Hikvision Attendance Sync',
    'summary': 'Download punches from Hikvision access-control and time-attendance '
               'terminals and turn them into Odoo attendances.',
    'description': """
Hikvision Attendance Sync
=========================
Connect Hikvision face, fingerprint and card terminals on your local network
(or over a VPN) to Odoo Attendances. Punches are downloaded over the device's
own ISAPI web interface and paired into check-ins and check-outs.

* Devices under Attendances > Configuration > Hikvision Devices: address, port,
  HTTPS (on by default) with certificate check, user name, device time zone,
  company. "Test Connection" reads the device model, serial number and firmware.
* Every few minutes (set in Attendance settings) new punches are downloaded,
  page by page, from the point the last complete download reached. "Sync Now"
  does the same on demand.
* Each punch is matched to the employee whose "Hikvision User ID" (Employee >
  Settings tab) equals the Employee No. on the device. Punches of people not yet
  mapped are kept and are turned into attendances as soon as the ID is entered.
* Pairing, per employee and in time order: a second read within the double-swipe
  threshold (default 2 minutes) is ignored; punches alternate check-in and
  check-out; a check-out is accepted up to the maximum shift length after the
  check-in (default 16 hours), so night shifts across midnight pair correctly.
* A check-in with no check-out within the maximum shift length is closed with
  zero hours and flagged "Missing check-out" for HR. If the real check-out
  arrives later (device was offline), it is filled in automatically.
* Attendances > Hikvision Punches lists every downloaded punch with its result:
  processed, double swipe, not mapped or to review, with filters by device,
  employee and day. "Process Again" retries punches set to review once HR has
  fixed the cause; "Reprocess Unmapped" on the device retries unmapped ones.
* To download a period again, set "Downloaded Up To" on the device back; it is
  read once, punches already stored are skipped, and a punch whose attendance
  already exists is only linked to it, never booked twice.
* Old punches are deleted after the retention period (default 365 days, 0 keeps
  them for ever); attendances are never deleted.
* A long backlog (first download of several months, or a device that was
  offline for weeks) is read a part at a time: every run saves what it read and
  the next run carries on, so a server time limit never throws the work away.

Behaves well:

* Never deletes or rewrites attendances. It only creates new ones and completes
  its own open check-ins. An attendance HR created, or edited after the device
  created it, is never touched again.
* A manual or kiosk attendance that overlaps the punches does not block the day:
  only the conflicting punches are set to "To Review", with the reason.
* Worked hours are Odoo's own calculation (lunch breaks are still deducted).
* An empty period on the device never stops the download, and punches downloaded
  twice (overlap, re-download) are stored only once.
* A connection or answer error puts the device in "Error" with the message and
  leaves the download point where it was, so nothing is lost; the next run tries
  again. A refused login pauses the automatic downloads of that device until the
  connection is tested again, so the device does not lock its account. A single
  unreadable punch is skipped (and logged) instead of blocking the device.
* A device that has punches cannot be deleted by mistake; archive it instead.
* Each device is downloaded in its own transaction savepoint and locked while it
  is read, so the scheduled job and "Sync Now" never download it twice at once.
* The device password can only be read by system administrators. Attendance
  administrators can set it (Set Password) and run syncs, but cannot read it.
  Attendance officers see the devices and the punches of the employees they
  manage, and cannot run or change anything.
* Punches are read-only for everybody. Multi-company rules on devices and punches.
* "Test Connection" also compares the device clock and time zone with Odoo and
  warns when they differ.
* No external Python library: Odoo's own "requests" with HTTP digest login.

Not included: the Hik-Connect / Hik-Partner cloud. Devices must be reachable from
the Odoo server on the local network or over a VPN. Pushing employees to the
device is not included either: enrol people on the device and enter the same
Employee No. in Odoo.

To check with a real device before going live: the login (digest) and HTTPS
certificate of your firmware, that the event search (ISAPI AccessControl/AcsEvent)
returns punches with the Employee No., that the times shown in Odoo match the
time on the device (device time zone), and the event codes your terminal uses if
you restrict them on the device form.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Human Resources/Attendances',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'security/cl_hik_security.xml',
        'data/ir_cron_data.xml',
        'wizard/cl_hik_device_password_views.xml',
        'views/cl_hik_device_views.xml',
        'views/cl_hik_punch_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/cl_hik_menus.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
