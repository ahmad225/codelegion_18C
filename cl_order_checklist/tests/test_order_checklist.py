# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOrderChecklist(TransactionCase):
    """Run with:  odoo-bin -d <db> -i cl_order_checklist --test-tags /cl_order_checklist

    The gate lets the superuser through (automatic operations), so everything
    a person does is done here as a real user.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.Item = cls.env['cl.order.checklist.item']
        cls.Line = cls.env['cl.order.checklist.line']
        # start from an empty checklist whatever the database holds
        cls.Item.search([]).action_archive()

        cls.partner = cls.env['res.partner'].create({'name': 'Buyer'})
        cls.product = cls.env['product.product'].create(
            {'name': 'Thing', 'type': 'consu', 'list_price': 10.0})
        cls.salesperson = new_test_user(
            cls.env, login='cl_checklist_salesperson',
            groups='sales_team.group_sale_salesman_all_leads')
        cls.own_docs_salesperson = new_test_user(
            cls.env, login='cl_checklist_own_docs',
            groups='sales_team.group_sale_salesman')
        cls.sales_manager = new_test_user(
            cls.env, login='cl_checklist_sales_manager',
            groups='sales_team.group_sale_manager')
        cls.mrp_user = new_test_user(
            cls.env, login='cl_checklist_mrp_user',
            groups='mrp.group_mrp_user')

        cls.required = cls.Item.create({'name': 'Address confirmed', 'applies_to': 'sale'})
        cls.reminder = cls.Item.create(
            {'name': 'Offer the service contract', 'applies_to': 'sale', 'blocking': False})
        cls.mrp_required = cls.Item.create({'name': 'QC passed', 'applies_to': 'mrp'})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _quotation(self, user=None):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': (user or self.salesperson).id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_uom_qty': 1})],
        })

    def _line(self, order, item):
        return order.cl_checklist_line_ids.filtered(lambda line: line.item_id == item)

    def _tick(self, order, item, user=None, done=True):
        """Tick the way the form does: through the order."""
        line = self._line(order, item)
        order.with_user(user or self.salesperson).write(
            {'cl_checklist_line_ids': [Command.update(line.id, {'done': done})]})
        return line

    # ------------------------------------------------------------------
    # lines
    # ------------------------------------------------------------------
    def test_new_quotation_gets_its_checklist(self):
        order = self.env['sale.order'].with_user(self.salesperson).create(
            {'partner_id': self.partner.id})
        self.assertEqual(order.cl_checklist_line_ids.item_id, self.required | self.reminder)
        self.assertEqual(order.cl_checklist_progress, 0.0)
        self.assertEqual(order.cl_checklist_required_left, 1)

    def test_item_added_later_reaches_open_quotations_only(self):
        open_order = self._quotation()
        confirmed = self._quotation()
        self._tick(confirmed, self.required)
        confirmed.with_user(self.salesperson).action_confirm()
        new_item = self.Item.with_user(self.sales_manager).create(
            {'name': 'Deposit received', 'applies_to': 'sale'})
        self.assertTrue(self._line(open_order, new_item))
        self.assertFalse(self._line(confirmed, new_item))

    def test_item_of_another_company_is_not_used(self):
        other_company = self.env['res.company'].create({'name': 'Checklist Other Co'})
        foreign = self.Item.create(
            {'name': 'Other company check', 'applies_to': 'sale', 'company_id': other_company.id})
        shared = self.Item.create(
            {'name': 'Group-wide check', 'applies_to': 'sale', 'company_id': False,
             'blocking': False})
        order = self._quotation()
        self.assertFalse(self._line(order, foreign))
        self.assertTrue(self._line(order, shared))

    def test_archived_item_leaves_open_quotations(self):
        order = self._quotation()
        self._tick(order, self.reminder)
        (self.required | self.reminder).action_archive()
        # the unticked line goes, the ticked one stays as a record
        self.assertFalse(self._line(order, self.required))
        self.assertTrue(self._line(order, self.reminder))
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    # ------------------------------------------------------------------
    # ticking
    # ------------------------------------------------------------------
    def test_tick_records_who_and_when_and_logs_it(self):
        order = self._quotation()
        messages_before = len(order.message_ids)
        line = self._tick(order, self.required)
        self.assertTrue(line.done)
        self.assertEqual(line.done_by_id, self.salesperson)
        self.assertTrue(line.done_on)
        self.assertEqual(order.cl_checklist_progress, 50.0)
        self.assertEqual(order.cl_checklist_required_left, 0)
        self.assertEqual(len(order.message_ids), messages_before + 1)
        self.assertIn('Address confirmed', order.message_ids[0].body)

        self._tick(order, self.required, done=False)
        self.assertFalse(line.done)
        self.assertFalse(line.done_by_id)
        self.assertFalse(line.done_on)
        self.assertEqual(len(order.message_ids), messages_before + 2)

    def test_users_can_only_tick(self):
        order = self._quotation()
        line = self._line(order, self.required)
        with self.assertRaises(AccessError):
            line.with_user(self.salesperson).write({'item_id': self.reminder.id})
        with self.assertRaises(AccessError):
            line.with_user(self.salesperson).write({'done': True, 'done_by_id': self.sales_manager.id})
        with self.assertRaises(AccessError):
            self.Line.with_user(self.salesperson).create(
                {'item_id': self.mrp_required.id, 'sale_order_id': order.id})

    def test_ticking_needs_access_to_the_order(self):
        order = self._quotation()  # belongs to another salesperson
        line = self._line(order, self.required)
        with self.assertRaises(AccessError):
            line.with_user(self.own_docs_salesperson).write({'done': True})
        self.assertFalse(line.done)

    def test_only_managers_manage_the_items(self):
        with self.assertRaises(AccessError):
            self.Item.with_user(self.salesperson).create({'name': 'Mine', 'applies_to': 'sale'})
        with self.assertRaises(AccessError):
            self.required.with_user(self.salesperson).write({'blocking': False})
        self.required.with_user(self.sales_manager).write({'name': 'Delivery address confirmed'})

    # ------------------------------------------------------------------
    # sales gate
    # ------------------------------------------------------------------
    def test_confirm_blocked_until_required_ticked(self):
        order = self._quotation()
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'draft')
        self._tick(order, self.required)
        # the reminder is not ticked and does not block
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_quotation_older_than_the_item_is_held_too(self):
        """An order with no line for a required item (made before the app was
        installed, say) is not let through by accident."""
        order = self._quotation()
        self._line(order, self.required).unlink()
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()

    def test_item_added_while_cancelled_can_be_ticked_after_reset(self):
        order = self._quotation()
        order._action_cancel()
        late = self.Item.create({'name': 'Deposit received', 'applies_to': 'sale'})
        self.assertFalse(self._line(order, late))
        order.action_draft()
        self.assertTrue(self._line(order, late))
        self._tick(order, self.required)
        with self.assertRaises(UserError):
            order.with_user(self.salesperson).action_confirm()
        self._tick(order, late)
        order.with_user(self.salesperson).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_skip_context_bypasses(self):
        order = self._quotation()
        order.with_user(self.salesperson).with_context(cl_skip_checklist=True).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_automatic_confirmation_is_let_through_and_logged(self):
        """Online payment and customer signature confirm in superuser mode."""
        order = self._quotation()
        messages_before = len(order.message_ids)
        order.sudo().action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertGreater(len(order.message_ids), messages_before)
        self.assertTrue(any(
            'Address confirmed' in (message.body or '') for message in order.message_ids))

    # ------------------------------------------------------------------
    # manufacturing gate
    # ------------------------------------------------------------------
    def test_manufacturing_order_held_at_mark_as_done(self):
        production = self.env['mrp.production'].with_user(self.mrp_user).create({
            'product_id': self.product.id,
            'product_qty': 1.0,
        })
        line = production.cl_checklist_line_ids
        self.assertEqual(line.item_id, self.mrp_required)
        # confirming and producing are not held up
        production.action_confirm()
        self.assertNotIn(production.state, ('draft', 'done', 'cancel'))
        with self.assertRaises(UserError):
            production.button_mark_done()
        self.assertNotEqual(production.state, 'done')

        production.write({'cl_checklist_line_ids': [Command.update(line.id, {'done': True})]})
        self.assertEqual(line.done_by_id, self.mrp_user)
        self.assertFalse(production._cl_checklist_missing())
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
