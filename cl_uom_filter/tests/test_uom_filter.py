# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests import TransactionCase, tagged

# model -> name of its unit of measure field
UNIT_FIELDS = {
    'sale.order.line': 'product_uom',
    'purchase.order.line': 'product_uom',
    'stock.move': 'product_uom',
    'mrp.production': 'product_uom_id',
    'account.move.line': 'product_uom_id',
}


@tagged('post_install', '-at_install')
class TestUomFilter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.dozen = cls.env.ref('uom.product_uom_dozen')
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.unit_category = cls.unit.category_id
        cls.product = cls.env['product.product'].create({
            'name': 'Filtered Units Product',
            'type': 'consu',
            'uom_id': cls.unit.id,
            'uom_po_id': cls.unit.id,
        })

    def _allow(self, units):
        self.product.product_tmpl_id.product_uom_ids = [(6, 0, units.ids)]

    # ------------------------------------------------------------------
    # The rule
    # ------------------------------------------------------------------

    def test_nothing_selected_means_standard_odoo(self):
        """Without a selection every unit of the product's category is offered,
        as in standard Odoo."""
        allowed = self.product._cl_get_allowed_uoms()
        self.assertEqual(allowed, self.unit_category.uom_ids)
        self.assertIn(self.dozen, allowed)
        self.assertNotIn(self.kg, allowed)

    def test_only_selected_units_are_offered(self):
        self._allow(self.dozen)
        self.assertEqual(self.product._cl_get_allowed_uoms(), self.dozen)
        self._allow(self.unit | self.dozen)
        self.assertEqual(self.product._cl_get_allowed_uoms(), self.unit | self.dozen)

    def test_units_of_another_category_are_ignored(self):
        self._allow(self.dozen | self.kg)
        self.assertEqual(self.product._cl_get_allowed_uoms(), self.dozen)
        # Only foreign units selected: fall back on the product's category
        # instead of offering nothing at all.
        self._allow(self.kg)
        self.assertEqual(self.product._cl_get_allowed_uoms(), self.unit_category.uom_ids)

    def test_no_product_no_unit(self):
        self.assertFalse(self.env['product.product']._cl_get_allowed_uoms())

    def test_selection_is_shared_by_the_variants(self):
        self._allow(self.dozen)
        self.assertEqual(self.product.product_uom_ids, self.dozen)
        self.assertEqual(self.product.product_tmpl_id.product_uom_ids, self.dozen)

    # ------------------------------------------------------------------
    # The five documents
    # ------------------------------------------------------------------

    def test_documents_offer_the_allowed_units(self):
        self._allow(self.unit | self.dozen)
        for model in UNIT_FIELDS:
            with self.subTest(model=model):
                record = self.env[model].new({'product_id': self.product.id})
                self.assertEqual(record.cl_allowed_uom_ids, self.unit | self.dozen)

    def test_documents_without_product_offer_nothing(self):
        for model in ('sale.order.line', 'account.move.line'):
            with self.subTest(model=model):
                self.assertFalse(self.env[model].new({}).cl_allowed_uom_ids)

    def test_unit_fields_are_filtered_on_the_allowed_units(self):
        for model, field_name in UNIT_FIELDS.items():
            with self.subTest(model=model):
                field = self.env[model]._fields[field_name]
                self.assertEqual(field.domain, "[('id', 'in', cl_allowed_uom_ids)]")
                # Only the filter changed: the field is still Odoo's own.
                self.assertEqual(field.comodel_name, 'uom.uom')
                self.assertTrue(field.store)

    def test_allowed_units_reach_the_sale_order_form(self):
        """The filter is evaluated by the web client, so the form must carry
        the allowed units of each line (Odoo adds the field by itself)."""
        self.env.user.groups_id |= self.env.ref('uom.group_uom')
        arch = self.env['sale.order'].get_view(view_type='form')['arch']
        self.assertIn('cl_allowed_uom_ids', arch)

    def test_saved_sale_line(self):
        """End to end on a real order: the line keeps Odoo's default unit and
        offers the selected ones."""
        self._allow(self.unit | self.dozen)
        order = self.env['sale.order'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Customer'}).id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 2})],
        })
        line = order.order_line
        self.assertEqual(line.product_uom, self.unit)
        self.assertEqual(line.cl_allowed_uom_ids, self.unit | self.dozen)
        line.product_uom = self.dozen
        self.assertEqual(line.product_uom, self.dozen)
        # The line follows a later change of the product's allowed units.
        self._allow(self.dozen)
        self.assertEqual(line.cl_allowed_uom_ids, self.dozen)
