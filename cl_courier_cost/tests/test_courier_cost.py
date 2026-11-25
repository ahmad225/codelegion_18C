# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ClCourierCostCommon


@tagged('post_install', '-at_install')
class TestCourierCost(ClCourierCostCommon):

    def test_log_created_on_delivery_validation(self):
        picking = self._deliver(qty=3)
        log = self._log(picking)
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'ok')
        self.assertAlmostEqual(log.cl_weight, 6.0)
        self.assertAlmostEqual(log.cl_expected_cost, 40.0)  # 6 kg * 5 + 10
        self.assertEqual(log.cl_carrier_id, self.carrier)
        self.assertEqual(log.cl_partner_id, self.customer)
        self.assertEqual(log.company_id, picking.company_id)
        self.assertEqual(json.loads(log.cl_variable_values)['kg'], 6.0)
        # nothing billed yet: no variance, no margin, not counted as profit
        self.assertFalse(log.cl_has_actual_cost)
        self.assertEqual(log.cl_variance, 0.0)
        self.assertEqual(log.cl_margin, 0.0)
        self.assertEqual(picking.cl_courier_cost_count, 1)

    def test_no_log_without_formula(self):
        picking = self._deliver(carrier=self.plain_carrier)
        self.assertFalse(self._log(picking))

    def test_division_by_zero_does_not_block_validation(self):
        formula = self._create_formula('Per kg fee', 'fee / kg')
        carrier = self._create_carrier('Fragile Courier', formula)
        picking = self._deliver(product=self.weightless, carrier=carrier)
        self.assertEqual(picking.state, 'done')
        log = self._log(picking)
        self.assertEqual(log.state, 'error')
        self.assertEqual(log.cl_expected_cost, 0.0)
        self.assertTrue(log.cl_error_message)
        self.assertTrue(any('could not be computed' in (message.body or '') for message in picking.message_ids))

    def test_draft_formula_is_not_used(self):
        formula = self._create_formula('Changed', 'kg * rate')
        carrier = self._create_carrier('Changed Courier', formula)
        formula.cl_expression = 'kg * rate * 100'
        self.assertEqual(formula.state, 'draft')
        picking = self._deliver(carrier=carrier)
        log = self._log(picking)
        self.assertEqual(log.state, 'error')
        self.assertEqual(log.cl_expected_cost, 0.0)
        self.assertIn('not validated', log.cl_error_message)
        # once validated, a manager recomputes the unbilled log
        formula.action_cl_validate()
        log.action_cl_recompute()
        self.assertEqual(log.state, 'ok')
        self.assertAlmostEqual(log.cl_expected_cost, 3000.0)

    def test_charge_apportioned_across_two_deliveries(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 10})],
        })
        order.set_delivery_line(self.carrier, 100.0)
        charge = sum(order.order_line.filtered('is_delivery').mapped('price_subtotal'))
        self.assertTrue(charge)
        # preview on the order: 10 x 2 kg = 20 kg -> 20 * 5 + 10
        self.assertAlmostEqual(order.cl_courier_cost_expected, 110.0)
        order.action_confirm()
        first = order.picking_ids
        self.assertEqual(len(first), 1)
        if first.carrier_id != self.carrier:
            first.carrier_id = self.carrier
        first.move_ids.quantity = 4
        first.move_ids.picked = True
        first.with_context(skip_backorder=True).button_validate()
        self.assertEqual(first.state, 'done')
        # only one delivery shipped so far: it carries the whole charge
        self.assertAlmostEqual(self._log(first).cl_customer_charge, charge)

        backorder = order.picking_ids - first
        self.assertEqual(len(backorder), 1)
        backorder.move_ids.quantity = 6
        backorder.move_ids.picked = True
        backorder.button_validate()
        first_log, second_log = self._log(first), self._log(backorder)
        # shared by shipping weight (8 kg / 12 kg), counted once in total
        self.assertAlmostEqual(first_log.cl_customer_charge, round(charge * 0.4, 2))
        self.assertAlmostEqual(first_log.cl_customer_charge + second_log.cl_customer_charge, charge)
        self.assertEqual(second_log.cl_sale_id, order)
        self.assertAlmostEqual(second_log.cl_expected_cost, 70.0)  # 12 kg * 5 + 10

    def test_sale_order_preview_converts_units(self):
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'carrier_id': self.carrier.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.env.ref('uom.product_uom_dozen').id,
            })],
        })
        # one dozen = 12 units x 2 kg = 24 kg -> 24 * 5 + 10
        self.assertAlmostEqual(order.cl_courier_cost_expected, 130.0)
        self.assertFalse(order.cl_courier_cost_message)

    def test_user_group_can_write_actual_cost(self):
        log = self._log(self._deliver(qty=3))
        user_log = log.with_user(self.courier_user)
        user_log.write({'cl_actual_cost': 46.0})
        self.assertTrue(log.cl_has_actual_cost)
        self.assertAlmostEqual(log.cl_variance, 6.0)
        self.assertAlmostEqual(log.cl_margin, log.cl_customer_charge - 46.0)
        self.assertTrue(log.cl_is_overrun)
        with self.assertRaises(AccessError):
            user_log.write({'cl_expected_cost': 1.0})
        # unticking "Billed" clears the actual cost again
        user_log.write({'cl_has_actual_cost': False})
        self.assertEqual(log.cl_actual_cost, 0.0)
        self.assertEqual(log.cl_variance, 0.0)
        user_log.write({'cl_actual_cost': 38.0})
        user_log.action_cl_lock()
        self.assertTrue(log.cl_is_locked)
        with self.assertRaises(UserError):
            user_log.write({'cl_actual_cost': 1.0})
        with self.assertRaises(AccessError):
            user_log.action_cl_unlock()
        log.action_cl_unlock()
        self.assertFalse(log.cl_is_locked)

    def test_lock_needs_actual_cost(self):
        log = self._log(self._deliver())
        with self.assertRaises(UserError):
            log.with_user(self.courier_user).write({'cl_is_locked': True})

    def test_carrier_change_keeps_billed_logs(self):
        billed = self._deliver()
        unbilled = self._deliver()
        other = self._deliver()
        billed_log = self._log(billed)
        billed_log.write({'cl_actual_cost': 41.0})

        billed.carrier_id = self.plain_carrier
        self.assertEqual(self._log(billed), billed_log)
        self.assertEqual(billed_log.cl_actual_cost, 41.0)
        self.assertEqual(billed_log.cl_carrier_id, self.carrier)

        unbilled.carrier_id = self.plain_carrier
        self.assertFalse(self._log(unbilled))
        self.assertTrue(any('removed' in (message.body or '') for message in unbilled.message_ids))

        cheap = self._create_carrier('Cheap Courier', self._create_formula('Flat', 'fee'))
        other.carrier_id = cheap
        self.assertAlmostEqual(self._log(other).cl_expected_cost, 10.0)
        self.assertEqual(self._log(other).cl_carrier_id, cheap)

    def test_recompute_many_logs_from_the_action_menu(self):
        formula = self._create_formula('Later', 'kg * rate')
        carrier = self._create_carrier('Later Courier', formula)
        formula.cl_expression = 'kg * rate + fee'  # back to draft: deliveries are logged in error
        logs = self._log(self._deliver(carrier=carrier, qty=3)) | self._log(self._deliver(carrier=carrier, qty=1))
        self.assertEqual(logs.mapped('state'), ['error', 'error'])
        formula.action_cl_validate()
        action = self.env.ref('cl_courier_cost.cl_courier_cost_action_server_recompute')
        action.with_context(active_model='cl.courier.cost', active_ids=logs.ids).run()
        self.assertEqual(logs.mapped('state'), ['ok', 'ok'])
        self.assertAlmostEqual(sum(logs.mapped('cl_expected_cost')), 60.0)  # (6 kg * 5 + 10) + (2 kg * 5 + 10)
        with self.assertRaises(AccessError):
            logs.with_user(self.courier_user).action_cl_recompute()

    def _warehouse_user_without_email(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Packer', 'login': 'cl_courier_packer',
            'groups_id': [(6, 0, [self.env.ref('stock.group_stock_user').id])]})
        user.partner_id.email = False
        return user

    def _ready_delivery(self, carrier=None):
        stock = self.warehouse.lot_stock_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': stock.id,
            'location_dest_id': self.customer_location.id,
            'partner_id': self.customer.id,
            'carrier_id': (carrier or self.carrier).id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom': self.product.uom_id.id,
                'location_id': stock.id,
                'location_dest_id': self.customer_location.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        return picking

    def test_recording_failure_never_blocks_a_user_without_email(self):
        """The fallback note is logged, not posted: posting needs a sender address."""
        packer = self._warehouse_user_without_email()
        picking = self._ready_delivery()
        cost_class = type(self.env['cl.courier.cost'])
        failing = patch.object(cost_class, '_cl_record_for_picking', side_effect=ValueError('boom'))
        with failing, self.assertLogs('odoo.addons.cl_courier_cost.models.stock_picking', level='ERROR'):
            picking.with_user(packer).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertFalse(self._log(picking))
        self.assertTrue(any('could not be recorded' in (message.body or '') for message in picking.message_ids))

    def test_formula_error_and_carrier_change_by_user_without_email(self):
        packer = self._warehouse_user_without_email()
        broken = self._create_carrier('Broken Courier', self._create_formula('Zero', 'fee / (kg - kg)'))
        picking = self._ready_delivery(carrier=broken)
        picking.with_user(packer).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self._log(picking).state, 'error')
        # the packer cannot read cost logs, so must not follow (and be emailed about) this one
        self.assertNotIn(packer.partner_id, self._log(picking).message_partner_ids)
        # the packer has no access to courier costs, yet the estimate follows the carrier
        picking.with_user(packer).write({'carrier_id': self.carrier.id})
        log = self._log(picking)
        self.assertEqual(log.state, 'ok')
        self.assertAlmostEqual(log.cl_expected_cost, 20.0)  # 2 kg * 5 + 10
        self.assertTrue(any('recomputed' in (message.body or '') for message in picking.message_ids))
