# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Compatibility - eCommerce',
    'summary': 'Block website checkout while the cart holds incompatible '
               'products, and tell the customer why.',
    'description': """
Product Compatibility - eCommerce
=================================
Companion of Product Compatibility for the online shop. Installed
automatically when both Product Compatibility and eCommerce are installed.

* Checkout, address and payment steps send the customer back to the cart while
  it holds incompatible products, and the Checkout button is disabled.
* The cart lists each mismatch and the compatible options (published products
  only); the notice follows the cart as quantities change.
* Payment is refused on the server for such a cart, express checkout included.

Done on the server through the standard cart checks - no custom checkout
scripts to break when Odoo updates.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Website/eCommerce',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['cl_product_compatibility', 'website_sale'],
    'data': [
        'views/website_sale_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
