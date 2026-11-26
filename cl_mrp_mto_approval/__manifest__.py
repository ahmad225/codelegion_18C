# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Make-to-Order Approval',
    'summary': 'Manufacturing orders created from sales orders wait for a '
               'Manufacturing Coordinator\'s approval before production starts. '
               'Salespeople follow the production of their sales orders read-only.',
    'description': """
Make-to-Order Approval
======================
A confirmed sales order with a make-to-order product creates its manufacturing
order straight away. This module makes sure nobody starts producing it before a
Manufacturing Coordinator has checked the job.

* Manufacturing orders created by the sales order procurement (make-to-order)
  are marked "Waiting Approval". Sub-assembly orders created for them follow
  the same approval.
* Every Manufacturing Coordinator of the company gets an activity. When one of
  them decides, the activities of the others are closed too.
* Coordinators (and administrators) approve, or reject with a reason. On
  rejection the salesperson is notified on the sales order, and the order is
  either kept on hold or cancelled, as the coordinator chooses. Production can
  send a rejected order for approval again.
* Until it is approved the order cannot be planned, started, produced, marked
  done or merged, and its work orders cannot be started or finished. Everything
  else (components, reservation, edits, splitting, cancellation) works as usual.
* Switch it on or off per company in Manufacturing settings.
* Manufacturing > Operations > To Approve lists the waiting orders; several
  can be approved at once from the list.
* The group "See Manufacturing of Sales Orders (read-only)" gives salespeople a
  Manufacturing button on the sales orders they can open (their own orders with
  "Own Documents Only"): they see the manufacturing and work orders of that
  order and can never change them.

Behaves well:

* No new manufacturing order state: Odoo's own state machine, reservation and
  other modules keep working. Approval is a separate flag checked by Python
  guards on the planning, start, produce and mark-done paths, so the API cannot
  bypass it either.
* The sales link is taken from the procurement itself (sales order line,
  destination move, procurement group), never from the Source text. Manual
  orders and orders from reordering rules are never affected. Sub-assemblies
  are recognised in 1, 2 and 3 step manufacturing.
* Backorders and splits of an approved order stay approved; splits of a waiting
  order stay waiting. Demand of different sales orders is never merged into one
  waiting order.
* Approval activities use their own activity type, so they are closed reliably
  whatever the user's language.
* Reading manufacturing orders is not restricted for salespeople (Odoo already
  allows it and its Forecast report needs it); writing is blocked by record
  rules, not by hidden buttons.
* Only depends on Odoo Community apps (sale_mrp). No JavaScript.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Manufacturing/Manufacturing',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['sale_mrp'],
    'data': [
        'security/cl_mrp_mto_approval_security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'wizard/cl_mrp_mto_reject_wizard_views.xml',
        'views/mrp_production_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'post_init_hook': 'cl_post_init_link_sale_orders',
    'installable': True,
    'application': False,
    'auto_install': False,
}
