# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Incoming Purchases on Product',
    'summary': 'See the open purchase order lines still to be received, '
               'directly on the product form.',
    'description': """
Incoming Purchases on Product
=============================
Answer "is more of this on the way?" without leaving the product.

* An **Incoming** smart button and an **Incoming Purchases** tab on the product
  (template and variant) list every confirmed purchase order line that still
  has an open receipt: vendor, order, expected arrival, ordered / received /
  quantity still to receive and receipt progress (Nothing Received / Partly
  Received),
  sorted by expected arrival.
* Works for all goods, storable or not, and for products bought as a kit.
* Purchase users open the purchase order from the line in one click.

Behaves well:

* A line is listed only while a receipt is actually still open, so cancelled
  receipts and lines closed without a backorder drop off by themselves - no
  manual "dismiss" step.
* Visible to Purchase users and Inventory users, who can already read purchase
  order lines in standard Odoo: it grants no extra access. Prices and the link
  to the order are shown to Purchase users only.
* All products on the page are looked up with a single query.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Purchase',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['purchase_stock'],
    'data': [
        'views/product_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
