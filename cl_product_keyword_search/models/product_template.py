# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.osv import expression

from .cl_product_search_keyword import TEMPLATE_RELATION, cl_precreate_keyword_text_column


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cl_search_keyword_ids = fields.Many2many(
        'cl.product.search.keyword', TEMPLATE_RELATION, 'product_tmpl_id', 'keyword_id',
        string='Search Keywords',
        help='Other words people use for this product. Searching for one of them finds the product '
             'in the backend, in the web shop and in the Point of Sale.')
    # What the searches actually look at: one indexed column on the product,
    # so that a search costs one more condition and no extra query.
    cl_keyword_search_text = fields.Char(
        string='Search Keyword', compute='_compute_cl_keyword_search_text', store=True,
        index='trigram',
        help='The keywords of the product and of all its variants, as text.')

    def _auto_init(self):
        cl_precreate_keyword_text_column(self.env.cr, self._table, 'cl_keyword_search_text')
        return super()._auto_init()

    @api.depends('cl_search_keyword_ids.name', 'product_variant_ids.cl_variant_keyword_ids.name')
    def _compute_cl_keyword_search_text(self):
        for template in self:
            keywords = template.cl_search_keyword_ids | template.product_variant_ids.cl_variant_keyword_ids
            template.cl_keyword_search_text = keywords._joined_text()

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        keyword_domain = self.env['cl.product.search.keyword']._text_domain(
            'cl_keyword_search_text', operator, value)
        if keyword_domain:
            domain = expression.OR([domain, keyword_domain])
        return domain

    @api.model
    def _search_get_detail(self, website, order, options):
        # Web shop search (and its "did you mean" correction) looks in the
        # fields listed here; the keyword text is one more of them.
        detail = super()._search_get_detail(website, order, options)
        detail['search_fields'].append('cl_keyword_search_text')
        return detail
