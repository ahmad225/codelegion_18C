# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Review Notifications',
    'summary': 'Email your team as soon as a customer rates or reviews a '
               'product on the website.',
    'description': """
Product Review Notifications
============================
Know about new product reviews straight away, so you can thank happy customers
and respond quickly to unhappy ones.

* An email to the people you choose whenever a customer posts a product rating
  or review on the website - and when they edit it.
* Shows the product, customer, star rating and comment, with a link to the
  review.
* Ready to use: the email template is selected automatically on install; just
  pick the recipients.

Behaves well:

* Sent from the company's address, not the reviewer's.
* Per company: a product's own company is notified, otherwise the company of
  the website. Saving a review without changing it sends nothing.
* A broken email template never stops a customer from posting a review.
* Queued for the mail server instead of sent while the customer waits, so
  posting a review stays fast.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Website/eCommerce',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['website_sale', 'rating'],
    'data': [
        'data/mail_template_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': '_cl_set_default_rating_template',
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
