# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Low Stock Notifications',
    'summary': 'Daily e-mail of the products below their minimum stock, with an '
               'Excel list, plus a PDF / Excel report on demand.',
    'description': """
Low Stock Notifications
=======================
Every day, the products that are below their minimum stock are e-mailed to the
users you choose, with the complete list attached as an Excel file. The same
list can be printed (PDF) or downloaded (Excel) at any time from
Inventory > Reporting > Low Stock.

Minimum stock (per company):

* **One minimum for all products**, or
* **a minimum set on each product** (Inventory tab of the product), or
* **the minimum of the reordering rules**, checked at the location of each rule.

Options:

* Compare the minimum with the quantity **on hand** or the **forecasted**
  quantity.
* Count only selected **stock locations** (otherwise all the warehouses of the
  company).
* Any number of recipients; a timezone for the date printed on the documents.
* A **Send E-mail Now** button to check the configuration without waiting.

Behaves well:

* On-hand, free, incoming, outgoing and forecasted quantities of a line are
  all measured on the same locations, so goods expected in another warehouse
  never hide a shortage.
* Nothing is stored: the list is computed when it is needed. Printing never
  rewrites data, and no file piles up in the database.
* The Excel file is attached to the e-mail itself (no download link that
  expires), and e-mails go through the normal mail queue.
* Only products tracked in stock are checked; services and untracked goods are
  never reported.
* Multi-company: each company has its own settings, recipients and e-mail.
* The report and its settings are for Inventory Administrators.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'report/low_stock_report_templates.xml',
        'wizard/low_stock_report_wizard_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
