# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Credit Note & Return Approval',
    'summary': 'Customer credit notes under control: a reason on every credit '
               'note, limits against the invoice, and goods returns that must '
               'be approved and received before the credit note is posted.',
    'description': """
Credit Note & Return Approval
=============================
Keeps customer credit notes honest and ties them to the goods coming back.

* **Credit note reasons** - a reason is chosen when a customer invoice is
  credited. Reasons can state that the goods must come back.
* **Limits against the invoice** - a credit note made from an invoice cannot
  credit a product that was not invoiced, more quantity than is left after the
  other credit notes, a higher unit price, or more than the invoice total.
  Everything that is wrong is listed in one message.
* **Return requests** - when the goods must come back, accounting requests the
  return from the draft credit note. A Return Approver approves or rejects it.
  Approving creates the return transfers from the original deliveries;
  rejecting creates nothing in the warehouse.
* **Posting waits for the goods** - such a credit note can only be posted once
  its request is approved and the goods are received, back orders included.
* **Returned Goods analysis** - quantity received and value credited by
  reason, product, category, customer and salesperson.

How it behaves:

* The checks run whenever a credit note is posted - the Confirm button,
  "Reverse and Create Invoice", automatic posting - not from one button only.
* Approval is a right, not a hidden button: approving, rejecting or forging
  the decision through the API is refused to anyone who is not a Return
  Approver, and a request cannot be moved to another credit note.
* The warehouse only ever sees approved returns. No new transfer state is
  added, so cancelling, back orders and uninstalling behave as in standard
  Odoo.
* Lines without a product are allowed; quantities and prices are compared in
  the product's unit of measure; services are never asked back.
* A return cannot bring back more than was delivered.
* The reason is asked for customer invoices only, not for vendor bills or
  journal entries reversed with the same wizard.
* Approvers get an activity, limited to the approvers of the company
  concerned; the person who asked is notified of the decision.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['account', 'sale_stock'],
    'data': [
        'security/return_security.xml',
        'security/ir.model.access.csv',
        'data/return_data.xml',
        'views/return_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
