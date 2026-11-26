# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Delete Confirmed Purchase Lines',
    'summary': 'Let authorised buyers remove a line from a confirmed purchase '
               'order - safely, with its receipt updated and a full log.',
    'description': """
Delete Confirmed Purchase Lines
===============================
Odoo does not let you remove a line once a purchase order is confirmed, so a
cancelled item forces you to cancel the whole order. This module lets members
of a dedicated group delete such a line safely.

* A line can be deleted only when nothing has been received or billed for it
  and the order is not locked. The error message lists every blocked line.
* Its open receipt moves are cancelled, so the receipt no longer expects the
  goods.
* The deletion is logged on the purchase order and on the receipt (product,
  quantity, and the user as author of the note).
* The product of a line cannot be changed once goods have been received for it.

Behaves well:

* Billed lines can never be deleted, so a vendor bill always keeps its link to
  the order.
* Only the "Delete Confirmed Purchase Lines" group can do it; everyone else
  keeps Odoo's standard rule.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Purchase',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['purchase_stock'],
    'data': [
        'security/cl_purchase_line_control_security.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
