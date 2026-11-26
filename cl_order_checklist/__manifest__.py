# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Order Checklist',
    'summary': 'Require a checklist to be completed before confirming a Sales '
               'Order or completing a Manufacturing Order.',
    'description': """
Order Checklist
===============
List the things to check on every Sales Order and every Manufacturing Order.
Each order gets its own Checklist tab; a sales order cannot be confirmed, and a
manufacturing order cannot be marked as done, until its required items are
ticked.

* One list of items for Sales and one for Manufacturing, per company or shared
  by all companies. An item is either required or a simple reminder.
* Each order carries its own checklist lines: tick them on the order and see
  who ticked what and when, a progress bar and how many required items are left.
* Ticks and unticks are logged in the chatter.
* An item added later is put on the orders that are still open.
* The check is made at the right moment: Sales Order confirmation and
  Manufacturing Order "Mark as Done" (starting and producing are never held up).

Behaves well:

* Orders confirmed without anybody at the screen (eCommerce orders, online
  payment, customer signature, subcontracting receipts) are never blocked; a
  note records what was not ticked.
* Ticking needs write access to the order and is checked on the server.
* Sales and Manufacturing managers manage the items of their own area.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['sale', 'mrp', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/cl_order_checklist_security.xml',
        'views/cl_order_checklist_item_views.xml',
        'views/sale_order_views.xml',
        'views/mrp_production_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
