# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Auto-Apply Promotions on Quotations',
    'summary': 'Apply eligible automatic promotions on quotations as the lines '
               'change, warn about expiring promotions and show the customer '
               'their total promotion savings.',
    'description': """
Auto-Apply Promotions on Quotations
===================================
Salespeople no longer have to click "Reward" on every quotation: eligible
automatic promotions are applied as soon as the quotation is created or its
lines change.

* **Automatic promotions only**: promotions and Buy X Get Y programs that
  trigger automatically. Loyalty cards, eWallets, gift cards, coupons and
  discount codes are never spent or applied without the salesperson.
* **Free products** are added for every eligible promotion.
* **Discounts**: a single eligible discount is applied; when several compete,
  nothing is picked behind your back - a banner asks the salesperson to choose
  one in the standard reward wizard.
* **Manual rewards are safe**: coupons, discount codes and rewards the
  salesperson chose are never removed by the module. Only the lines it added
  itself are recomputed.
* **Removed promotions stay removed**: an automatic promotion line the
  salesperson deletes is not added again while the quotation keeps earning
  it. If the quotation stops earning it and earns it again later, it is
  offered again.
* **End notice**: one banner on the quotation when a promotion used on it
  ends soon (amber) or has already ended (red).
* **Promotion savings** shown under the totals of the quotation and the
  invoice, and on both PDFs. eWallet and gift card payments are not counted;
  each invoice shows only the savings on its own lines.
* The quotation PDF lists the promotions applied, with their end date while
  the quotation is still open.
* A short log note in the chatter lists the promotions added or removed.

Turn it on per company in Sales > Configuration > Settings > Pricing, where
the length of the end notice is set too.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['sale_loyalty'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/sale_order_report_templates.xml',
        'report/account_invoice_report_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
