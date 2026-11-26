# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Compatibility',
    'summary': 'Stop products that do not fit together - such as a cup and '
               'the wrong-size lid - from being sold on the same order.',
    'description': """
Product Compatibility
=====================
Define which products go together and catch mismatches before the order is
confirmed.

* **Compatibility groups** - e.g. "Cups & Lids": the products that are checked
  against each other.
* **Fits With** on each product - e.g. 12oz Cup <-> 12oz Lid. A link always
  works both ways. Set it on the product, or on each variant.
* A warning on the quotation lists every mismatch and the compatible options.
* Users cannot confirm the order while a mismatch remains; a Sales Manager can
  override, and the override is logged in the chatter.
* Orders confirmed by the system or for the customer (online payment or
  signature) are never refused; the mismatches are logged on the order.
* With eCommerce installed, the companion module blocks checkout and payment
  until the cart is fixed and shows the reason on the cart page.

The rule: two products on an order that share a group, are not compatible, and
neither of which has a compatible partner elsewhere on the order, are flagged.
So an order with 12oz cups + 12oz lids + 16oz cups + 16oz lids passes, while
12oz cups + 16oz lids is caught.

Behaves well:

* The check is enforced on the server when confirming, not only shown.
* Mismatches are reported even when there is no compatible product to suggest.
* Nothing is stored on old orders, so editing a group never rewrites history.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
        'security/cl_product_compatibility_security.xml',
        'security/ir.model.access.csv',
        'views/cl_product_compatibility_group_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
