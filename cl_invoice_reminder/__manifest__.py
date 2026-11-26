# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Invoice Payment Reminders',
    'summary': 'Email customers automatically about overdue invoices, stage '
               'by stage, with one email per customer and a record of every '
               'reminder sent.',
    'description': """
Invoice Payment Reminders
=========================
Follows up overdue customer invoices for you. You describe a reminder schedule
- for example a friendly reminder 7 days after the due date, a firmer one after
15 days and a final notice after 30 days - and a daily job emails each customer
the reminder that is due.

What you get:

* **Reminder stages** per company: a name, a number of days after the due
  date and an email template.
* **One email per customer** listing all the invoices that reached the stage,
  instead of one email per invoice.
* **Reminders Sent**: every reminder is recorded with the invoice, the stage,
  the address it went to, the days overdue and the amount due at the time. A
  button on the invoice opens its reminders.
* **Overdue Invoices** work list: days overdue, amount due, the stage each
  invoice reached and when, with filters for invoices not reminded yet, final
  reminder sent, partially paid and customers without an email address.
* **Multi-company**: each company has its own schedule and sender address;
  one job serves them all.

How it behaves:

* An invoice receives each stage once, and never a stage earlier than one it
  already received. An invoice that is already 40 days overdue when you switch
  reminders on gets the 30-day reminder once - not three reminders in a row.
* The email goes to the invoice contact, or to the company it belongs to when
  that contact has no email. Customers without any email are not recorded as
  reminded and are reminded as soon as an address is filled in.
* Customers are handled one by one: a problem with one customer never stops
  the others, and a large run is split in batches that follow each other
  without waiting for the next day.
* The email template and the scheduled job are not overwritten by upgrades.
* Searching on days overdue always agrees with the number shown: paid
  invoices, drafts and vendor bills are 0 days overdue.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': [
        'account',
    ],
    'data': [
        'security/reminder_security.xml',
        'security/ir.model.access.csv',
        'data/reminder_data.xml',
        'views/reminder_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
