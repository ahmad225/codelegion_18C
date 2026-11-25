# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests import TransactionCase, tagged

MARKER = 'o_cl_sign_block'


@tagged('post_install', '-at_install')
class TestSignBlock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.receipts = warehouse.in_type_id
        cls.deliveries = warehouse.out_type_id
        cls.product = cls.env['product.product'].create({
            'name': 'Signed Goods', 'type': 'consu', 'is_storable': True})

    def _picking(self, picking_type):
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id
            or self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': picking_type.default_location_dest_id.id
            or self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom': self.product.uom_id.id,
                'location_id': picking_type.default_location_src_id.id
                or self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': picking_type.default_location_dest_id.id
                or self.env.ref('stock.stock_location_customers').id,
            })],
        })
        picking.action_confirm()
        return picking

    def _html(self, report_name, records):
        html = self.env['ir.actions.report']._render_qweb_html(report_name, records.ids)[0]
        return html.decode() if isinstance(html, bytes) else html

    def test_off_by_default(self):
        self.assertFalse(self.receipts.cl_sign_block)
        self.assertNotIn(MARKER, self._html('stock.report_picking', self._picking(self.receipts)))

    def test_block_on_picking_operations(self):
        self.receipts.cl_sign_block = True
        html = self._html('stock.report_picking', self._picking(self.receipts))
        self.assertIn(MARKER, html)
        for label in ('Name', 'Date and time', 'Signature'):
            self.assertIn(label, html)

    def test_only_the_chosen_operation_types(self):
        self.receipts.cl_sign_block = True
        self.assertNotIn(MARKER, self._html('stock.report_picking', self._picking(self.deliveries)))

    def test_delivery_slip_is_untouched(self):
        self.deliveries.cl_sign_block = True
        picking = self._picking(self.deliveries)
        self.assertIn(MARKER, self._html('stock.report_picking', picking))
        self.assertNotIn(MARKER, self._html('stock.report_deliveryslip', picking))

    def test_block_on_batch_transfer(self):
        picking = self._picking(self.receipts)
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.receipts.id,
            'picking_ids': [(4, picking.id)],
        })
        self.assertNotIn(MARKER, self._html('stock_picking_batch.report_picking_batch', batch))
        self.receipts.cl_sign_block = True
        self.assertIn(MARKER, self._html('stock_picking_batch.report_picking_batch', batch))
