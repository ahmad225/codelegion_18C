# Hikvision Attendance Sync (`cl_hr_attendance_hikvision`)

Punches from Hikvision access-control and time-attendance terminals, turned into Odoo attendances. By [Code Legion](https://thecodelegion.com).

Connect your Hikvision terminals over the local network or VPN (ISAPI). Odoo downloads every punch on a schedule, matches it to the employee by their device ID, and builds check-ins and check-outs. Night shifts and double swipes are handled, and HR corrections are never overwritten.

## What it does

- **Reliable sync**: Incremental download with paging, safe to rerun, on a schedule or with "Sync Now".
- **Night shifts**: A check-out is accepted across midnight, up to the maximum shift length you set.
- **Double swipes ignored**: Punches within a few minutes of the previous one are skipped (configurable).
- **HR edits respected**: Attendances HR created or corrected are never changed; conflicts go to a review list.

## Behaves well

- The device password is visible only to system administrators; HTTPS and certificate checks are on by default.
- A connection error never loses punches: the device shows the error and the next sync carries on where it stopped.
- A long backlog is downloaded a part at a time, each run saving its own work, so server time limits never cancel it.
- Downloading a period again never books an attendance twice, even after the old punches were cleaned up.
- Punches recorded before an employee's ID was set are processed as soon as it is set.
- Worked hours are left to Odoo, so lunch breaks are still deducted. Raw punches can't be edited, and old ones are cleaned up after the retention period (0 keeps them for ever). A device with punches is archived, not deleted.

## Technical

- Models `cl.hik.device` and `cl.hik.punch`; `cl_hik_user_id` on `hr.employee` (unique per company).
- ISAPI `/ISAPI/AccessControl/AcsEvent` with digest authentication; cron per device in its own savepoint. Test with your terminal model before going live.
- Tests: `odoo -i cl_hr_attendance_hikvision --test-tags /cl_hr_attendance_hikvision`.
- Odoo 18.0 · depends on `hr_attendance` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
