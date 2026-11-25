# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Partner Payment Term Default',
    'summary': "Default and sync a company's payment terms down to its child "
               "contacts, while letting a contact keep its own.",
    'description': """
Partner Payment Term Default
============================
One rule: a contact has the customer and vendor payment terms of its company,
unless **Keep Own Payment Terms** is ticked on it.

* New contacts of a company get the company's payment terms, however they are
  created.
* Changing the company's terms updates all its contacts, at any depth.
* Giving a contact different terms ticks **Keep Own Payment Terms** for you;
  the company's changes then leave it alone. Untick it and the contact goes
  back to the company's terms.
* A contact moved to another company takes the terms of the new company.
* An **Apply Company Payment Terms** action repairs existing contacts and
  reports what it did.

Behaves well:

* Payment terms are stored per company: new and moved contacts are aligned in
  every company, and a change made in one company stays in that company.
* A contact that keeps its own terms is never overwritten.
* A child company (subsidiary) stays its own commercial entity, as in standard
  Odoo.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'data/ir_actions_server.xml',
        'views/res_partner_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
