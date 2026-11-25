# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from random import randint

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL
from odoo.tools.sql import column_exists, create_column, table_exists

# Keywords are only looked at for "contains" searches. Exact lookups (an
# import matching a product by its name, a barcode scan) are never widened.
CONTAINS_OPERATORS = ('ilike', 'like')

TEMPLATE_RELATION = 'cl_product_template_search_keyword_rel'
VARIANT_RELATION = 'cl_product_variant_search_keyword_rel'


def cl_precreate_keyword_text_column(cr, table, column):
    """Create the stored search-text column of ``table`` empty.

    Without this the ORM computes the new column record by record for every
    existing product when the module is installed, only to store "nothing".
    It is skipped as soon as a keyword is linked to a product, in which case
    the ORM computes the column as usual.
    """
    if column_exists(cr, table, column):
        return
    for relation in (TEMPLATE_RELATION, VARIANT_RELATION):
        if table_exists(cr, relation):
            cr.execute(SQL("SELECT 1 FROM %s LIMIT 1", SQL.identifier(relation)))
            if cr.fetchone():
                return
    create_column(cr, table, column, 'varchar')


class ClProductSearchKeyword(models.Model):
    _name = 'cl.product.search.keyword'
    _description = 'Product Search Keyword'
    _order = 'name, id'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Keyword', required=True)
    match_key = fields.Char(
        string='Comparison Key', compute='_compute_match_key', store=True, precompute=True,
        index=True, help='The keyword without extra spaces and in lower case, used to detect duplicates.')
    color = fields.Integer(string='Color', default=_default_color)
    template_ids = fields.Many2many(
        'product.template', TEMPLATE_RELATION, 'keyword_id', 'product_tmpl_id', string='Products')
    variant_ids = fields.Many2many(
        'product.product', VARIANT_RELATION, 'keyword_id', 'product_id', string='Variants',
        help='Variants that carry this keyword on top of the keywords of their product.')

    _sql_constraints = [
        ('match_key_unique', 'unique(match_key)',
         'This search keyword already exists. Upper and lower case are treated as the same.'),
    ]

    # ---- normalisation and duplicates ----

    @api.model
    def _clean_name(self, name):
        return ' '.join((name or '').split())

    @api.model
    def _key_of(self, name):
        return self._clean_name(name).casefold()

    @api.depends('name')
    def _compute_match_key(self):
        for keyword in self:
            keyword.match_key = self._key_of(keyword.name)

    def _check_names_are_free(self, names):
        """Refuse empty and already used keywords with a readable message,
        before anything is written (the SQL constraint is the safety net for
        two people creating the same keyword at the same moment)."""
        keys = [self._key_of(name) for name in names]
        if not all(keys):
            raise ValidationError(_("A search keyword cannot be empty."))
        if len(set(keys)) != len(keys):
            raise ValidationError(_("The same search keyword is given more than once."))
        twin = self.search([('match_key', 'in', keys), ('id', 'not in', self.ids)], limit=1)
        if twin:
            raise ValidationError(_(
                'The search keyword "%s" already exists. Upper and lower case are treated as the same.',
                twin.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self._clean_name(vals.get('name'))
        self.browse()._check_names_are_free([vals['name'] for vals in vals_list])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals = dict(vals, name=self._clean_name(vals['name']))
            # the same name on several keywords at once is a duplicate by itself
            self._check_names_are_free([vals['name']] * len(self))
        return super().write(vals)

    @api.model
    def name_create(self, name):
        # Typing an existing keyword in a tags field picks it instead of failing.
        existing = self.search([('match_key', '=', self._key_of(name))], limit=1)
        if existing:
            return existing.id, existing.display_name
        return super().name_create(name)

    # ---- used by the product models ----

    def _joined_text(self):
        """All keywords of the recordset as one line of text (False when none)."""
        return ' '.join(sorted(set(self.mapped('name')), key=str.casefold)) or False

    @api.model
    def _text_domain(self, text_field, operator, value):
        """Domain on a stored keyword text: every typed word must be found.

        :return: a domain, or None when keywords do not apply to this search
        """
        if operator not in CONTAINS_OPERATORS or not isinstance(value, str):
            return None
        return [(text_field, operator, word) for word in value.split()] or None
