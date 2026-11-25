# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestPackagingMeasurements(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.cm = cls.env.ref('uom.product_uom_cm')
        cls.mm = cls.env.ref('uom.product_uom_millimeter')
        cls.meter = cls.env.ref('uom.product_uom_meter')
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.company.write({
            'cl_packaging_length_uom_id': cls.cm.id,
            'cl_packaging_length_uom_free': False,
            'cl_packaging_weight_uom_id': cls.kg.id,
            'cl_packaging_weight_uom_free': False,
        })
        cls.product = cls.env['product.product'].create(
            {'name': 'Boxed', 'type': 'consu'})
        cls.packaging = cls.env['product.packaging'].create({
            'name': 'Carton', 'product_id': cls.product.id, 'qty': 10,
            'cl_length': 120.0, 'cl_width': 80.0, 'cl_height': 100.0,
            'cl_gross_weight': 25.0})
        cls.customer = cls.env['res.partner'].create({'name': 'Customer'})

    def _order(self, qty, packaging=None):
        line = {'product_id': self.product.id, 'product_uom_qty': qty}
        if packaging:
            line['product_packaging_id'] = packaging.id
        return self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, line)],
        })

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def test_labels(self):
        dimensions = self.packaging.cl_dimensions
        for part in ('120', '80', '100', ' x '):
            self.assertIn(part, dimensions)
        self.assertTrue(dimensions.endswith(self.cm.name))
        self.assertIn('25', self.packaging.cl_gross_weight_label)
        self.assertTrue(self.packaging.cl_gross_weight_label.endswith(self.kg.name))

    def test_labels_of_partial_or_missing_measurements(self):
        self.packaging.write({'cl_width': 0.0, 'cl_height': 0.0, 'cl_gross_weight': 0.0})
        self.assertIn('120', self.packaging.cl_dimensions)
        self.assertIn('-', self.packaging.cl_dimensions)
        self.assertFalse(self.packaging.cl_gross_weight_label)
        self.packaging.cl_length = 0.0
        self.assertFalse(self.packaging.cl_dimensions)

    def test_negative_measurements_are_refused(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.packaging.cl_length = -1.0
            self.packaging.flush_recordset()

    # ------------------------------------------------------------------
    # Units
    # ------------------------------------------------------------------

    def test_company_unit_is_imposed_by_default(self):
        self.assertEqual(self.packaging.cl_length_uom_id, self.cm)
        self.assertEqual(self.packaging.cl_weight_uom_id, self.kg)
        self.assertTrue(self.packaging.cl_length_uom_locked)
        # Even a direct write cannot give the packaging another unit.
        self.packaging.cl_length_uom_id = self.mm
        self.assertEqual(self.packaging.cl_length_uom_id, self.cm)

    def test_changing_the_company_unit_updates_packagings(self):
        self.company.cl_packaging_length_uom_id = self.mm
        self.assertEqual(self.packaging.cl_length_uom_id, self.mm)
        self.assertTrue(self.packaging.cl_dimensions.endswith(self.mm.name))

    def test_own_unit_per_packaging(self):
        self.company.cl_packaging_length_uom_free = True
        self.packaging.invalidate_recordset(['cl_length_uom_locked', 'cl_weight_uom_locked'])
        self.assertFalse(self.packaging.cl_length_uom_locked)
        self.assertTrue(self.packaging.cl_weight_uom_locked, "weight is a separate switch")
        self.packaging.cl_length_uom_id = self.mm
        self.assertEqual(self.packaging.cl_length_uom_id, self.mm)
        # The company unit is then only the default of new packagings.
        self.company.cl_packaging_length_uom_id = self.meter
        self.assertEqual(self.packaging.cl_length_uom_id, self.mm)
        new = self.env['product.packaging'].create({
            'name': 'Pallet', 'product_id': self.product.id, 'qty': 100})
        self.assertEqual(new.cl_length_uom_id, self.meter)
        # Switching the option off brings every packaging back to the company unit.
        self.company.cl_packaging_length_uom_free = False
        self.assertEqual(self.packaging.cl_length_uom_id, self.meter)

    # ------------------------------------------------------------------
    # Sales order lines
    # ------------------------------------------------------------------

    def test_sale_line_shows_packaging_measurements(self):
        line = self._order(10, self.packaging).order_line
        self.assertEqual(line.cl_packaging_dimensions, self.packaging.cl_dimensions)
        self.assertEqual(line.cl_packaging_weight, self.packaging.cl_gross_weight_label)

    def test_packaging_suggested_by_odoo_is_covered(self):
        """Odoo picks the packaging itself from the quantity; the measurements
        must follow without the packaging being written explicitly."""
        line = self._order(10).order_line
        self.assertEqual(line.product_packaging_id, self.packaging)
        self.assertEqual(line.cl_packaging_dimensions, self.packaging.cl_dimensions)
        line.product_packaging_id = False
        self.assertFalse(line.cl_packaging_dimensions)
        self.assertFalse(line.cl_packaging_weight)

    def test_quotation_follows_packaging_confirmed_order_does_not(self):
        order = self._order(10, self.packaging)
        line = order.order_line
        self.packaging.cl_length = 150.0
        self.assertIn('150', line.cl_packaging_dimensions)
        order.action_confirm()
        before = line.cl_packaging_dimensions
        self.packaging.write({'cl_length': 999.0, 'cl_gross_weight': 77.0})
        self.assertEqual(line.cl_packaging_dimensions, before)
        self.assertNotIn('77', line.cl_packaging_weight)
        # Putting another packaging on the confirmed line takes its figures.
        other = self.env['product.packaging'].create({
            'name': 'Crate', 'product_id': self.product.id, 'qty': 5,
            'cl_length': 33.0, 'cl_width': 22.0, 'cl_height': 11.0})
        line.product_packaging_id = other
        self.assertEqual(line.cl_packaging_dimensions, other.cl_dimensions)
        self.assertFalse(line.cl_packaging_weight)
