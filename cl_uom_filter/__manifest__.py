# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Allowed Units Filter',
    'summary': 'Select the allowed units on each product; only those are offered in '
               'Sales, Purchase, Inventory, Manufacturing and Accounting.',
    'description': """
Product Allowed Units Filter
============================
Adds an "Allowed Units" field on the product form (General Information tab).
The unit field on the following documents then offers ONLY the units selected
there:

* Sales order lines
* Purchase order lines
* Stock moves (transfers, and the components / finished moves of manufacturing orders)
* Manufacturing orders
* Invoice and bill lines

If a product has no units selected, the standard Odoo behaviour applies
(every unit of the product's unit category is offered).

The default unit proposed by Odoo on a new line is not changed, so include the
product's own unit and purchase unit in its allowed units.

This module is standalone and needs no other app-store module.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.2.0.2',
    'license': 'LGPL-3',
    'depends': [
        'product',
        'uom',
        'sale',
        'purchase',
        'stock',
        'mrp',
        'account',
    ],
    'data': [
        'views/product_template_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
