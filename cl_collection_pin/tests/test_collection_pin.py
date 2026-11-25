# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

from odoo.addons.cl_collection_pin.models.sale_order import CL_PIN_WRITE_CTX, cl_hash_pin


@tagged('post_install', '-at_install')
class TestCollectionPin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.cl_pin_max_attempts = 5
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.warehouse.delivery_steps = 'ship_only'
        fee = cls.env['product.product'].create({
            'name': 'Delivery Fee', 'type': 'service', 'list_price': 0.0,
            'invoice_policy': 'order', 'sale_ok': False, 'purchase_ok': False})
        carrier_vals = {'delivery_type': 'fixed', 'fixed_price': 0.0, 'product_id': fee.id}
        cls.collect = cls.env['delivery.carrier'].create(
            dict(carrier_vals, name='Click & Collect', cl_is_collection=True))
        cls.collect_2 = cls.env['delivery.carrier'].create(
            dict(carrier_vals, name='Collect at Branch 2', cl_is_collection=True))
        cls.courier = cls.env['delivery.carrier'].create(
            dict(carrier_vals, name='Courier'))
        cls.product = cls.env['product.product'].create({
            'name': 'Kettle', 'type': 'consu', 'is_storable': True, 'list_price': 20.0})
        cls.env['stock.quant']._update_available_quantity(
            cls.product, cls.warehouse.lot_stock_id, 100)
        cls.customer = cls.env['res.partner'].create(
            {'name': 'Collecting Customer', 'email': 'collect@customer.example'})
        cls.salesman = cls._user('cl_pin_salesman', ['sales_team.group_sale_salesman'])
        cls.stock_user = cls._user('cl_pin_stock_user', ['stock.group_stock_user'])
        cls.stock_manager = cls._user('cl_pin_stock_manager', ['stock.group_stock_manager'])

    @classmethod
    def _user(cls, login, groups):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login,
            'login': login,
            'email': '%s@example.com' % login,
            'groups_id': [(6, 0, [cls.env.ref(xmlid).id for xmlid in ['base.group_user'] + groups])],
        })

    def setUp(self):
        super().setUp()
        # Capture the clear PIN on its way to the email: it is stored nowhere else.
        self.pins = []
        SaleOrder = type(self.env['sale.order'])
        send_pin_email = SaleOrder._cl_send_pin_email
        pins = self.pins

        def capture_pin(order, pin):
            pins.append(pin)
            return send_pin_email(order, pin)

        patcher = patch.object(SaleOrder, '_cl_send_pin_email', capture_pin)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _order(self, carrier=None, qty=2, partner=None):
        return self.env['sale.order'].create({
            'partner_id': (partner or self.customer).id,
            'user_id': self.salesman.id,
            'warehouse_id': self.warehouse.id,
            'carrier_id': (carrier or self.collect).id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': qty})],
        })

    def _confirmed_order(self, **kwargs):
        order = self._order(**kwargs)
        order.action_confirm()
        return order

    def _delivery(self, order):
        return order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state not in ('done', 'cancel'))

    def _logs(self, order, event):
        return self.env['cl.collection.pin.log'].search(
            [('cl_order_id', '=', order.id), ('cl_event', '=', event)])

    def _wrong_pin(self, pin):
        return '000000' if pin != '000000' else '111111'

    def _verify(self, picking, pin, user=None):
        """Click Validate on the delivery and enter ``pin`` in the wizard."""
        picking = picking.with_user(user) if user else picking
        action = picking.button_validate()
        self.assertEqual(action.get('res_model'), 'cl.collection.pin.verify')
        wizard = self.env['cl.collection.pin.verify'].with_user(user or self.env.user).browse(action['res_id'])
        wizard.cl_pin = pin
        return wizard, wizard.action_cl_verify()

    # ------------------------------------------------------------------
    # issuing
    # ------------------------------------------------------------------

    def test_pin_issued_on_confirm_one_step(self):
        order = self._confirmed_order()
        self.assertTrue(order.cl_is_collection_order)
        self.assertEqual(order.cl_pin_state, 'active')
        self.assertTrue(order.cl_pin_issued_at)
        self.assertEqual(len(self.pins), 1)
        pin = self.pins[0]
        self.assertRegex(pin, r'^[0-9]{6}$')
        # Only a salted hash is stored.
        order_sudo = order.sudo()
        self.assertTrue(order_sudo.cl_pin_salt)
        self.assertNotEqual(order_sudo.cl_pin_hash, pin)
        self.assertEqual(order_sudo.cl_pin_hash, cl_hash_pin(pin, order_sudo.cl_pin_salt))
        self.assertEqual(len(self._logs(order, 'issued')), 1)
        # Never issued twice while a PIN is active.
        order._cl_auto_issue_pin()
        self.assertEqual(len(self.pins), 1)
        self.assertTrue(self._delivery(order).cl_is_collection_delivery)

    def test_pin_issued_when_pick_done_two_steps(self):
        self.warehouse.delivery_steps = 'pick_ship'
        order = self._confirmed_order()
        self.assertEqual(order.cl_pin_state, 'none', "Goods are not picked yet")
        self.assertFalse(self.pins)
        pick = order.picking_ids.filtered(lambda p: p.picking_type_code == 'internal')
        self.assertTrue(pick)
        self.assertFalse(pick.cl_is_collection_delivery, "Only the delivery needs the PIN")
        pick.button_validate()
        self.assertEqual(pick.state, 'done')
        self.assertEqual(order.cl_pin_state, 'active')
        self.assertEqual(len(self.pins), 1)

    def test_no_pin_for_other_delivery_methods(self):
        order = self._confirmed_order(carrier=self.courier)
        self.assertFalse(order.cl_is_collection_order)
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertFalse(self.pins)
        delivery = self._delivery(order)
        self.assertFalse(delivery.cl_is_collection_delivery)
        delivery.button_validate()
        self.assertEqual(delivery.state, 'done')
        # No restriction on changing the carrier of a normal order.
        order.carrier_id = self.collect_2
        order.carrier_id = self.courier
        self.assertEqual(order.cl_pin_state, 'none')

    def test_customer_without_email(self):
        customer = self.env['res.partner'].create({'name': 'No Email Customer'})
        order = self._confirmed_order(partner=customer)
        self.assertEqual(order.cl_pin_state, 'active')
        bodies = ' '.join(order.message_ids.mapped('body'))
        self.assertIn('could not be sent', bodies)
        self.assertNotIn(self.pins[0], bodies)
        self.assertIn('Not emailed', self._logs(order, 'issued').cl_note)

    # ------------------------------------------------------------------
    # verification
    # ------------------------------------------------------------------

    def test_validation_blocked_without_verification(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        action = delivery.button_validate()
        self.assertEqual(action['res_model'], 'cl.collection.pin.verify')
        self.assertNotEqual(delivery.state, 'done')
        # Hard guard for any other caller.
        with self.assertRaises(UserError):
            delivery._action_done()
        self.assertNotEqual(delivery.state, 'done')

    def test_wrong_pin_counts_and_does_not_raise(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        wizard, result = self._verify(delivery, self._wrong_pin(self.pins[0]), user=self.stock_user)
        self.assertEqual(result['res_model'], 'cl.collection.pin.verify')
        self.assertEqual(result['res_id'], wizard.id)
        self.assertTrue(wizard.cl_error)
        self.assertFalse(wizard.cl_pin, "The typed PIN is not kept")
        self.assertEqual(order.cl_pin_attempts, 1)
        self.assertEqual(order.cl_pin_state, 'active')
        failed = self._logs(order, 'failed')
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed.cl_attempt, 1)
        self.assertEqual(failed.cl_picking_id, delivery)
        self.assertEqual(failed.cl_user_id, self.stock_user)
        self.assertFalse(delivery.cl_pin_verified)
        self.assertNotEqual(delivery.state, 'done')

    def test_bad_format_is_not_an_attempt(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        action = delivery.button_validate()
        wizard = self.env['cl.collection.pin.verify'].browse(action['res_id'])
        for value in ('12ab56', '12345', ''):
            wizard.cl_pin = value
            with self.assertRaises(UserError):
                wizard.action_cl_verify()
        self.assertEqual(order.cl_pin_attempts, 0)
        self.assertFalse(self._logs(order, 'failed'))

    def test_lock_after_max_attempts(self):
        self.company.cl_pin_max_attempts = 3
        order = self._confirmed_order()
        pin = self.pins[0]
        delivery = self._delivery(order)
        for _attempt in range(3):
            self._verify(delivery, self._wrong_pin(pin))
        self.assertEqual(order.cl_pin_state, 'locked')
        self.assertEqual(order.cl_pin_attempts, 3)
        self.assertEqual(len(self._logs(order, 'locked')), 1)
        # Even the right PIN is refused once locked.
        action = delivery.button_validate()
        wizard = self.env['cl.collection.pin.verify'].browse(action['res_id'])
        wizard.cl_pin = pin
        with self.assertRaises(UserError):
            wizard.action_cl_verify()
        # Sales users cannot unlock; an Inventory Administrator can.
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).action_cl_send_new_pin()
        delivery.with_user(self.stock_manager).action_cl_send_new_pin()
        self.assertEqual(order.cl_pin_state, 'active')
        self.assertEqual(order.cl_pin_attempts, 0)
        new_pin = self.pins[-1]
        self.assertEqual(len(self.pins), 2)
        if new_pin != pin:
            self.assertFalse(order._cl_pin_matches(pin), "The old PIN no longer works")
        self._verify(delivery, new_pin)
        self.assertEqual(delivery.state, 'done')

    def test_right_pin_verifies_and_validates(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        self._verify(delivery, self.pins[0], user=self.stock_user)
        self.assertTrue(delivery.cl_pin_verified)
        self.assertEqual(delivery.state, 'done')
        self.assertEqual(order.cl_pin_state, 'used', "A PIN is used once")
        verified = self._logs(order, 'verified')
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified.cl_picking_id, delivery)

    def test_backorder_needs_its_own_verification(self):
        order = self._confirmed_order(qty=5)
        delivery = self._delivery(order)
        delivery.move_ids.write({'quantity': 2, 'picked': True})
        _wizard, result = self._verify(delivery, self.pins[0])
        self.assertEqual(result.get('res_model'), 'stock.backorder.confirmation')
        Form.from_action(self.env, result).save().process()
        self.assertEqual(delivery.state, 'done')
        backorder = delivery.backorder_ids
        self.assertTrue(backorder)
        self.assertFalse(backorder.cl_pin_verified)
        self.assertEqual(order.cl_pin_state, 'used')
        with self.assertRaises(UserError):
            backorder._action_done()
        # The used PIN is refused for the backorder: a new one must be sent.
        action = backorder.button_validate()
        wizard = self.env['cl.collection.pin.verify'].browse(action['res_id'])
        wizard.cl_pin = self.pins[0]
        with self.assertRaises(UserError):
            wizard.action_cl_verify()
        order.with_user(self.salesman).action_cl_send_new_pin()
        self.assertEqual(len(self._logs(order, 'resent')), 1)
        self._verify(backorder, self.pins[-1])
        self.assertEqual(backorder.state, 'done')

    # ------------------------------------------------------------------
    # resend / protection
    # ------------------------------------------------------------------

    def test_send_new_pin_rights(self):
        order = self._confirmed_order()
        with self.assertRaises(AccessError):
            order.with_user(self.stock_user).action_cl_send_new_pin()
        order.with_user(self.salesman).action_cl_send_new_pin()
        self.assertEqual(len(self.pins), 2)
        self.assertEqual(order.cl_pin_state, 'active')
        if self.pins[0] != self.pins[1]:
            self.assertFalse(order._cl_pin_matches(self.pins[0]))
        self.assertTrue(order._cl_pin_matches(self.pins[1]))

    def test_pin_fields_are_protected(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({'cl_pin_state': 'none'})
        with self.assertRaises(AccessError):
            # The context key alone is not enough (it can be sent over RPC).
            order.with_user(self.salesman).with_context(**{CL_PIN_WRITE_CTX: True}).write(
                {'cl_pin_attempts': 0})
        with self.assertRaises(AccessError):
            order.write({'cl_pin_hash': 'forged'})
        with self.assertRaises(AccessError):
            delivery.with_user(self.stock_user).write({'cl_pin_verified': True})
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).read(['cl_pin_hash'])

    # ------------------------------------------------------------------
    # bypass attempts (RPC context, rights, rewiring the delivery)
    # ------------------------------------------------------------------

    def test_context_defaults_cannot_forge_pin(self):
        salt = 'ab' * 16
        forged = {
            'default_cl_pin_hash': cl_hash_pin('123456', salt),
            'default_cl_pin_salt': salt,
            'default_cl_pin_state': 'active',
            'default_cl_pin_attempts': -50,
            # Sending the module's own context key does not help either.
            CL_PIN_WRITE_CTX: True,
        }
        order = self.env['sale.order'].with_user(self.salesman).with_context(**forged).create({
            'partner_id': self.customer.id,
            'warehouse_id': self.warehouse.id,
            'carrier_id': self.collect.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})],
        })
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertEqual(order.cl_pin_attempts, 0)
        self.assertFalse(order.sudo().cl_pin_hash)
        self.assertFalse(order.sudo().cl_pin_salt)
        with self.assertRaises(AccessError):
            self.env['sale.order'].create({
                'partner_id': self.customer.id, 'cl_pin_state': 'active'})
        # Also as superuser with the context key: core code creates records
        # as superuser with the caller's context.
        with self.assertRaises(AccessError):
            self.env['sale.order'].sudo().with_context(**{CL_PIN_WRITE_CTX: True}).create({
                'partner_id': self.customer.id, 'cl_pin_hash': 'forged'})

    def test_context_default_cannot_verify_backorder(self):
        order = self._confirmed_order(qty=5)
        delivery = self._delivery(order)
        delivery.move_ids.write({'quantity': 2, 'picked': True})
        forged = {'default_cl_pin_verified': True, CL_PIN_WRITE_CTX: True}
        action = delivery.with_context(**forged).button_validate()
        wizard = self.env['cl.collection.pin.verify'].with_context(**forged).browse(action['res_id'])
        wizard.cl_pin = self.pins[0]
        result = wizard.action_cl_verify()
        self.assertEqual(result.get('res_model'), 'stock.backorder.confirmation')
        backorder_wizard = Form.from_action(self.env, result).save()
        backorder_wizard.with_context(**forged).process()
        self.assertEqual(delivery.state, 'done')
        backorder = delivery.backorder_ids
        self.assertTrue(backorder)
        self.assertFalse(backorder.cl_pin_verified)
        with self.assertRaises(UserError):
            backorder._action_done()
        with self.assertRaises(AccessError):
            self.env['stock.picking'].sudo().with_context(**{CL_PIN_WRITE_CTX: True}).create({
                'picking_type_id': self.warehouse.out_type_id.id,
                'location_id': self.warehouse.lot_stock_id.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'cl_pin_verified': True,
            })

    def test_next_step_delivery_is_created_unverified(self):
        """The delivery created (as superuser) when the pick is done cannot be
        marked verified through the context of whoever validates the pick."""
        self.warehouse.delivery_steps = 'pick_ship'
        order = self._confirmed_order()
        pick = order.picking_ids.filtered(lambda p: p.picking_type_code == 'internal')
        pick.with_context(**{'default_cl_pin_verified': True, CL_PIN_WRITE_CTX: True}).button_validate()
        self.assertEqual(pick.state, 'done')
        delivery = self._delivery(order)
        self.assertTrue(delivery)
        self.assertTrue(delivery.cl_is_collection_delivery)
        self.assertFalse(delivery.cl_pin_verified)

    def test_carrier_change_needs_sales_rights(self):
        """Inventory users have write access to sales orders: they must not be
        able to switch the PIN check off by changing the delivery method."""
        order = self._confirmed_order()
        with self.assertRaises(AccessError):
            order.with_user(self.stock_user).write({'carrier_id': self.courier.id})
        with self.assertRaises(AccessError):
            order.with_user(self.stock_user).write({'carrier_id': False})
        self.assertEqual(order.carrier_id, self.collect)
        self.assertEqual(order.cl_pin_state, 'active')
        # Writing the same carrier is not a change.
        order.with_user(self.stock_user).write({'carrier_id': self.collect.id})
        # Sales users can: the PIN is cleared and it is logged.
        order.with_user(self.salesman).write({'carrier_id': self.courier.id})
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertEqual(len(self._logs(order, 'cleared')), 1)
        # Orders that are not waiting for a collection are not restricted.
        other = self._confirmed_order(carrier=self.courier)
        other.with_user(self.stock_user).write({'carrier_id': self.collect_2.id})
        self.assertEqual(other.carrier_id, self.collect_2)

    def test_carrier_change_cannot_unlock(self):
        self.company.cl_pin_max_attempts = 1
        order = self._confirmed_order()
        self._verify(self._delivery(order), self._wrong_pin(self.pins[0]))
        self.assertEqual(order.cl_pin_state, 'locked')
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).write({'carrier_id': self.collect_2.id})
        self.assertEqual(order.cl_pin_state, 'locked')
        order.with_user(self.stock_manager).write({'carrier_id': self.collect_2.id})
        self.assertEqual(order.cl_pin_state, 'none')

    def test_operation_type_switch_keeps_pin_check(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        delivery.write({'picking_type_id': self.warehouse.int_type_id.id})
        delivery.write({'location_dest_id': self.env.ref('stock.stock_location_customers').id})
        self.assertEqual(delivery.picking_type_code, 'internal')
        self.assertTrue(delivery.cl_is_collection_delivery)
        action = delivery.button_validate()
        self.assertEqual(action['res_model'], 'cl.collection.pin.verify')
        with self.assertRaises(UserError):
            delivery._action_done()
        self.assertNotEqual(delivery.state, 'done')

    def test_delivery_cannot_be_unlinked_from_order(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        with self.assertRaises(AccessError):
            delivery.with_user(self.stock_user).write({'sale_id': False})
        with self.assertRaises(AccessError):
            delivery.with_user(self.stock_user).write({'group_id': False})
        self.assertEqual(delivery.sale_id, order)
        self.assertTrue(delivery.cl_is_collection_delivery)

    def test_pin_email_goes_to_the_customer_only(self):
        template = self.env.ref('cl_collection_pin.mail_template_collection_pin')
        template.write({'email_cc': 'cc@spy.example', 'email_to': 'to@spy.example'})
        captured = []
        MailMail = type(self.env['mail.mail'])
        send = MailMail.send

        def capture_send(mails, *args, **kwargs):
            for mail in mails:
                # Only the PIN email (other apps may send their own emails).
                if self.pins and self.pins[-1] in (mail.body_html or ''):
                    captured.append((mail.email_to, mail.email_cc, mail.recipient_ids))
            return send(mails, *args, **kwargs)

        with patch.object(MailMail, 'send', capture_send):
            order = self._confirmed_order()
        self.assertEqual(order.cl_pin_state, 'active')
        self.assertEqual(len(captured), 1)
        email_to, email_cc, recipients = captured[0]
        self.assertFalse(email_to)
        self.assertFalse(email_cc)
        self.assertEqual(recipients, self.customer)

    # ------------------------------------------------------------------
    # users at the counter
    # ------------------------------------------------------------------

    def test_user_without_email_can_enter_pin(self):
        """Chatter notes are logged, not posted: no sender address is needed."""
        clerk = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Counter Clerk',
            'login': 'cl_pin_clerk',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('stock.group_stock_user').id])],
        })
        clerk.partner_id.email = False
        order = self._confirmed_order()
        delivery = self._delivery(order)
        wizard, _result = self._verify(delivery, self._wrong_pin(self.pins[0]), user=clerk)
        self.assertTrue(wizard.cl_error)
        self.assertEqual(order.cl_pin_attempts, 1)
        self.assertIn('Wrong collection PIN', ' '.join(order.message_ids.mapped('body')))
        self.assertIn('Wrong collection PIN', ' '.join(delivery.message_ids.mapped('body')))

    def test_user_limited_to_own_orders_can_enter_pin(self):
        """A user who is 'Sales: own documents only' and Inventory user cannot
        read the orders of other salespeople, but must still be able to check
        the PIN of their deliveries."""
        clerk = self._user('cl_pin_own_docs', [
            'sales_team.group_sale_salesman', 'stock.group_stock_user'])
        order = self._confirmed_order()
        self.assertNotEqual(order.user_id, clerk)
        with self.assertRaises(AccessError):
            order.with_user(clerk).read(['name'])
        delivery = self._delivery(order)
        with self.assertRaises(UserError) as error:
            delivery.with_user(clerk)._action_done()
        self.assertNotIsInstance(error.exception, AccessError)
        wizard, _result = self._verify(delivery, self._wrong_pin(self.pins[0]), user=clerk)
        self.assertTrue(wizard.cl_error)
        self.assertEqual(wizard.cl_attempts_left, 4)
        self.assertEqual(order.cl_pin_attempts, 1)
        # ... but cannot send a new PIN for an order they cannot see.
        with self.assertRaises(AccessError):
            order.with_user(clerk).action_cl_send_new_pin()

    # ------------------------------------------------------------------
    # carrier / state changes
    # ------------------------------------------------------------------

    def test_carrier_change_clears_pin(self):
        order = self._confirmed_order()
        order.carrier_id = self.collect_2
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertFalse(order.sudo().cl_pin_hash)
        cleared = self._logs(order, 'cleared')
        self.assertEqual(len(cleared), 1)
        self.assertIn('delivery method changed', cleared.cl_note)

        order.with_user(self.salesman).action_cl_send_new_pin()
        self.assertEqual(order.cl_pin_state, 'active')
        order.carrier_id = self.courier
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertEqual(len(self._logs(order, 'cleared')), 2)
        # No longer a collection: the delivery validates normally.
        delivery = self._delivery(order)
        self.assertFalse(delivery.cl_is_collection_delivery)
        delivery.button_validate()
        self.assertEqual(delivery.state, 'done')

    def test_cancel_expires_once_and_draft_clears(self):
        order = self._confirmed_order()
        order._action_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertEqual(order.cl_pin_state, 'expired')
        expired = self._logs(order, 'expired')
        self.assertEqual(len(expired), 1)
        self.assertIn('cancelled', expired.cl_note)
        order._cl_expire_if_collected()
        self.assertEqual(len(self._logs(order, 'expired')), 1)
        order.action_draft()
        self.assertEqual(order.cl_pin_state, 'none')
        self.assertEqual(len(self._logs(order, 'cleared')), 1)

    def test_cancelled_delivery_expires_once(self):
        order = self._confirmed_order()
        self._delivery(order).action_cancel()
        self.assertEqual(order.cl_pin_state, 'expired')
        order._cl_expire_if_collected()
        order._action_cancel()
        self.assertEqual(len(self._logs(order, 'expired')), 1)

    # ------------------------------------------------------------------
    # the PIN never leaks
    # ------------------------------------------------------------------

    def test_pin_never_in_chatter_mail_or_log(self):
        order = self._confirmed_order()
        delivery = self._delivery(order)
        self._verify(delivery, self._wrong_pin(self.pins[0]))
        order.with_user(self.salesman).action_cl_send_new_pin()
        self._verify(delivery, self.pins[-1])
        self.assertEqual(delivery.state, 'done')
        self.assertEqual(len(self.pins), 2)

        messages = self.env['mail.message'].sudo().search([
            '|',
            '&', ('model', '=', 'sale.order'), ('res_id', '=', order.id),
            '&', ('model', '=', 'stock.picking'), ('res_id', 'in', order.picking_ids.ids),
        ])
        self.assertTrue(messages)
        logs = self.env['cl.collection.pin.log'].search([('cl_order_id', '=', order.id)])
        self.assertTrue(logs)
        for pin in self.pins:
            for message in messages:
                self.assertNotIn(pin, message.body or '')
                self.assertNotIn(pin, message.subject or '')
            for log in logs:
                self.assertNotIn(pin, log.cl_note or '')
            self.assertFalse(
                self.env['mail.mail'].sudo().search([('body_html', 'ilike', pin)]),
                "No email holding the PIN is left in the database")
