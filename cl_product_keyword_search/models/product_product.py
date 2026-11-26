# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.osv import expression

from .cl_product_search_keyword import VARIANT_RELATION, cl_precreate_keyword_text_column


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cl_variant_keyword_ids = fields.Many2many(
        'cl.product.search.keyword', VARIANT_RELATION, 'product_id', 'keyword_id',
        string='Variant Search Keywords',
        help='Extra keywords for this variant only. The keywords of the product apply to all its variants.')
    cl_variant_search_text = fields.Char(
        string='Variant Search Keyword', compute='_compute_cl_variant_search_text', store=True,
        index='trigram',
        help='The keywords of the product and of this variant, as text.')

    def _auto_init(self):
        cl_precreate_keyword_text_column(self.env.cr, self._table, 'cl_variant_search_text')
        return super()._auto_init()

    @api.depends('cl_variant_keyword_ids.name', 'product_tmpl_id.cl_search_keyword_ids.name')
    def _compute_cl_variant_search_text(self):
        for product in self:
            keywords = product.product_tmpl_id.cl_search_keyword_ids | product.cl_variant_keyword_ids
            product.cl_variant_search_text = keywords._joined_text()

    # ---- backend search ----

    @api.model
    def _search_display_name(self, operator, value):
        # Reached when another document is searched by product (orders, moves,
        # invoices ...) and when product templates are searched by name.
        domain = super()._search_display_name(operator, value)
        keyword_domain = self.env['cl.product.search.keyword']._text_domain(
            'cl_variant_search_text', operator, value)
        if keyword_domain:
            domain = expression.OR([domain, keyword_domain])
        return domain

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Product drop-downs: core looks at reference, barcode and name in turn
        # and does not go through _search_display_name. Its results come first;
        # products found by keyword fill what is left of the list.
        found = super().name_search(name, args, operator, limit)
        keyword_domain = self.env['cl.product.search.keyword']._text_domain(
            'cl_variant_search_text', operator, name)
        room = limit - len(found) if limit else None
        if not keyword_domain or (room is not None and room <= 0):
            return found
        by_keyword = self.search_fetch(
            expression.AND([args or [], keyword_domain, [('id', 'not in', [row[0] for row in found])]]),
            ['display_name'], limit=room)
        return found + [(product.id, product.display_name) for product in by_keyword.sudo()]

    # ---- point of sale ----

    @api.model
    def _load_pos_data_fields(self, config_id):
        return [*super()._load_pos_data_fields(config_id), 'cl_variant_search_text']
