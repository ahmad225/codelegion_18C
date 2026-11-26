# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Payment Unreconcile Warning',
    'summary': 'Ask for confirmation before removing a reconciled payment '
               'from an invoice or bill.',
    'description': """
Payment Unreconcile Warning
===========================
Removing a payment from an invoice is a single click in Odoo and is easy to do
by accident. This module adds a confirmation dialog before the payment is
unreconciled from the payment widget of the invoice.

* Works on customer invoices, vendor bills, credit notes and receipts.
* Names what is removed (payment, credit note or other entry), the amount and
  the document it is removed from, the right way round.
* Reminds the user that the payment itself is not cancelled.
* Purely a confirmation step - it never hides or disables the standard
  'Reset to Draft' button and keeps no extra state on the invoice.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['account'],
    'assets': {
        'web.assets_backend': [
            'cl_payment_unreconcile_warning/static/src/js/payment_unreconcile_warning.js',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
