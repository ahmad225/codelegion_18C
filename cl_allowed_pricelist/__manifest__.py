# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Allowed Pricelists per Customer',
    'summary': "Restrict which pricelists can be chosen on a sales order to "
               "the ones allowed for the customer.",
    'description': """
Allowed Pricelists per Customer
===============================
Choose the pricelists a customer can be sold on. Quotations for that customer
only offer those pricelists, start on one of them, and refuse any other.

* **Allowed Pricelists** on the customer, kept on the company so that it holds
  for all its contacts. Empty means any pricelist.
* The Pricelist field of a quotation only offers the allowed pricelists, plus
  the pricelist set on the customer itself.
* A new quotation starts on an allowed pricelist, also when it is imported or
  created through the API.
* A server-side check refuses a pricelist that is not allowed, and says which
  ones are.

Behaves well:

* A customer without a list is not restricted.
* eCommerce orders and orders made by the system itself (connectors, scheduled
  jobs) are not checked, so online carts and integrations are never blocked.
* Works per company: pricelists of another company are ignored.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
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
