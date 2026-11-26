# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Chart of Accounts Archive',
    'summary': 'Archive and unarchive accounts in the Chart of Accounts.',
    'description': """
Chart of Accounts Archive
=========================
Adds Archive / Unarchive to the Chart of Accounts. Odoo marks an account out of
use with its **Deprecated** flag; this module presents that flag as "Archived"
and adds the Archive / Unarchive actions users expect.

* Archive one or more accounts from the list or form via the Actions menu
  (Account Managers only).
* "Archived" here means Odoo's **Deprecated** flag: the account is kept out of
  account pickers and new journal entries. An *Archived* ribbon and toggle mark
  it on the form and the *Archived* filter lists archived accounts for review
  or restore.
* Archiving is blocked while a tax still posts to the account; the message
  lists the accounts and the taxes concerned.
* Archived accounts are greyed out in the list.

Note: the module adds no field of its own. Archived accounts are hidden from
pickers but still visible in the Chart of Accounts when you include them.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'data/ir_actions_server.xml',
        'views/account_account_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
