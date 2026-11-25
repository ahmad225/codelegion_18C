# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductKeywordSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Keyword = cls.env['cl.product.search.keyword']
        cls.Template = cls.env['product.template']
        cls.Product = cls.env['product.product']
        cls.azure = cls.Keyword.create({'name': 'azure'})
        cls.travel = cls.Keyword.create({'name': 'travel'})
        cls.volume = cls.Keyword.create({'name': '250ml'})
        cls.mug = cls.Template.create({
            'name': 'Mug', 'cl_search_keyword_ids': [(6, 0, (cls.azure | cls.travel).ids)]})
        cls.bottle = cls.Template.create({
            'name': 'Bottle', 'barcode': '250', 'cl_search_keyword_ids': [(6, 0, cls.volume.ids)]})
        cls.plate = cls.Template.create({'name': 'Plate'})

    def _names(self, model, text, **kwargs):
        return [row[0] for row in model.name_search(text, **kwargs)]

    # ---- the stored text ----

    def test_text_holds_product_and_variant_keywords(self):
        variant = self.mug.product_variant_id
        self.assertEqual(self.mug.cl_keyword_search_text, 'azure travel')
        self.assertEqual(variant.cl_variant_search_text, 'azure travel')
        self.assertFalse(self.plate.cl_keyword_search_text)
        # a keyword of the variant only: on the variant, and on the product that owns it
        variant.cl_variant_keyword_ids = self.volume
        self.assertEqual(variant.cl_variant_search_text, '250ml azure travel')
        self.assertEqual(self.mug.cl_keyword_search_text, '250ml azure travel')

    def test_text_follows_rename_removal_and_keyword_side_edits(self):
        self.azure.name = 'Sky Blue'
        self.assertEqual(self.mug.cl_keyword_search_text, 'Sky Blue travel')
        self.assertEqual(self.mug.product_variant_id.cl_variant_search_text, 'Sky Blue travel')
        self.travel.unlink()
        self.assertEqual(self.mug.cl_keyword_search_text, 'Sky Blue')
        # linking products from the keyword list
        self.volume.template_ids = [(4, self.plate.id)]
        self.assertEqual(self.plate.cl_keyword_search_text, '250ml')
        self.assertEqual(self.plate.product_variant_id.cl_variant_search_text, '250ml')

    # ---- backend ----

    def test_variant_dropdown_finds_by_keyword(self):
        self.assertIn(self.mug.product_variant_id.id, self._names(self.Product, 'azure'))
        self.assertIn(self.mug.product_variant_id.id, self._names(self.Product, 'AZU'))
        self.assertNotIn(self.plate.product_variant_id.id, self._names(self.Product, 'azure'))

    def test_product_dropdown_finds_by_keyword(self):
        self.assertIn(self.mug.id, self._names(self.Template, 'azure'))
        self.assertNotIn(self.plate.id, self._names(self.Template, 'azure'))

    def test_every_word_must_be_found(self):
        self.assertIn(self.mug.product_variant_id.id, self._names(self.Product, 'travel azure'))
        self.assertNotIn(self.mug.product_variant_id.id, self._names(self.Product, 'azure 250ml'))

    def test_core_results_come_first_and_limit_is_kept(self):
        named = self.Template.create({'name': 'Azure Vase'})
        found = self._names(self.Product, 'azure')
        self.assertEqual(found[0], named.product_variant_id.id)
        self.assertIn(self.mug.product_variant_id.id, found)
        self.assertEqual(len(found), len(set(found)))
        self.assertEqual(self._names(self.Product, 'azure', limit=1), [named.product_variant_id.id])

    def test_dropdown_domain_is_respected(self):
        found = self._names(self.Product, 'azure', args=[('id', '!=', self.mug.product_variant_id.id)])
        self.assertNotIn(self.mug.product_variant_id.id, found)

    def test_other_documents_can_be_searched_by_product_keyword(self):
        # what a search such as [('product_id', 'ilike', 'azure')] turns into
        self.assertIn(self.mug.product_variant_id,
                      self.Product.search([('display_name', 'ilike', 'azure')]))
        self.assertIn(self.mug, self.Template.search([('display_name', 'ilike', 'azure')]))

    def test_exact_searches_are_not_widened(self):
        # the keyword "250ml" contains "250"; the barcode lookup stays exact
        self.assertEqual(self.Product.search([('barcode', '=', '250')]), self.bottle.product_variant_id)
        self.assertFalse(self.Product.search([('barcode', '=', 'azure')]))
        # an import matches products by exact name
        self.assertFalse(self._names(self.Product, 'azure', operator='='))
        self.assertFalse(self._names(self.Template, 'azure', operator='='))
        self.assertNotIn(self.mug.product_variant_id,
                         self.Product.search([('display_name', '=', 'azure')]))
        # "does not contain" must not start returning the product either way
        self.assertIn(self.mug.product_variant_id,
                      self.Product.search([('display_name', 'not ilike', 'azure')]))

    # ---- web shop and point of sale ----

    def test_web_shop_searches_the_keyword_text(self):
        website = self.env['website'].search([], limit=1)
        options = {'displayImage': False, 'displayDescription': False,
                   'displayExtraLink': False, 'displayDetail': False}
        detail = self.Template._search_get_detail(website, 'name asc', options)
        self.assertIn('cl_keyword_search_text', detail['search_fields'])
        domain = self.Template._search_build_domain(
            detail['base_domain'], 'travel azure', detail['search_fields'])
        self.mug.is_published = True
        self.assertIn(self.mug, self.Template.search(domain))

    def test_point_of_sale_loads_the_keyword_text(self):
        config = self.env['pos.config'].search([], limit=1)
        self.assertIn('cl_variant_search_text', self.Product._load_pos_data_fields(config.id))

    # ---- keywords ----

    def test_keyword_is_cleaned_and_unique(self):
        self.assertEqual(self.Keyword.create({'name': '  hot   drinks '}).name, 'hot drinks')
        with self.assertRaises(ValidationError):
            self.Keyword.create({'name': 'AZURE'})
        with self.assertRaises(ValidationError):
            self.Keyword.create({'name': ' azure  '})
        with self.assertRaises(ValidationError):
            self.Keyword.create([{'name': 'twice'}, {'name': 'Twice'}])
        with self.assertRaises(ValidationError):
            self.travel.name = 'Azure'
        with self.assertRaises(ValidationError):
            self.Keyword.create({'name': '   '})
        # changing only the case of a keyword is not a duplicate of itself
        self.azure.name = 'Azure'
        self.assertEqual(self.azure.name, 'Azure')

    def test_typing_an_existing_keyword_picks_it(self):
        keyword_id, _label = self.Keyword.name_create('  AZURE ')
        self.assertEqual(keyword_id, self.azure.id)
        new_id, _label = self.Keyword.name_create('brand new')
        self.assertNotIn(new_id, (self.azure | self.travel | self.volume).ids)
