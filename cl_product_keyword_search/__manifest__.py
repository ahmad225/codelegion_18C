# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Product Keyword Search',
    'summary': 'Find products by your own keywords - nicknames, old references, '
               'competitor names - in the backend, the web shop and the POS.',
    'description': """
Product Keyword Search
======================
People rarely search for a product by the name on its form. Give each product
the other words it is known by and it is found by them wherever a product is
searched.

* **Search keywords** on the product (General Information tab), shared by all
  its variants, plus extra keywords on a single variant when needed.
* **Backend**: product drop-downs on orders, invoices, transfers and so on,
  searches of other documents by product, and a "Search Keyword" field and a
  "Without Search Keywords" filter in the product lists.
* **Web shop**: the shop search and its search-as-you-type suggestions.
* **Point of Sale**: the product search box.
* **Several words**: every typed word has to be found.
* **Keyword list** under Sales > Configuration > Products > Search Keywords,
  to rename or colour a keyword and see where it is used.

Behaves well:

* Exact lookups are left alone. A barcode scan, an import matching products by
  name or any other "equals" search never returns extra products.
* No extra query per search: the keywords of a product are kept in one indexed
  text column, and a search is one more condition on it.
* The Point of Sale search is extended, not replaced: Odoo's own results are
  never changed.
* The same keyword cannot exist twice (upper/lower case and extra spaces are
  ignored); typing an existing one in a product simply picks it.
* Quick to install on large catalogues: nothing is computed per product at
  install time.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['product', 'point_of_sale', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/cl_product_search_keyword_views.xml',
        'views/product_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'cl_product_keyword_search/static/src/pos/keyword_search.js',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
