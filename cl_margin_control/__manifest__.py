# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Sales Margin Control',
    'summary': 'Warn on low-margin sales order lines and orders, and require '
               'approval below a margin floor before confirmation.',
    'description': """
Sales Margin Control
====================
Keeps an eye on the margin of your sales orders, using Odoo's standard margin
figures (Sales Margin).

* **Line margin warnings** - a Margin % column on the order lines, highlighted
  when the line margin falls below a threshold.
* **Order margin warnings** - a banner when the whole order's margin is below a
  threshold.
* **Margin floor** - below a set margin, the order cannot be confirmed
  until a margin approver approves it. Approvers are the members of the group
  chosen in the settings, or the Sales Administrators when none is chosen. They
  get a Margin Approval activity and a Sales > Orders > Margin Approvals list,
  and the salesperson is notified of the decision.

Behaves well:

* Warnings fire when the margin is **low** (below the threshold), which is what
  you actually want to catch.
* Confirming several orders at once handles each one: those below the floor are
  sent for approval, the rest are confirmed.
* No new order state and no edit-locks, so chatter, messages and activities on a
  pending order keep working.
* Approval is computed live from company settings, so quotations created before
  installing the app are covered too.
* An approval covers the approved margin: if the margin drops afterwards, or
  the order is cancelled and reopened, it must be approved again.
* A request that is no longer needed (margin fixed, order cancelled) is
  withdrawn by itself, and only the app's own activities are closed.
* Orders confirmed automatically (online payment, customer signature,
  eCommerce) are let through with a logged note, or held for approval,
  depending on the setting.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'sale_margin'],
    'data': [
        'data/mail_activity_type_data.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
