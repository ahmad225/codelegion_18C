# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Manufacturing to Sales Handover',
    'summary': 'Keep sales in step with production: delivery dates follow the '
               'manufacturing orders, the salesperson is told when goods are handed '
               'over, event dates reach production and customers hear when their '
               'order is ready for collection.',
    'description': """
Manufacturing to Sales Handover
===============================
Made-to-order goods pass from production to the warehouse and then to the
customer. This module keeps the sales order, the salesperson and the customer
informed at every step, without phone calls between factory and sales.

* Delivery date from manufacturing: the sales order shows when its
  manufacturing orders will be (or were) finished. Its Delivery Date can follow
  the planned end of the manufacturing orders, or be set when they are done.
  With several manufacturing orders the latest one counts.
* Agreed dates are respected: a Delivery Date entered by hand is the date agreed
  with the customer. By default it is never moved; when production will finish
  later, the salesperson gets a note. Optionally the agreed date is moved to the
  later date, always with a note to the salesperson. Agreed dates are never
  moved earlier.
* Hand over to warehouse: a button on finished manufacturing orders. When every
  manufacturing order of the sales order has been handed over, the salesperson
  gets a "Ready for Delivery" activity. Managers can undo a handover. Both are
  done with buttons only: the handover fields cannot be edited or imported.
* Sales > Orders > Ready for Delivery lists handed-over orders not yet delivered.
* Event date: an optional customer event date and note on the sales order. They
  are shown on its manufacturing orders (also sub-assemblies, at any level) and in
  their list,
  with a warning when production is planned to finish after the event.
* Ready for Collection: tick "Customer Collection" on a delivery method. When the
  customer's delivery order is ready (all goods reserved, previous steps done),
  the customer gets a "Ready for Collection" email, once per delivery order and
  once per backorder, sent in the name of the salesperson.
* Collection reminders: a daily job reminds the customer every few days, up to a
  maximum, and stops as soon as the delivery order is done or cancelled.
* Every part can be switched on or off per company in Manufacturing settings.

Behaves well:

* Sales users can change the event date of their orders: the manufacturing
  orders are updated by the system, no manufacturing rights needed.
* Updates on the other document (sales order, activities) are done by the system
  after checking the user may change the manufacturing order.
* One link from manufacturing order to sales order (sales line, procurement
  group, or the moves it feeds), used everywhere.
* Emails are queued, never sent in the middle of a validation. The reminder job
  works in batches, isolates failures and never sends the same reminder twice.
* No new security groups, no record rules, no changes to Odoo's access rights.
* The email templates are ready to use after install and can be edited in
  Settings > Technical > Email Templates.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Manufacturing/Manufacturing',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['sale_mrp', 'stock_delivery'],
    'data': [
        'data/mail_activity_type_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/mrp_production_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/delivery_carrier_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
