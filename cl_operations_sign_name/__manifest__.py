# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Operations Sign Block',
    'summary': 'Name, date and signature boxes at the end of the Picking '
               'Operations and Batch Transfer printouts, per operation type.',
    'description': """
Operations Sign Block
=====================
Prints three boxes to fill in by hand - name, date and time, signature - at the
end of the Picking Operations and Batch Transfer documents, so the person who
hands over or receives the goods can sign the printout. Turned on per operation
type.

Behaves well:

* The block is part of **those two documents only**. The company document
  layout is not touched, so invoices, quotations, delivery slips and every other
  PDF stay exactly as they are, whatever layout the company uses.
* Only the operation types you choose print it; a batch follows its own
  operation type.
* The three boxes are never split over two pages.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['stock', 'stock_picking_batch'],
    'data': [
        'views/stock_picking_type_views.xml',
        'report/sign_block_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
