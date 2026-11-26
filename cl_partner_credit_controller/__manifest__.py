# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Customer Credit Controller',
    'summary': 'Give every customer a credit controller, kept the same on all '
               'its contacts, orders and invoices.',
    'description': """
Customer Credit Controller
==========================
Assign the person who chases payments for each customer, next to the
salesperson.

* "Credit Controller" on the customer (Sales & Purchase tab).
* Held by the customer's company and copied to all its contact persons, at
  every level, automatically - like the VAT number. New contacts get it at once.
* Shown on sales orders and invoices, with filters and grouping:
  "My Credit Customers", "My Invoices to Chase" (my customers' overdue
  invoices), "Credit Controller" group-by.
* Optionally printed on the invoice PDF, so the customer knows who to call.
* Action "Sync Credit Controller to Contacts" for data loaded from elsewhere.

Behaves well:

* Uses Odoo's own commercial-field sync: contacts at every level stay in step,
  and a contact moved to another company takes that company's controller.
* No view patching at run time and no Studio fields.
* Only internal users can be credit controllers, checked on the server.
* Quick to install on large databases: nothing is computed per order or
  invoice at install time.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['sale'],
    'data': [
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'report/report_invoice.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
