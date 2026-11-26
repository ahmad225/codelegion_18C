# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Customer Artwork Approval',
    'summary': 'Customer logos and print artwork per customer and product: designer proofs, '
               'rework and approval, reused on the next order and sent to manufacturing.',
    'description': """
Customer Artwork Approval
=========================
Printing a customer's logo on a product needs an approved design, and the same
design should be used again on the next order without anyone hunting for files.

* Tick "Requires Artwork" on the products you brand for customers.
* On the quotation, the Artwork tab lists the lines that need artwork and what
  each one has. Click "Request Artwork" on a line, upload the customer's logo,
  pick a designer and click "Send to Designer".
* The designer gets an activity, uploads the proof (any file, plus an optional
  preview image) and clicks "Proof Ready". The salesperson gets a review
  activity.
* The salesperson approves the proof or requests rework with a comment; the
  designer gets a new activity with that comment. Every proof is kept in the
  artwork's chatter.
* Approved artwork is stored per customer (company) and product, with a version
  number. The next order for the same customer and product uses it
  automatically; pick an older version on the line if the customer wants it,
  or click "New Version" on the line to start a changed design from it.
* The approved proof is shown on the customer, the product and the
  manufacturing order, and attached to manufacturing orders created from the
  order.
* Settings: block confirming orders whose artwork is not approved (default on)
  and block starting or producing manufacturing orders until it is (default off).
* Artwork per variant is possible; it is preferred over artwork for the whole
  product.

Behaves well:

* Only lines whose product requires artwork are checked. Artwork on other
  products never blocks a confirmation.
* Customers who accept and pay online are never blocked; a note is posted on
  the order instead.
* Approval needs a proof file and can only be given by sales users, never by
  closing an activity. Approved artwork cannot be changed: create a new version.
* Approved artwork cannot be deleted (archive it instead), and deleting a
  quotation, customer or product never deletes artwork.
* Artwork of a contact person's company is found on the order and on the
  manufacturing order alike.
* Files are stored as private attachments: only users who can read the
  artwork can open them. Portal users have no access.
  The copy attached to a manufacturing order (a setting, on by default) can be
  opened by whoever can open that order.
* Designers are plain users in the Designer group; no HR, Project or
  Timesheets app is needed.
* The notes of the workflow are posted for users without an email address too.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['sale_mrp'],
    'data': [
        'security/cl_sale_artwork_approval_security.xml',
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'wizard/cl_artwork_rework_wizard_views.xml',
        'views/cl_artwork_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/mrp_production_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
