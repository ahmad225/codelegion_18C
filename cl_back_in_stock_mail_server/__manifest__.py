# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Back-in-Stock Email Server',
    'summary': 'Send the eCommerce "back in stock" emails through a dedicated '
               'outgoing mail server.',
    'description': """
Back-in-Stock Email Server
==========================
Route the eCommerce "the product is now available" emails through an outgoing
mail server of your choice - for example a marketing/bulk sender - instead of
the server used for invoices and orders.

* One setting per company: the outgoing mail server for back-in-stock emails.
* A product that belongs to a company uses that company's server; a shared
  product, or a company without its own server, uses the server of the
  website's company.
* Leave it empty to keep Odoo's normal behaviour.

Behaves well:

* Odoo's own back-in-stock logic is kept untouched (content, translated
  subject, sender) - the module only chooses the server, so future Odoo fixes
  still apply.
* An archived server is ignored: customers still get their email through the
  usual server.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Website/eCommerce',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['website_sale_stock'],
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
