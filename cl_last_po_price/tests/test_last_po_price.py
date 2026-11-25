# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLastPoPrice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.cl_last_po_price = True
        cls.company.cl_last_po_price_vendor = 'same'
        cls.company.cl_last_po_price_products = 'all'
        cls.vendor = cls.env['res.partner'].create({'name': 'Vendor A'})
        cls.vendor_b = cls.env['res.partner'].create({'name': 'Vendor B'})
        cls.product = cls.env['product.product'].create({
            'name': 'Widget', 'type': 'consu', 'standard_price': 0.0,
            'list_price': 0.0})

    def _po(self, vendor, price=None, qty=3.0, **order_vals):
        line = {'product_id': self.product.id, 'product_qty': qty}
        if price is not None:
            line['price_unit'] = price
        return self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, line)],
            **order_vals,
        })

    def test_last_price_filled_from_confirmed_po(self):
        # The first confirmation also registers Vendor A on the product at 42
        # (standard Odoo). The second one, at 55, is the last purchase price.
        self._po(self.vendor, price=42.0).button_confirm()
        self._po(self.vendor, price=55.0).button_confirm()
        po = self._po(self.vendor)
        self.assertEqual(po.order_line.price_unit, 55.0)
        self.assertEqual(po.state, 'draft')

    def test_same_vendor_scope_isolates_vendors(self):
        self._po(self.vendor, price=42.0).button_confirm()
        # Different vendor -> no last price from Vendor A under same_vendor scope
        po = self._po(self.vendor_b)
        self.assertEqual(po.order_line.price_unit, 0.0)

    def test_any_vendor_scope_crosses_vendors(self):
        self.company.cl_last_po_price_vendor = 'any'
        self._po(self.vendor, price=42.0).button_confirm()
        po = self._po(self.vendor_b)
        self.assertEqual(po.order_line.price_unit, 42.0)

    def test_latest_confirmation_wins(self):
        """The price comes from the order confirmed last, not created last."""
        po_old = self._po(self.vendor, price=10.0)
        po_new = self._po(self.vendor, price=20.0)
        po_new.button_confirm()
        po_old.button_confirm()
        # po_old was created first but confirmed last; make that unambiguous.
        po_new.date_approve = po_old.date_approve - timedelta(days=1)
        po = self._po(self.vendor)
        self.assertEqual(po.order_line.price_unit, 10.0)

    def test_explicit_price_is_kept_on_create(self):
        self._po(self.vendor, price=42.0).button_confirm()
        po = self._po(self.vendor, price=100.0)
        self.assertEqual(po.order_line.price_unit, 100.0)

    def test_confirmed_line_not_overwritten(self):
        self.company.cl_last_po_price_vendor = 'any'
        po_b = self._po(self.vendor_b, price=100.0)
        po_b.button_confirm()
        # A later confirmed order (other vendor) makes 42 the last price.
        self._po(self.vendor, price=42.0).button_confirm()
        # Changing the quantity of the confirmed line must NOT pull 42 onto it.
        po_b.order_line.product_qty = 9.0
        self.assertEqual(po_b.order_line.price_unit, 100.0)

    def test_manual_price_kept_on_quantity_change(self):
        """A price typed on a saved draft line survives a quantity change, as
        in standard Odoo when the vendor has no price list for the product."""
        self.company.cl_last_po_price_vendor = 'any'
        self._po(self.vendor, price=42.0).button_confirm()
        line = self._po(self.vendor_b).order_line
        self.assertEqual(line.price_unit, 42.0)
        line.write({'price_unit': 50.0, 'discount': 7.0})
        line.product_qty = 9.0
        self.assertEqual(line.price_unit, 50.0)
        self.assertEqual(line.discount, 7.0)

    def test_discount_carried_over(self):
        self.company.cl_last_po_price_vendor = 'any'
        po1 = self._po(self.vendor, price=42.0)
        po1.order_line.discount = 12.5
        po1.button_confirm()
        # Created without a price, as an import or the product catalog does.
        po = self._po(self.vendor_b)
        self.assertEqual(po.order_line.price_unit, 42.0)
        self.assertEqual(po.order_line.discount, 12.5)

    def test_price_converted_to_order_currency(self):
        self.company.cl_last_po_price_vendor = 'any'
        foreign = self.env['res.currency'].create({
            'name': 'CLX', 'symbol': 'X', 'rounding': 0.01})
        self.env['res.currency.rate'].create({
            'name': '2000-01-01', 'currency_id': foreign.id,
            'rate': 2.0, 'company_id': self.company.id})
        self._po(self.vendor, price=42.0).button_confirm()
        po = self._po(self.vendor_b, currency_id=foreign.id)
        expected = self.company.currency_id._convert(
            42.0, foreign, self.company, po.date_order, round=False)
        self.assertNotEqual(round(expected, 2), 42.0)
        self.assertAlmostEqual(po.order_line.price_unit, expected, places=2)

    def test_price_converted_to_line_uom(self):
        po1 = self._po(self.vendor, price=5.0)
        po1.button_confirm()
        po = self._po(self.vendor, price=1.0)
        target = self.env['purchase.order.line'].new({
            'order_id': po.id,
            'product_id': self.product.id,
            'product_uom': self.env.ref('uom.product_uom_dozen').id,
        })
        price = self.env['purchase.order.line']._cl_convert_last_price(
            po1.order_line, target)
        self.assertAlmostEqual(price, 60.0, places=2)

    def test_variant_scope_skips_simple_products(self):
        self.company.cl_last_po_price_vendor = 'any'
        self.company.cl_last_po_price_products = 'variants'
        self._po(self.vendor, price=42.0).button_confirm()
        po = self._po(self.vendor_b)
        self.assertEqual(po.order_line.price_unit, 0.0)

    def test_form_fills_price_on_product_selection(self):
        self.company.cl_last_po_price_vendor = 'any'
        self._po(self.vendor, price=42.0).button_confirm()
        form = Form(self.env['purchase.order'])
        form.partner_id = self.vendor_b
        with form.order_line.new() as line:
            line.product_id = self.product
            self.assertEqual(line.price_unit, 42.0)
        po = form.save()
        self.assertEqual(po.order_line.price_unit, 42.0)

    def test_disabled_does_nothing(self):
        self.company.cl_last_po_price = False
        self.company.cl_last_po_price_vendor = 'any'
        self._po(self.vendor, price=42.0).button_confirm()
        po = self._po(self.vendor_b)
        self.assertEqual(po.order_line.price_unit, 0.0)
