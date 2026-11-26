# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Stale Quotation Approval',
    'summary': 'Quotations left untouched for too long need a manager\'s '
               'approval before they can be confirmed.',
    'description': """
Stale Quotation Approval
========================
Prices, stock and terms change. A quotation nobody has worked on for weeks
should be reviewed before it becomes an order.

* Set the number of days of inactivity in Sales settings (default 14, 0 = off).
* When staff confirm a quotation that has been inactive for longer, it is not
  confirmed: it goes to "Pending Approval" and every approver gets an activity.
* Approvers approve or reject it; once approved it can be confirmed. The
  approval counts as activity: left alone again for too long, the quotation
  needs a new approval.
* While pending, only approvers can change its customer, lines, prices or terms.
* Sales > Orders > Quotations to Approve lists the waiting quotations.

What counts as activity: changes to the quotation (customer, lines, prices,
terms, dates, notes) and messages to or from the customer. Internal notes and
automatic tracking do not reset the clock.

Behaves well:

* Confirming several quotations at once confirms the fresh ones and sends only
  the stale ones for approval.
* Online acceptance, signature and payment by the customer are never blocked;
  they close a pending request by themselves, as does a confirmation by an
  approver.
* The approval status and last-activity date cannot be set by hand, import or
  API by non-approvers.
* No new order state and no changes to Odoo's own read-only rules.
* No scheduled job: the check happens when someone clicks Confirm.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['sale'],
    'data': [
        'security/cl_quotation_inactivity_approval_security.xml',
        'data/mail_activity_type_data.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
