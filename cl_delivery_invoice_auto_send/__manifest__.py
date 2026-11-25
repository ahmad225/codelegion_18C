# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Auto-send Invoice on Delivery',
    'summary': "Automatically send the customer invoice (with its PDF) once "
               "the delivery is validated.",
    'description': """
Auto-send Invoice on Delivery
=============================
When an outgoing delivery is validated, this module automatically sends the
posted customer invoices of its sale order to the customer - with the invoice
PDF attached - through Odoo's standard Send queue.

* Triggers on **delivery validation** (outgoing picking done), and on
  **invoice posting** when the goods have already left (invoicing policy
  "delivered quantities").
* Sends through `account.move.send`, so the **PDF is generated and attached**,
  the customer's sending preference and email template are used, and the
  invoice is marked as sent.
* Each invoice is sent once: invoices already sent by hand or by another
  automatic flow are left alone.

Behaves well:

* Never blocks or slows down the delivery validation: the invoice is put in
  Odoo's background sending queue and leaves a moment later.
* Works for warehouse users who have no accounting rights.
* Reads the setting from the **invoice's company**, not the current user's
  company.
* Identifies deliveries by the operation **type code** (outgoing), not by name,
  so renaming or translating operation types doesn't break it.
* A customer without an email address gets a note on the invoice instead of a
  silent skip; a failed sending shows the standard error in the chatter.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account', 'sale_stock'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
