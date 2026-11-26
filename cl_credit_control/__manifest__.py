# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Customer Credit Control',
    'summary': 'Block sales orders for customers with overdue invoices, over their '
               'credit limit or on credit hold, with an approve / reject workflow.',
    'description': """
Customer Credit Control
=======================
Stops a quotation from being confirmed when the customer is a credit risk, and
lets a Credit Manager approve or reject the exception.

A quotation is blocked when the customer:

* has invoices overdue by more than the allowed number of days
  (company setting, with an optional allowance per customer),
* would go over the credit limit with this order (uses Odoo's own credit limit), or
* has been put on credit hold by hand.

Blocked quotations show the reasons on the form. The salesperson requests
approval, Credit Managers get an activity, and they approve (the order is
confirmed) or reject with a reason. Everything is logged in the chatter.
A request that is no longer needed (customer cleared, order cancelled) is
withdrawn by itself.

Other points:

* Customers can be exempted from credit control. Only Credit Managers can
  change a customer's hold, exemption and allowance.
* An approval covers the approved amount only; if the order total grows, it
  must be approved again.
* All figures are worked out live and per company. There is no nightly job.
* Orders confirmed automatically (online payment, customer signature) are
  never dropped silently: they are either let through with a logged note or
  blocked with an error, depending on the setting.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'account',
        'mail',
    ],
    'data': [
        'security/credit_control_security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'wizard/credit_approval_request_views.xml',
        'wizard/credit_reject_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
