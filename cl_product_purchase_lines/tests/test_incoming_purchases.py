# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase, new_test_user, tagged

_FIELDS = ['cl_incoming_po_line_ids', 'cl_incoming_po_line_count']


@tagged('post_install', '-at_install')
class TestIncomingPurchases(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'Vendor'})
        cls.product = cls.env['product.product'].create({
            'name': 'Stocked Item', 'type': 'consu', 'is_storable': True,
            'purchase_ok': True})

    def _confirmed_po(self, qty=10.0, product=None, date_planned=None):
        line = {'product_id': (product or self.product).id, 'product_qty': qty,
                'price_unit': 5.0}
        if date_planned:
            line['date_planned'] = date_planned
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, line)],
        })
        po.button_confirm()
        return po

    def _refresh(self, product=None):
        product = product or self.product
        product.invalidate_recordset(_FIELDS)
        product.product_tmpl_id.invalidate_recordset(_FIELDS)

    def _receive(self, po, qty, backorder=True):
        picking = po.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
        for move in picking.move_ids:
            move.quantity = qty
            move.picked = True
        action = picking.button_validate()
        if isinstance(action, dict) and action.get('res_model'):
            wizard = Form(self.env[action['res_model']].with_context(action['context'])).save()
            if backorder:
                wizard.process()
            else:
                wizard.process_cancel_backorder()

    def test_open_receipt_is_listed(self):
        po = self._confirmed_po()
        self._refresh()
        line = po.order_line
        self.assertIn(line, self.product.cl_incoming_po_line_ids)
        self.assertEqual(self.product.cl_incoming_po_line_count, 1)
        self.assertEqual(line.cl_qty_to_receive, 10.0)
        self.assertEqual(line.cl_receipt_progress, 'none')
        self.assertIn(line, self.product.product_tmpl_id.cl_incoming_po_line_ids)
        self.assertEqual(self.product.product_tmpl_id.cl_incoming_po_line_count, 1)

    def test_fully_received_drops_off(self):
        po = self._confirmed_po()
        self._receive(po, 10.0)
        self._refresh()
        self.assertNotIn(po.order_line, self.product.cl_incoming_po_line_ids)

    def test_partial_receipt_with_backorder_stays(self):
        po = self._confirmed_po()
        self._receive(po, 4.0, backorder=True)
        self._refresh()
        line = po.order_line
        self.assertIn(line, self.product.cl_incoming_po_line_ids)
        self.assertEqual(line.cl_receipt_progress, 'part')
        self.assertEqual(line.cl_qty_to_receive, 6.0)

    def test_partial_receipt_without_backorder_drops_off(self):
        po = self._confirmed_po()
        self._receive(po, 4.0, backorder=False)
        self._refresh()
        self.assertNotIn(po.order_line, self.product.cl_incoming_po_line_ids)

    def test_cancelled_receipt_drops_off(self):
        po = self._confirmed_po()
        po.picking_ids.action_cancel()
        self._refresh()
        self.assertNotIn(po.order_line, self.product.cl_incoming_po_line_ids)

    def test_draft_po_not_listed(self):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 3.0})],
        })
        self._refresh()
        self.assertNotIn(po.order_line, self.product.cl_incoming_po_line_ids)

    def test_non_storable_goods_are_listed(self):
        """Goods that are not tracked in stock still come in through a receipt."""
        consumable = self.env['product.product'].create({
            'name': 'Consumable', 'type': 'consu', 'is_storable': False})
        po = self._confirmed_po(product=consumable)
        self.assertTrue(po.picking_ids)
        self._refresh(consumable)
        self.assertIn(po.order_line, consumable.cl_incoming_po_line_ids)

    def test_service_has_no_incoming(self):
        service = self.env['product.product'].create({
            'name': 'Service', 'type': 'service'})
        self._confirmed_po(product=service)
        self._refresh(service)
        self.assertFalse(service.cl_incoming_po_line_ids)
        self.assertEqual(service.cl_incoming_po_line_count, 0)

    def test_lines_sorted_by_expected_arrival(self):
        now = fields.Datetime.now()
        late = self._confirmed_po(date_planned=now + timedelta(days=30))
        early = self._confirmed_po(date_planned=now + timedelta(days=2))
        self._refresh()
        expected = (early.order_line | late.order_line).ids
        self.assertEqual(self.product.cl_incoming_po_line_ids.ids, expected)
        self.assertEqual(
            self.product.product_tmpl_id.cl_incoming_po_line_ids.ids, expected)

    def test_smart_button_action(self):
        po = self._confirmed_po()
        self._refresh()
        action = self.product.action_cl_view_incoming_po_lines()
        self.assertEqual(action['res_model'], 'purchase.order.line')
        self.assertEqual(action['domain'], [('id', 'in', po.order_line.ids)])
        list_view = self.env.ref('cl_product_purchase_lines.cl_incoming_po_line_list')
        self.assertEqual(action['views'], [(list_view.id, 'list')])
        tmpl_action = self.product.product_tmpl_id.action_cl_view_incoming_po_lines()
        self.assertEqual(tmpl_action['domain'], [('id', 'in', po.order_line.ids)])

    def test_inventory_user_sees_incoming(self):
        """Inventory users can already read purchase lines in standard Odoo;
        they get the tab too, without being Purchase users."""
        po = self._confirmed_po()
        user = new_test_user(
            self.env, login='cl_incoming_stock_user',
            groups='base.group_user,stock.group_stock_user')
        self.assertFalse(user.has_group('purchase.group_purchase_user'))
        self._refresh()
        product = self.product.with_user(user)
        values = product.read(['cl_incoming_po_line_count'])[0]
        self.assertEqual(values['cl_incoming_po_line_count'], 1)
        self.assertEqual(product.cl_incoming_po_line_ids, po.order_line)

    def test_other_users_cannot_read_the_fields(self):
        self._confirmed_po()
        user = new_test_user(
            self.env, login='cl_incoming_basic_user', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.product.with_user(user).read(['cl_incoming_po_line_count'])
