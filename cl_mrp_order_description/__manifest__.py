# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Manufacturing Order Description',
    'summary': 'Add a description to manufacturing orders and print it - and '
               'the shop floor note - on the Production Order PDF.',
    'description': """
Manufacturing Order Description
===============================
Give the shop floor the instructions that matter for this order.

* A **Description** field on the manufacturing order (e.g. print details,
  packing instructions, customer remarks).
* The description is printed on the **Production Order** PDF.
* Duplicated orders and backorders keep the description; orders can be searched
  by it.
* When Enterprise Shop Floor is installed, the MO's **shop floor note** is
  printed as well.

Behaves well:

* The field belongs to this module - no Studio field is needed - so the report
  prints on any database.
* Works with or without Enterprise Shop Floor: the note is only read when that
  module is installed.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Manufacturing/Manufacturing',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['mrp'],
    'data': [
        'views/mrp_production_views.xml',
        'report/mrp_production_report.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
