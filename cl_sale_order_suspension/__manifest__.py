# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Suspend Quotations',
    'summary': 'Park a quotation with a reason and a follow-up date; it cannot '
               'be confirmed or sent until it is resumed.',
    'description': """
Suspend Quotations
==================
Put a quotation on hold while something is being sorted out (a stock
question, a credit issue, a customer query) without cancelling it.

* "Suspend" asks for a reason and a follow-up date. A To-Do is scheduled for
  you on that date.
* A suspended quotation cannot be confirmed or emailed until it is resumed,
  and the customer cannot sign or pay it on the portal.
* "Resume" puts it back in the normal flow and closes the follow-up.
* Other quotations of the same customer show which of their quotations are
  suspended.
* Sales > Orders > Suspended Quotations lists them all.

Behaves well:

* Only members of the "Suspend Quotations" group can suspend, resume or
  cancel a suspended quotation; this is checked on the server, not only by
  hiding buttons.
* No new order state: Odoo's own statuses, buttons and rules are untouched.
* No scheduled job: the reminder is a normal activity with a due date.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale'],
    'data': [
        'security/cl_sale_order_suspension_security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'wizard/cl_sale_suspend_wizard_views.xml',
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
