# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Previously Ordered Products',
    'summary': 'A customer portal page listing previously ordered products '
               'with one-click reorder.',
    'description': """
Previously Ordered Products
===========================
Adds a "Previously Ordered" page to the website customer portal, listing the
products a customer has bought before so they can order them again.

* Lists the products of the customer's latest confirmed orders, most recent
  first: image, name, reference, variant, last ordered date and quantity, and
  how many times it was ordered.
* Each product has its quantity and its own add-to-cart button; "Add all to
  cart" puts the whole list in the cart with the quantities shown.
* Search by product name or reference; a card on the portal home page.
* Everything goes through Odoo's standard cart, so prices, taxes, stock rules
  and promotions apply normally. No custom JavaScript.

Behaves well:

* Orders of the whole company are included (commercial partner), so B2B users
  see colleagues' orders too, not just their own contact's.
* Only products still sold on the website are listed; shipping lines, down
  payments and loyalty rewards are left out.
* Quantities are shown in the unit the shop sells the product in.
* Per website: number of past orders looked at, and the "Add all to cart"
  button on or off.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Website/eCommerce',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['website_sale'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
