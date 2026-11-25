# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Click & Collect PIN',
    'summary': 'Secure collection PIN for click & collect orders: emailed to '
               'the customer, verified at the counter before the delivery '
               'can be validated.',
    'description': """
Click & Collect PIN
===================
Make sure the right person collects the goods. When a customer picks up an
order in store, the warehouse validates the delivery only after the customer
gives the PIN that was emailed to them.

* **Collection methods**: tick "Customer Collection" on any delivery method.
* **PIN issued when the goods are ready**: when the pick (or pack) transfer of
  the order is done, or on confirmation for one-step warehouses.
* **Emailed to the customer** - the only place the PIN ever appears.
* **Verified at validation**: validating the delivery asks for the PIN; the
  delivery cannot be done without it, from any screen or API.
* **Every delivery and backorder** is verified on its own; a PIN is used once.
* **Brute-force protection**: wrong attempts are counted and the PIN locks
  after a configurable number of tries; only an Inventory Administrator can
  unlock it by issuing a new PIN.
* **Send New PIN** for sales users when a customer lost the email.
* **Audit log** of every PIN event, under Inventory > Reporting.

Behaves well:

* Only a salted hash of the PIN is stored - never the PIN itself. It is not
  shown on any screen, chatter message or log.
* Changing the delivery method, resetting the order to quotation, cancelling
  it or completing every collection clears or expires the PIN.
* The PIN check cannot be switched off from the warehouse: only sales users
  and Inventory Administrators can change the delivery method of an order that
  is waiting for collection (only an Inventory Administrator while the PIN is
  locked), and an open collection delivery cannot be detached from its order.
* The PIN email goes to the customer only, whatever recipients are added to
  the email template.
* Works for counter staff without an email address and for users limited to
  their own sales orders.
* No restriction is added to orders that are not collected by the customer.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_stock', 'delivery', 'mail'],
    'data': [
        'security/cl_collection_pin_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'wizard/cl_collection_pin_verify_views.xml',
        'views/cl_collection_pin_log_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
