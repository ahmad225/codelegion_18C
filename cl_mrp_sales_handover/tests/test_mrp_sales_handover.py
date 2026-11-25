# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

READY_ACTIVITY = 'cl_mrp_sales_handover.mail_act_cl_handover_ready'


@tagged('post_install', '-at_install')
class TestMrpSalesHandover(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'cl_handover_date_sync': 'planned',
            'cl_handover_move_agreed_date': False,
            'cl_handover_notify': True,
            'cl_handover_event_date': True,
            'cl_handover_collection_email': True,
            'cl_handover_reminder_days': 3,
            'cl_handover_reminder_max': 2,
        })
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        mto_route = cls.env.ref('stock.route_warehouse0_mto')
        if not mto_route.active:
            mto_route.toggle_active()
        cls.warehouse.mto_pull_id.active = True
        cls.warehouse.mto_pull_id.procure_method = 'make_to_order'
        routes = cls.warehouse.manufacture_pull_id.route_id | cls.warehouse.mto_pull_id.route_id
        cls.routes = routes

        def group(xmlid):
            return cls.env.ref(xmlid).id

        cls.salesman = cls.env['res.users'].create({
            'name': 'Handover Salesman', 'login': 'cl_handover_salesman', 'email': 'sales@example.com',
            'groups_id': [(6, 0, [group('sales_team.group_sale_salesman')])]})
        cls.mrp_user = cls.env['res.users'].create({
            'name': 'Handover Producer', 'login': 'cl_handover_producer',
            'groups_id': [(6, 0, [group('mrp.group_mrp_user')])]})
        cls.mrp_manager = cls.env['res.users'].create({
            'name': 'Handover Manager', 'login': 'cl_handover_manager',
            'groups_id': [(6, 0, [group('mrp.group_mrp_manager')])]})
        cls.customer = cls.env['res.partner'].create({'name': 'Event Customer', 'email': 'customer@example.com'})

        component = cls.env['product.product'].create({'name': 'Blank Cup', 'type': 'consu'})
        cls.component = component
        cls.product_a = cls.env['product.product'].create({
            'name': 'Printed Cup', 'type': 'consu', 'is_storable': True,
            'route_ids': [(6, 0, routes.ids)]})
        cls.product_b = cls.env['product.product'].create({
            'name': 'Printed Lid', 'type': 'consu', 'is_storable': True,
            'route_ids': [(6, 0, routes.ids)]})
        for product in cls.product_a | cls.product_b:
            cls.env['mrp.bom'].create({
                'product_tmpl_id': product.product_tmpl_id.id,
                'product_qty': 1,
                'type': 'normal',
                'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
            })
        cls.stock_product = cls.env['product.product'].create({
            'name': 'Plain Mug', 'type': 'consu', 'is_storable': True})
        cls.env['stock.quant']._update_available_quantity(cls.stock_product, cls.warehouse.lot_stock_id, 50)
        service = cls.env['product.product'].create({'name': 'Collection', 'type': 'service'})
        cls.collection_carrier = cls.env['delivery.carrier'].create({
            'name': 'Collect at the shop', 'delivery_type': 'fixed', 'fixed_price': 0,
            'product_id': service.id, 'cl_handover_collection': True})
        cls.courier = cls.env['delivery.carrier'].create({
            'name': 'Courier', 'delivery_type': 'fixed', 'fixed_price': 5, 'product_id': service.id})

    # ---- helpers ----

    def _order(self, products, **vals):
        order = self.env['sale.order'].create(dict({
            'partner_id': self.customer.id,
            'user_id': self.salesman.id,
            'warehouse_id': self.warehouse.id,
            'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': 1}) for p in products],
        }, **vals))
        order.action_confirm()
        return order

    def _produce(self, production):
        mo_form = Form(production)
        mo_form.qty_producing = production.product_qty
        production = mo_form.save()
        production.button_mark_done()
        self.assertEqual(production.state, 'done')

    def _notes_to_salesman(self, order):
        # Notes of this module that notify the salesperson (not assignment or activity notices).
        note = self.env.ref('mail.mt_note')
        return order.message_ids.filtered(
            lambda m: m.subtype_id == note and m.message_type == 'notification'
            and self.salesman.partner_id in m.partner_ids)

    def _ready_activities(self, order):
        activity_type = self.env.ref(READY_ACTIVITY)
        return order.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)

    def _mails(self, picking, subject):
        return self.env['mail.mail'].search([
            ('model', '=', 'stock.picking'), ('res_id', '=', picking.id), ('subject', 'ilike', subject)])

    def _bom(self, product, component):
        return self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'type': 'normal',
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
        })

    # ---- link and event date ----

    def test_link_field_belongs_to_this_module_only(self):
        # cl_mrp_mto_approval keeps its own link in cl_mto_sale_order_id: two modules
        # defining the same field would be merged by Odoo into one.
        field = self.env['mrp.production']._fields['cl_sale_order_id']
        self.assertTrue(field.compute)
        self.assertTrue(field.store)
        modules = getattr(field, '_modules', None)
        if modules:
            self.assertEqual(set(modules), {'cl_mrp_sales_handover'})

    def test_sub_assemblies_at_any_level_follow_the_sales_order(self):
        def made_to_order(name):
            return self.env['product.product'].create({
                'name': name, 'type': 'consu', 'is_storable': True,
                'route_ids': [(6, 0, self.routes.ids)]})

        sleeve = made_to_order('Printed Sleeve')
        label = made_to_order('Sleeve Label')
        self._bom(label, self.component)
        self._bom(sleeve, label)
        self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_a.product_tmpl_id.id)]).write({
            'bom_line_ids': [(0, 0, {'product_id': sleeve.id, 'product_qty': 1})]})

        order = self._order(self.product_a, cl_event_date=date(2031, 3, 10))
        productions = order.cl_production_ids
        self.assertEqual(productions.product_id, self.product_a | sleeve | label)
        self.assertEqual(set(productions.mapped('cl_event_date')), {date(2031, 3, 10)})
        # Only the order that makes the sold product counts for the delivery date
        # and the handover.
        self.assertEqual(productions._cl_final_productions().product_id, self.product_a)
        self.assertEqual(order.cl_handover_state, 'waiting')

    def test_mo_linked_and_event_date_flows(self):
        order = self._order(self.product_a, cl_event_date=date(2031, 3, 10), cl_event_note='Wedding')
        production = order.cl_production_ids
        self.assertEqual(len(production), 1)
        self.assertEqual(production.cl_sale_order_id, order)
        self.assertEqual(production.cl_event_date, date(2031, 3, 10))
        self.assertEqual(production.cl_event_note, 'Wedding')

    def test_salesman_changes_event_date_without_mrp_rights(self):
        order = self._order(self.product_a, cl_event_date=date(2031, 3, 10))
        production = order.cl_production_ids
        order.with_user(self.salesman).write({'cl_event_date': date(2031, 3, 1)})
        self.assertEqual(production.cl_event_date, date(2031, 3, 1))
        self.assertTrue(any(order.name in (m.body or '') for m in production.message_ids))
        order.with_user(self.salesman).write({'cl_event_date': False})
        self.assertFalse(production.cl_event_date)

    def test_event_at_risk(self):
        order = self._order(self.product_a, cl_event_date=fields.Date.today() + timedelta(days=30))
        production = order.cl_production_ids
        production.write({'date_finished': fields.Datetime.now() + timedelta(days=40)})
        self.assertTrue(production.cl_event_at_risk)
        self.assertTrue(order.cl_event_at_risk)

    # ---- delivery date ----

    def test_empty_delivery_date_follows_planned_end(self):
        order = self._order(self.product_a)
        production = order.cl_production_ids
        self.assertTrue(order.cl_commitment_by_mfg)
        self.assertEqual(order.commitment_date.date(), production.date_finished.date())
        later = production.date_finished + timedelta(days=5)
        production.write({'date_finished': later})
        self.assertEqual(order.commitment_date.date(), later.date())
        # Our own date slipped: the salesperson is told.
        self.assertTrue(self._notes_to_salesman(order))

    def test_agreed_date_is_kept_and_salesman_warned_once(self):
        agreed = fields.Datetime.now() + timedelta(days=20)
        order = self._order(self.product_a, commitment_date=agreed)
        production = order.cl_production_ids
        self.assertFalse(order.cl_commitment_by_mfg)
        self.assertEqual(order.commitment_date, agreed)
        production.write({'date_finished': agreed + timedelta(days=4)})
        self.assertEqual(order.commitment_date, agreed)
        self.assertEqual(len(self._notes_to_salesman(order)), 1)
        production.write({'date_finished': agreed + timedelta(days=4)})
        self.assertEqual(len(self._notes_to_salesman(order)), 1, "Same delay is reported only once")
        # Earlier than agreed: never moved earlier.
        production.write({'date_finished': agreed - timedelta(days=3)})
        self.assertEqual(order.commitment_date, agreed)

    def test_agreed_date_moved_later_when_allowed(self):
        self.company.cl_handover_move_agreed_date = True
        agreed = fields.Datetime.now() + timedelta(days=20)
        order = self._order(self.product_a, commitment_date=agreed)
        production = order.cl_production_ids
        new_end = agreed + timedelta(days=6)
        production.write({'date_finished': new_end})
        self.assertEqual(order.commitment_date.date(), new_end.date())
        self.assertTrue(self._notes_to_salesman(order))

    def test_manual_date_becomes_agreed(self):
        order = self._order(self.product_a)
        self.assertTrue(order.cl_commitment_by_mfg)
        typed = fields.Datetime.now() + timedelta(days=60)
        order.write({'commitment_date': typed})
        self.assertFalse(order.cl_commitment_by_mfg)
        order.cl_production_ids.write({'date_finished': typed - timedelta(days=10)})
        self.assertEqual(order.commitment_date, typed)

    def test_several_mos_latest_counts(self):
        order = self._order(self.product_a | self.product_b)
        mo_a = order.cl_production_ids.filtered(lambda p: p.product_id == self.product_a)
        mo_b = order.cl_production_ids.filtered(lambda p: p.product_id == self.product_b)
        self.assertTrue(mo_a and mo_b)
        now = fields.Datetime.now()
        mo_a.write({'date_finished': now + timedelta(days=7)})
        mo_b.write({'date_finished': now + timedelta(days=10)})
        self.assertEqual(order.commitment_date.date(), (now + timedelta(days=10)).date())
        mo_b.write({'date_finished': now + timedelta(days=3)})
        self.assertEqual(order.commitment_date.date(), (now + timedelta(days=7)).date())

    def test_done_mode_waits_for_all_mos(self):
        self.company.cl_handover_date_sync = 'done'
        order = self._order(self.product_a | self.product_b)
        self.assertFalse(order.commitment_date)
        mo_a, mo_b = order.cl_production_ids[0], order.cl_production_ids[1]
        self._produce(mo_a)
        self.assertFalse(order.commitment_date)
        self._produce(mo_b)
        self.assertEqual(order.commitment_date.date(), max(mo_a.date_finished, mo_b.date_finished).date())

    def test_switched_off_leaves_delivery_date(self):
        self.company.cl_handover_date_sync = 'none'
        order = self._order(self.product_a)
        self.assertFalse(order.commitment_date)

    # ---- handover ----

    def test_handover_notifies_salesman_when_all_handed_over(self):
        order = self._order(self.product_a | self.product_b)
        mo_a, mo_b = order.cl_production_ids[0], order.cl_production_ids[1]
        self.assertEqual(order.cl_handover_state, 'waiting')
        with self.assertRaises(UserError):
            mo_a.with_user(self.mrp_user).action_cl_hand_over()
        self._produce(mo_a)
        self._produce(mo_b)

        mo_a.with_user(self.mrp_user).action_cl_hand_over()
        self.assertTrue(mo_a.cl_handed_over)
        self.assertEqual(mo_a.cl_handover_user_id, self.mrp_user)
        self.assertEqual(order.cl_handover_state, 'partial')
        self.assertFalse(self._ready_activities(order))

        mo_b.with_user(self.mrp_user).action_cl_hand_over()
        self.assertEqual(order.cl_handover_state, 'done')
        activities = self._ready_activities(order)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.salesman)
        # Handing over again does not create a second activity.
        mo_b.with_user(self.mrp_user).action_cl_hand_over()
        self.assertEqual(len(self._ready_activities(order)), 1)

    def test_undo_handover_by_manager_only(self):
        order = self._order(self.product_a)
        production = order.cl_production_ids
        self._produce(production)
        production.with_user(self.mrp_user).action_cl_hand_over()
        self.assertEqual(len(self._ready_activities(order)), 1)
        with self.assertRaises(UserError):
            production.with_user(self.mrp_user).action_cl_undo_handover()
        production.with_user(self.mrp_manager).action_cl_undo_handover()
        self.assertFalse(production.cl_handed_over)
        self.assertEqual(order.cl_handover_state, 'waiting')
        self.assertFalse(self._ready_activities(order))

    def test_handover_fields_only_through_the_buttons(self):
        order = self._order(self.product_a)
        production = order.cl_production_ids
        with self.assertRaises(AccessError):
            production.with_user(self.mrp_user).write({'cl_handed_over': True})
        self._produce(production)
        production.with_user(self.mrp_user).action_cl_hand_over()
        # Undoing is for managers, through the button that tells the salesperson.
        with self.assertRaises(AccessError):
            production.with_user(self.mrp_user).write({'cl_handed_over': False})
        with self.assertRaises(AccessError):
            production.with_user(self.mrp_manager).write({'cl_handover_date': False})
        self.assertTrue(production.cl_handed_over)
        self.assertEqual(len(self._ready_activities(order)), 1)

    # ---- ready for collection ----

    def test_ready_for_collection_email_once(self):
        order = self._order(self.stock_product, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        self.assertEqual(picking.state, 'assigned')
        self.assertTrue(picking.cl_collection_ready_sent)
        mail = self._mails(picking, 'ready for collection')
        self.assertEqual(len(mail), 1)
        # Sent in the name of the salesperson, so the customer's reply reaches them
        # (also when the daily job or a user without email address triggers it).
        self.assertIn('sales@example.com', mail.email_from)
        picking.do_unreserve()
        picking.action_assign()
        picking.action_assign()
        self.assertEqual(len(self._mails(picking, 'ready for collection')), 1)

    def test_customer_without_email_is_logged_not_sent(self):
        self.customer.email = False
        order = self._order(self.stock_product, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        self.assertTrue(picking.cl_collection_ready_sent)
        self.assertFalse(self._mails(picking, 'collection'))
        self.assertFalse(picking.cl_collection_next_reminder, "No reminders without an email")
        self.assertTrue(any('no email address' in (m.body or '') for m in picking.message_ids))

    def test_no_email_for_other_delivery_methods(self):
        order = self._order(self.stock_product, carrier_id=self.courier.id)
        picking = order.picking_ids
        self.assertEqual(picking.state, 'assigned')
        self.assertFalse(picking.cl_collection_ready_sent)
        self.assertFalse(self._mails(picking, 'collection'))

    def test_collection_email_waits_for_manufacturing(self):
        order = self._order(self.product_a, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        self.assertFalse(picking.cl_collection_ready_sent)
        self._produce(order.cl_production_ids)
        self.assertEqual(picking.state, 'assigned')
        self.assertEqual(len(self._mails(picking, 'ready for collection')), 1)

    def test_reminders_idempotent_and_limited(self):
        order = self._order(self.stock_product, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        self.assertTrue(picking.cl_collection_next_reminder)
        Picking = self.env['stock.picking']
        picking.cl_collection_next_reminder = fields.Datetime.now() - timedelta(hours=1)
        Picking._cl_cron_collection_reminders()
        self.assertEqual(len(self._mails(picking, 'reminder')), 1)
        self.assertEqual(picking.cl_collection_reminder_count, 1)
        Picking._cl_cron_collection_reminders()
        self.assertEqual(len(self._mails(picking, 'reminder')), 1, "A second run the same day sends nothing")
        picking.cl_collection_next_reminder = fields.Datetime.now() - timedelta(hours=1)
        Picking._cl_cron_collection_reminders()
        self.assertEqual(len(self._mails(picking, 'reminder')), 2)
        self.assertFalse(picking.cl_collection_next_reminder, "Maximum reached")

    def test_reminders_stop_after_collection(self):
        order = self._order(self.stock_product, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertFalse(picking.cl_collection_next_reminder)
        picking.cl_collection_next_reminder = fields.Datetime.now() - timedelta(hours=1)
        self.env['stock.picking']._cl_cron_collection_reminders()
        self.assertFalse(self._mails(picking, 'reminder'))

    def test_reminders_stop_after_cancel(self):
        order = self._order(self.stock_product, carrier_id=self.collection_carrier.id)
        picking = order.picking_ids
        picking.action_cancel()
        self.assertFalse(picking.cl_collection_next_reminder)
        self.env['stock.picking']._cl_cron_collection_reminders()
        self.assertFalse(self._mails(picking, 'reminder'))
