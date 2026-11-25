# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Packaging Measurements',
    'summary': 'Record the length, width, height and gross weight of product '
               'packagings and show them on sales order lines.',
    'description': """
Product Packaging Measurements
==============================
Record the physical size and gross weight of each product packaging.

* Length, width, height and gross weight on every product packaging, in the
  packaging list (also inside the product form) and in the packaging form.
* Units are set per company in the Inventory settings. By default every
  packaging uses the company units; optionally each packaging can use its own
  dimension unit and / or weight unit.
* A readable summary ("120.00 x 80.00 x 100.00 cm", "25.00 kg") is shown on the
  packaging and, as two optional columns, on sales order lines.

Behaves well:

* On a sales order the figures follow the packaging while the order is a
  quotation, and stay as they were once it is confirmed. They are taken again
  whenever the packaging of the line changes, including when Odoo changes it
  because the quantity changed or the order comes from the website or an import.
* When the company imposes its units, a packaging cannot keep another unit,
  whatever the way it is created or edited.
* Dimension units are limited to length units and weight units to weight units.
* Existing order lines are not recomputed when the module is installed.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['stock', 'sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/product_packaging_views.xml',
        'views/sale_order_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
