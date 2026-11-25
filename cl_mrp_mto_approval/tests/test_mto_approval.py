# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMtoApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.cl_mto_approval_required = True
        cls.env.ref('stock.route_warehouse0_mto').active = True
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.route_manufacture = cls.warehouse.manufacture_pull_id.route_id
        cls.routes = cls.route_manufacture | cls.env.ref('stock.route_warehouse0_mto')

        cls.component = cls.env['product.product'].create({'name': 'Cup Blank', 'is_storable': True})
        cls.product = cls.env['product.product'].create({
            'name': 'Printed Cup', 'is_storable': True, 'route_ids': [(6, 0, cls.routes.ids)]})
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': cls.component.id, 'product_qty': 1})],
        })
        cls.env['stock.quant']._update_available_quantity(cls.component, cls.warehouse.lot_stock_id, 100)

        cls.viewer_group = 'cl_mrp_mto_approval.group_cl_mto_sale_viewer'
        cls.coordinator_group = 'cl_mrp_mto_approval.group_cl_mto_coordinator'
        cls.salesman = cls._user('cl_mto_salesman', cls.viewer_group)
        cls.other_salesman = cls._user('cl_mto_other_salesman', cls.viewer_group)
        cls.mrp_user = cls._user('cl_mto_mrp_user', 'mrp.group_mrp_user')
        cls.coordinator = cls._user('cl_mto_coordinator', cls.coordinator_group)
        cls.admin = cls._user('cl_mto_admin', 'base.group_system', 'mrp.group_mrp_user')
        cls.customer = cls.env['res.partner'].create({'name': 'Cafe Customer'})
        cls.activity_type = cls.env.ref('cl_mrp_mto_approval.mail_act_cl_mto_approval')

    @classmethod
    def _user(cls, login, *xmlids, email=True):
        return cls.env['res.users'].create({
            'name': login, 'login': login,
            'email': '%s@example.com' % login if email else False,
            'groups_id': [(6, 0, [cls.env.ref(x).id for x in xmlids])],
        })

    def _confirmed_order(self, salesman=None, qty=2):
        salesman = salesman or self.salesman
        order = self.env['sale.order'].with_user(salesman).create({
            'partner_id': self.customer.id,
            'user_id': salesman.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': qty})],
        })
        order.action_confirm()
        return order.with_user(self.env.user)

    def _mo(self, order):
        return self.env['mrp.production'].search([('cl_mto_sale_order_id', '=', order.id)])

    def _approval_activities(self, production):
        production.invalidate_recordset(['activity_ids'])
        return production.activity_ids.filtered(lambda a: a.activity_type_id == self.activity_type)

    def _produce(self, production, user, qty=None):
        production = production.with_user(user)
        with Form(production) as mo_form:
            mo_form.qty_producing = qty or production.product_qty
        return production.button_mark_done()

    def _reject(self, production, reason, user=None, cancel=False):
        self.env['cl.mrp.mto.reject.wizard'].with_user(user or self.coordinator).create({
            'production_ids': [(6, 0, production.ids)], 'reason': reason, 'cancel_production': cancel,
        }).action_cl_confirm_reject()

    # ------------------------------------------------------------------
    # which orders wait for approval
    # ------------------------------------------------------------------

    def test_link_field_is_not_shared_with_other_modules(self):
        # cl_mrp_sales_handover has a computed mrp.production.cl_sale_order_id. Odoo
        # merges same-named fields of different modules into one, so ours has its own
        # name and stays a plain field written by the procurement.
        fields_ = self.env['mrp.production']._fields
        self.assertFalse(fields_['cl_mto_sale_order_id'].compute)
        other = fields_.get('cl_sale_order_id')
        if other is not None:
            self.assertNotIn('cl_mrp_mto_approval', getattr(other, '_modules', None) or ())

    def test_mto_mo_from_sale_needs_approval(self):
        order = self._confirmed_order()
        mo = self._mo(order)
        self.assertEqual(len(mo), 1)
        self.assertEqual(mo.cl_approval_state, 'pending')
        # Odoo's own state machine is untouched: the order is confirmed and reserves as usual.
        self.assertEqual(mo.state, 'confirmed')
        self.assertIn(self.coordinator, self._approval_activities(mo).user_id)

    def test_manual_mo_not_affected(self):
        order = self._confirmed_order()
        # Same Source text as a sales order: still a manual order, no approval.
        mo = self.env['mrp.production'].with_user(self.mrp_user).create({
            'product_id': self.product.id, 'product_qty': 1, 'origin': order.name})
        mo.action_confirm()
        self.assertEqual(mo.cl_approval_state, 'none')
        self.assertFalse(mo.cl_mto_sale_order_id)
        self._produce(mo, self.mrp_user)
        self.assertEqual(mo.state, 'done')

    def test_reordering_rule_mo_not_affected(self):
        orderpoint = self.env['stock.warehouse.orderpoint'].create({
            'product_id': self.product.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'route_id': self.route_manufacture.id,
            'product_min_qty': 5,
            'product_max_qty': 10,
        })
        orderpoint.action_replenish()
        mo = self.env['mrp.production'].search([('orderpoint_id', '=', orderpoint.id)])
        self.assertTrue(mo)
        self.assertEqual(set(mo.mapped('cl_approval_state')), {'none'})

    def test_switched_off(self):
        self.env.company.cl_mto_approval_required = False
        order = self._confirmed_order()
        mo = self._mo(order)
        self.assertEqual(mo.cl_approval_state, 'none')
        self._produce(mo, self.mrp_user)
        self.assertEqual(mo.state, 'done')

    def test_each_sales_order_gets_its_own_mo(self):
        mo1 = self._mo(self._confirmed_order())
        mo2 = self._mo(self._confirmed_order(self.other_salesman))
        self.assertTrue(mo1 and mo2)
        self.assertNotEqual(mo1, mo2)

    def test_sub_assembly_follows_its_parent(self):
        sleeve = self.env['product.product'].create({
            'name': 'Printed Sleeve', 'is_storable': True, 'route_ids': [(6, 0, self.routes.ids)]})
        self.env['mrp.bom'].create({
            'product_tmpl_id': sleeve.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.component.id, 'product_qty': 1})],
        })
        self.bom.write({'bom_line_ids': [(0, 0, {'product_id': sleeve.id, 'product_qty': 1})]})

        order = self._confirmed_order()
        productions = self._mo(order)
        parent = productions.filtered(lambda p: p.product_id == self.product)
        child = productions.filtered(lambda p: p.product_id == sleeve)
        self.assertEqual(len(parent), 1)
        self.assertEqual(len(child), 1)
        self.assertEqual(child.cl_approval_parent_id, parent)
        self.assertEqual(child.cl_approval_state, 'pending')
        # Only the top order asks the coordinators.
        self.assertTrue(self._approval_activities(parent))
        self.assertFalse(self._approval_activities(child))
        with self.assertRaises(UserError):
            child.with_user(self.mrp_user).action_start()

        parent.with_user(self.coordinator).action_cl_approve()
        self.assertEqual(child.cl_approval_state, 'approved')

    def test_sub_assembly_found_through_a_transfer(self):
        # 2 and 3 step manufacturing: the sub-assembly supplies a "pick components"
        # move, which in turn supplies the component move of the parent order.
        Rule = self.env['stock.rule']
        parent = self.env['mrp.production'].create({'product_id': self.product.id, 'product_qty': 1})
        parent.action_confirm()
        raw_move = parent.move_raw_ids[:1]
        self.assertTrue(raw_move)
        pick_move = self.env['stock.move'].create({
            'name': 'Pick components',
            'product_id': raw_move.product_id.id,
            'product_uom_qty': 1,
            'product_uom': raw_move.product_uom.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': raw_move.location_id.id,
            'move_dest_ids': [(4, raw_move.id)],
        })
        self.assertEqual(Rule._cl_parent_production(pick_move), parent)
        self.assertFalse(Rule._cl_parent_production(self.env['stock.move']))

        # Parent without sales order: the sub-assembly is an ordinary order.
        self.assertEqual(Rule._cl_mto_approval_vals({'move_dest_ids': pick_move}, self.env.company), {})
        # Parent waiting for approval: the sub-assembly waits with it.
        order = self._confirmed_order()
        parent.write({'cl_mto_sale_order_id': order.id, 'cl_approval_state': 'pending'})
        self.assertEqual(
            Rule._cl_mto_approval_vals({'move_dest_ids': pick_move}, self.env.company),
            {'cl_mto_sale_order_id': order.id, 'cl_approval_state': 'pending',
             'cl_approval_parent_id': parent.id})

    # ------------------------------------------------------------------
    # nobody gets around the approval
    # ------------------------------------------------------------------

    def test_non_coordinator_cannot_approve_or_bypass(self):
        mo = self._mo(self._confirmed_order()).with_user(self.mrp_user)
        with self.assertRaises(AccessError):
            mo.action_cl_approve()
        with self.assertRaises(AccessError):
            mo.action_cl_reject()
        with self.assertRaises(AccessError):
            mo.write({'cl_approval_state': 'approved'})
        with self.assertRaises(UserError):
            mo.action_start()
        with self.assertRaises(UserError):
            mo.button_plan()
        with self.assertRaises(UserError):
            mo.write({'qty_producing': 1})
        with self.assertRaises(UserError):
            mo.button_mark_done()
        self.assertEqual(mo.cl_approval_state, 'pending')

    def test_waiting_orders_cannot_be_merged(self):
        # Merging replaces the orders by a brand new one: not a way around the approval.
        mo1 = self._mo(self._confirmed_order())
        mo2 = self._mo(self._confirmed_order(self.other_salesman))
        with self.assertRaises(UserError):
            (mo1 | mo2).with_user(self.mrp_user).action_merge()
        self.assertEqual((mo1 | mo2).mapped('state'), ['confirmed', 'confirmed'])

    def test_merged_order_keeps_its_sales_order(self):
        order = self._confirmed_order(qty=2)
        mo = self._mo(order)
        mo.with_user(self.coordinator).action_cl_approve()
        parts = mo._split_productions({mo: [1, 1]})
        self.assertEqual(len(parts), 2)
        self.assertEqual(set(parts.mapped('cl_approval_state')), {'approved'})
        action = parts.with_user(self.mrp_user).action_merge()
        merged = self.env['mrp.production'].browse(action['res_id'])
        self.assertEqual(merged.cl_mto_sale_order_id, order)
        self.assertEqual(merged.cl_approval_state, 'approved')

    # ------------------------------------------------------------------
    # approve / reject
    # ------------------------------------------------------------------

    def test_approved_mo_can_be_produced_and_backorder_stays_approved(self):
        mo = self._mo(self._confirmed_order(qty=2))
        mo.with_user(self.coordinator).action_cl_approve()
        self.assertEqual(mo.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(mo))
        action = self._produce(mo, self.mrp_user, qty=1)
        Form(self.env['mrp.production.backorder'].with_user(self.mrp_user).with_context(
            **action['context'])).save().action_backorder()
        self.assertEqual(mo.state, 'done')
        backorder = mo.procurement_group_id.mrp_production_ids - mo
        self.assertEqual(len(backorder), 1)
        self.assertEqual(backorder.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(backorder))
        self._produce(backorder, self.mrp_user)
        self.assertEqual(backorder.state, 'done')

    def test_administrator_can_approve(self):
        mo = self._mo(self._confirmed_order())
        mo.with_user(self.admin).action_cl_approve()
        self.assertEqual(mo.cl_approval_state, 'approved')

    def test_approve_several_orders_and_close_all_activities(self):
        second = self._user('cl_mto_coordinator_2', self.coordinator_group)
        mo1 = self._mo(self._confirmed_order())
        mo2 = self._mo(self._confirmed_order(self.other_salesman))
        self.assertIn(second, self._approval_activities(mo1).user_id)
        # From the list view: one click for the selected orders.
        (mo1 | mo2).with_user(self.coordinator).action_cl_approve()
        self.assertEqual((mo1 | mo2).mapped('cl_approval_state'), ['approved', 'approved'])
        # The activities of the other coordinators are gone too.
        self.assertFalse(self._approval_activities(mo1 | mo2))

    def test_coordinator_without_email_can_decide(self):
        no_mail = self._user('cl_mto_coordinator_no_mail', self.coordinator_group, email=False)
        mo = self._mo(self._confirmed_order())
        self._reject(mo, 'Artwork missing', user=no_mail)
        self.assertEqual(mo.cl_approval_state, 'rejected')
        mo.with_user(no_mail).action_cl_approve()
        self.assertEqual(mo.cl_approval_state, 'approved')
        self.assertFalse(self._approval_activities(mo))

    def test_reject_notifies_salesperson_then_request_again_or_cancel(self):
        order = self._confirmed_order()
        mo = self._mo(order)
        self._reject(mo, 'Logo file missing')
        self.assertEqual(mo.cl_approval_state, 'rejected')
        self.assertEqual(mo.state, 'confirmed')
        self.assertFalse(self._approval_activities(mo))
        notes = order.message_ids.filtered(lambda m: self.salesman.partner_id in m.partner_ids)
        self.assertTrue(notes)
        with self.assertRaises(UserError):
            mo.with_user(self.mrp_user).action_start()

        mo.with_user(self.mrp_user).action_cl_request_approval()
        self.assertEqual(mo.cl_approval_state, 'pending')
        self.assertIn(self.coordinator, self._approval_activities(mo).user_id)

        self._reject(mo, 'Order withdrawn', cancel=True)
        self.assertEqual(mo.state, 'cancel')
        self.assertFalse(self._approval_activities(mo))

    def test_user_who_cannot_open_the_sales_order(self):
        # A production user who is also a salesperson with "Own Documents Only"
        # cannot read the sales order of a colleague: the approval steps still work.
        both = self._user('cl_mto_mrp_and_sales', 'mrp.group_mrp_user', 'sales_team.group_sale_salesman')
        coordinator = self._user(
            'cl_mto_coordinator_and_sales', self.coordinator_group, 'sales_team.group_sale_salesman')
        order = self._confirmed_order()
        with self.assertRaises(AccessError):
            order.with_user(both).read(['name'])
        mo = self._mo(order)
        self._reject(mo, 'Wrong colour', user=coordinator)
        self.assertEqual(mo.cl_approval_state, 'rejected')
        mo.with_user(both).action_cl_request_approval()
        self.assertEqual(mo.cl_approval_state, 'pending')
        mo.with_user(coordinator).action_cl_approve()
        self.assertEqual(mo.cl_approval_state, 'approved')

    # ------------------------------------------------------------------
    # salespeople follow the manufacturing of sales orders
    # ------------------------------------------------------------------

    def test_salesperson_follows_manufacturing_read_only(self):
        own_order = self._confirmed_order()
        own_mo = self._mo(own_order)
        other_mo = self._mo(self._confirmed_order(self.other_salesman))

        order = own_order.with_user(self.salesman)
        self.assertEqual(order.cl_mrp_production_count, 1)
        action = order.action_cl_view_mto_productions()
        self.assertEqual(action['res_id'], own_mo.id)
        own_mo.with_user(self.salesman).read(['name', 'state', 'cl_approval_state'])

        # Read-only, whatever Odoo's own access rights for salespeople say.
        with self.assertRaises(AccessError):
            own_mo.with_user(self.salesman).write({'origin': 'changed'})
        with self.assertRaises(AccessError):
            own_mo.with_user(self.salesman).check_access('unlink')
        with self.assertRaises(AccessError):
            own_mo.with_user(self.salesman).check_access('create')

        # Reading is not restricted: screens salespeople use (the Forecast report of a
        # product) read the names of manufacturing orders that are not theirs.
        self.assertEqual(other_mo.with_user(self.salesman).read(['name'])[0]['name'], other_mo.name)

    def test_viewer_who_is_also_manufacturing_user_keeps_full_access(self):
        mo = self._mo(self._confirmed_order(self.other_salesman))
        both = self._user('cl_mto_both', self.viewer_group, 'mrp.group_mrp_user', email=False)
        mo.with_user(both).write({'origin': 'checked'})
        self.assertEqual(mo.origin, 'checked')
