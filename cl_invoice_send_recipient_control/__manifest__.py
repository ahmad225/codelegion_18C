# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Invoice Send Recipient Control',
    'summary': "When emailing an invoice, notify only the chosen recipients, "
               "not the document's followers.",
    'description': """
Invoice Send Recipient Control
==============================
When you send an invoice by email, Odoo also notifies the invoice's followers.
With this setting on, an invoice email reaches only the customer and anyone
you add in the Send window - followers are left out.

* One setting per company: Invoice Emails: Skip Followers.
* Applies to everything sent through Odoo's standard invoice sending: the Send
  window, Send on several invoices, and automatic flows built on it.
* A follower added as a recipient on purpose still gets the email; if all
  recipients are removed, nobody is emailed.
* Chatter messages keep notifying followers as usual.

Behaves well:

* The recipient list is Odoo's own, simply filtered down to the chosen
  recipients, so other apps that extend invoice notifications keep working.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account'],
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
