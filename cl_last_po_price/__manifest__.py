# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Last Purchase Price',
    'summary': "Fill a purchase order line's price from the product's last "
               "confirmed purchase order.",
    'description': """
Last Purchase Price
===================
When you add a product to a purchase order, its unit price (and discount) are
filled from the last confirmed purchase order for that product, so buyers start
from what was actually paid last time instead of a blank or list price.

Options (per company):

* **On / off** - turn the behaviour on per company.
* **Last price taken from** - the same vendor only, or any vendor.
* **Applies to** - all products, or only products with variants.

Behaves well:

* Only drafts and sent RFQs are filled; confirmed and already-billed lines are
  left untouched.
* The last order is the one confirmed most recently.
* A price typed by the user on a saved line is kept when only the quantity
  changes, in the same cases standard Odoo keeps it. A price given explicitly
  when the line is created is never replaced.
* The last price is converted to the order's currency and unit of measure, so a
  price from a USD order is not copied as-is onto a EUR order.
* The last order's discount is carried over with the price.
* When a product has a last purchase price, it wins over the vendor price list.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Purchase',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['purchase'],
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
