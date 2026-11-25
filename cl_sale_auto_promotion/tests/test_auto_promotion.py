# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAutoPromotion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Existing programs (demo data) must not interfere.
        cls.env['loyalty.program'].search([]).write({'active': False})
        cls.company = cls.env.company
        cls.company.cl_promo_auto_apply = True
        cls.partner = cls.env['res.partner'].create({'name': 'Promotion Customer'})
        cls.product = cls._product('Widget', 100.0)
        cls.gift = cls._product('Free Gift', 20.0)
        cls.topup = cls._product('eWallet Top-up', 50.0)

    @classmethod
    def _product(cls, name, price):
        return cls.env['product.product'].create({
            'name': name,
            'list_price': price,
            'invoice_policy': 'order',
            'taxes_id': [Command.clear()],
        })

    def _promotion(self, name, reward_vals, rule_vals=None, **program_vals):
        return self.env['loyalty.program'].create({
            'name': name,
            'program_type': 'promotion',
            'trigger': 'auto',
            'applies_on': 'current',
            'rule_ids': [Command.create({
                'reward_point_mode': 'order',
                'reward_point_amount': 1,
                **(rule_vals or {}),
            })],
            'reward_ids': [Command.create({'required_points': 1, **reward_vals})],
            **program_vals,
        })

    def _percent_promotion(self, name, percent=10, **reward_vals):
        return self._promotion(name, {
            'reward_type': 'discount',
            'discount_mode': 'percent',
            'discount': percent,
            'discount_applicability': 'order',
            **reward_vals,
        })

    def _order(self, qty=1.0):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_uom_qty': qty})],
        })

    def _set_qty(self, order, qty):
        line = order.order_line.filtered(lambda l: l.product_id == self.product and not l.reward_id)
        order.write({'order_line': [Command.update(line.id, {'product_uom_qty': qty})]})

    def _ewallet(self, points):
        program = self.env['loyalty.program'].create({
            'name': 'Test eWallet',
            'program_type': 'ewallet',
            'trigger': 'auto',
            'applies_on': 'future',
            'rule_ids': [Command.create({
                'reward_point_amount': 1,
                'reward_point_mode': 'money',
                'product_ids': [Command.set(self.topup.ids)],
            })],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount_mode': 'per_point',
                'discount': 1,
            })],
            'trigger_product_ids': [Command.set(self.topup.ids)],
        })
        card = self.env['loyalty.card'].create({
            'program_id': program.id,
            'partner_id': self.partner.id,
            'points': points,
        })
        return program, card

    def _promotion_notes(self, order, text):
        return order.message_ids.filtered(lambda m: text in (m.body or ''))

    # ------------------------------------------------------------------

    def test_automatic_discount_applied(self):
        promo = self._percent_promotion('Ten Percent Off', 10)
        order = self._order()

        reward_lines = order.order_line.filtered('reward_id')
        self.assertEqual(reward_lines.reward_id, promo.reward_ids)
        self.assertTrue(all(reward_lines.mapped('cl_auto_applied')))
        self.assertAlmostEqual(order.amount_untaxed, 90.0)
        self.assertAlmostEqual(order.cl_promotion_savings, 10.0)
        self.assertFalse(order.cl_has_reward_choice)
        self.assertEqual(len(self._promotion_notes(order, 'Ten Percent Off')), 1)

        # A line change recomputes the automatic line, without a new note.
        self._set_qty(order, 2)
        reward_lines = order.order_line.filtered('reward_id')
        self.assertEqual(len(reward_lines), 1)
        self.assertAlmostEqual(order.amount_untaxed, 180.0)
        self.assertAlmostEqual(order.cl_promotion_savings, 20.0)
        self.assertEqual(len(self._promotion_notes(order, 'Ten Percent Off')), 1)

    def test_disabled_setting_does_nothing(self):
        self._percent_promotion('Ten Percent Off', 10)
        self.company.cl_promo_auto_apply = False
        order = self._order()
        self.assertFalse(order.order_line.filtered('reward_id'))

    def test_ewallet_and_loyalty_card_not_spent(self):
        promo = self._percent_promotion('Ten Percent Off', 10)
        ewallet_program, ewallet = self._ewallet(30)
        loyalty_program = self.env['loyalty.program'].create({
            'name': 'Test Loyalty Card',
            'program_type': 'loyalty',
            'trigger': 'auto',
            'applies_on': 'both',
            'rule_ids': [Command.create({'reward_point_mode': 'money', 'reward_point_amount': 1})],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount_mode': 'per_point',
                'discount': 0.1,
                'discount_applicability': 'order',
                'required_points': 10,
            })],
        })
        loyalty_card = self.env['loyalty.card'].create({
            'program_id': loyalty_program.id,
            'partner_id': self.partner.id,
            'points': 100,
        })

        order = self._order()

        # Both cards could pay for rewards on this order...
        claimable_coupons = set(order._get_claimable_rewards())
        self.assertIn(ewallet, claimable_coupons)
        self.assertIn(loyalty_card, claimable_coupons)
        # ...but only the automatic promotion was applied.
        self.assertEqual(order.order_line.filtered('reward_id').reward_id, promo.reward_ids)
        self.assertEqual(ewallet.points, 30)
        self.assertEqual(loyalty_card.points, 100)
        self.assertFalse(order.order_line.filtered(
            lambda l: l.reward_id.program_id in (ewallet_program | loyalty_program)))

    def test_manual_coupon_kept_after_line_change(self):
        promo = self._promotion('Widget Ten Percent', {
            'reward_type': 'discount',
            'discount_mode': 'percent',
            'discount': 10,
            'discount_applicability': 'specific',
            'discount_product_ids': [Command.set(self.product.ids)],
        })
        code_program = self.env['loyalty.program'].create({
            'name': 'Code Five Off',
            'program_type': 'promotion',
            'trigger': 'with_code',
            'applies_on': 'current',
            'rule_ids': [Command.create({'mode': 'with_code', 'code': 'CLFIVE'})],
            'reward_ids': [Command.create({
                'reward_type': 'discount',
                'discount_mode': 'per_order',
                'discount': 5,
                'discount_applicability': 'order',
                'required_points': 1,
            })],
        })
        order = self._order()
        self.assertEqual(order.order_line.filtered('reward_id').reward_id, promo.reward_ids)

        # The salesperson applies a promo code.
        claimable = order._try_apply_code('CLFIVE')
        self.assertNotIn('error', claimable)
        coupon = next(iter(claimable))
        result = order._apply_program_reward(code_program.reward_ids, coupon)
        self.assertFalse(result.get('error'))
        code_line = order.order_line.filtered(lambda l: l.reward_id == code_program.reward_ids)
        self.assertTrue(code_line)
        self.assertFalse(code_line.cl_auto_applied)

        self._set_qty(order, 3)

        code_line = order.order_line.filtered(lambda l: l.reward_id == code_program.reward_ids)
        self.assertTrue(code_line, "A promo code applied by the salesperson must be kept.")
        self.assertFalse(code_line.cl_auto_applied)
        self.assertAlmostEqual(code_line.price_subtotal, -5.0)
        auto_line = order.order_line.filtered(lambda l: l.reward_id == promo.reward_ids)
        self.assertEqual(len(auto_line), 1)
        self.assertTrue(auto_line.cl_auto_applied)
        self.assertLess(auto_line.price_subtotal, 0.0)

    def test_competing_discounts_ask_for_a_choice(self):
        promo_a = self._percent_promotion('Ten Percent Off', 10)
        promo_b = self._promotion('Fifteen Off', {
            'reward_type': 'discount',
            'discount_mode': 'per_order',
            'discount': 15,
            'discount_applicability': 'order',
        })
        order = self._order()

        self.assertTrue(order.cl_has_reward_choice)
        self.assertFalse(order.order_line.filtered('reward_id'), "Nothing may be picked silently.")

        action = order.action_open_reward_wizard()
        self.assertEqual(action.get('res_model'), 'sale.loyalty.reward.wizard')
        wizard = self.env['sale.loyalty.reward.wizard'].with_context(active_id=order.id).create({
            'selected_reward_id': promo_b.reward_ids.id,
        })
        self.assertIn(promo_a.reward_ids, wizard.reward_ids)
        wizard.action_apply()

        chosen = order.order_line.filtered('reward_id')
        self.assertEqual(chosen.reward_id, promo_b.reward_ids)
        self.assertFalse(chosen.cl_auto_applied)
        self.assertFalse(order.cl_has_reward_choice)

        # The salesperson's choice survives a line change, and is not doubled up.
        self._set_qty(order, 2)
        self.assertEqual(order.order_line.filtered('reward_id').reward_id, promo_b.reward_ids)
        self.assertFalse(order.cl_has_reward_choice)

    def test_removed_automatic_line_not_added_again(self):
        promo = self._percent_promotion('Ten Percent Off', 10)
        order = self._order()
        auto_line = order.order_line.filtered('reward_id')
        order.write({'order_line': [Command.delete(auto_line.id)]})
        self.assertFalse(order.order_line.filtered('reward_id'))
        self.assertIn(promo.reward_ids, order.cl_dismissed_reward_ids)
        self._set_qty(order, 2)
        self.assertFalse(order.order_line.filtered('reward_id'))

    def test_removed_line_forgotten_once_promotion_stops_applying(self):
        promo = self._percent_promotion('Bulk Ten Percent')
        promo.rule_ids.minimum_qty = 2
        order = self._order(qty=2)
        auto_line = order.order_line.filtered('reward_id')
        self.assertEqual(auto_line.reward_id, promo.reward_ids)
        order.write({'order_line': [Command.delete(auto_line.id)]})
        self.assertIn(promo.reward_ids, order.cl_dismissed_reward_ids)

        # Still earned: the removed promotion stays away.
        self._set_qty(order, 3)
        self.assertFalse(order.order_line.filtered('reward_id'))
        self.assertIn(promo.reward_ids, order.cl_dismissed_reward_ids)

        # No longer earned: the removal is forgotten...
        self._set_qty(order, 1)
        self.assertFalse(order.order_line.filtered('reward_id'))
        self.assertFalse(order.cl_dismissed_reward_ids)

        # ...so the promotion is applied again once it is earned again.
        self._set_qty(order, 2)
        auto_line = order.order_line.filtered('reward_id')
        self.assertEqual(auto_line.reward_id, promo.reward_ids)
        self.assertTrue(all(auto_line.mapped('cl_auto_applied')))

    def test_salesperson_without_email(self):
        """The chatter note must not block a user who has no email address."""
        promo = self._percent_promotion('Ten Percent Off', 10)
        salesperson = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Salesperson Without Email',
            'login': 'cl_auto_promotion_no_email',
            'email': False,
            'groups_id': [Command.set(self.env.ref('sales_team.group_sale_salesman').ids)],
        })
        self.assertFalse(salesperson.partner_id.email)

        order = self.env['sale.order'].with_user(salesperson).create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_uom_qty': 1.0})],
        })

        order = order.sudo()
        self.assertEqual(order.order_line.filtered('reward_id').reward_id, promo.reward_ids)
        self.assertEqual(len(self._promotion_notes(order, 'Ten Percent Off')), 1)

    def test_savings_free_product_and_excludes_ewallet(self):
        self._percent_promotion('Ten Percent Off', 10)
        gift_promo = self._promotion('Free Gift With Widget', {
            'reward_type': 'product',
            'reward_product_id': self.gift.id,
            'reward_product_qty': 1,
        }, rule_vals={'product_ids': [Command.set(self.product.ids)]})
        ewallet_program, ewallet = self._ewallet(30)
        order = self._order()

        gift_line = order.order_line.filtered(lambda l: l.reward_id == gift_promo.reward_ids)
        self.assertTrue(gift_line.cl_auto_applied)
        self.assertAlmostEqual(order.cl_promotion_savings, 10.0 + 20.0)

        # Paying part of the order with the eWallet is not a saving.
        result = order._apply_program_reward(ewallet_program.reward_ids, ewallet)
        self.assertFalse(result.get('error'))
        order._update_programs_and_rewards()
        ewallet_line = order.order_line.filtered(lambda l: l.reward_id == ewallet_program.reward_ids)
        self.assertAlmostEqual(ewallet_line.price_subtotal, -30.0)
        self.assertAlmostEqual(order.cl_promotion_savings, 10.0 + 20.0)

    def test_promotion_end_notice(self):
        promo = self._percent_promotion('Ten Percent Off', 10)
        today = fields.Date.context_today(promo)
        order = self._order()
        notice_fields = ['cl_promo_expiry_level', 'cl_promo_expiry_notice']
        self.assertFalse(order.cl_promo_expiry_level)
        self.assertFalse(order.cl_promo_expiry_notice)

        # Outside the notice period (3 days by default): nothing yet.
        promo.date_to = fields.Date.add(today, days=10)
        order.invalidate_recordset(notice_fields)
        self.assertFalse(order.cl_promo_expiry_level)

        promo.date_to = fields.Date.add(today, days=2)
        order.invalidate_recordset(notice_fields)
        self.assertEqual(order.cl_promo_expiry_level, 'soon')
        self.assertIn('Ten Percent Off', order.cl_promo_expiry_notice)

        promo.date_to = fields.Date.subtract(today, days=1)
        order.invalidate_recordset(notice_fields)
        self.assertEqual(order.cl_promo_expiry_level, 'ended')
        self.assertIn('Ten Percent Off', order.cl_promo_expiry_notice)

    def test_quotation_pdf_lists_promotions(self):
        promo = self._percent_promotion('Ten Percent Off', 10)
        promo.date_to = fields.Date.add(fields.Date.context_today(promo), days=30)
        ewallet_program, ewallet = self._ewallet(30)
        order = self._order()
        result = order._apply_program_reward(ewallet_program.reward_ids, ewallet)
        self.assertFalse(result.get('error'))

        # The eWallet pays, it is not a promotion.
        self.assertEqual(order._cl_get_applied_promotions(), promo)

        html = self.env['ir.actions.report']._render_qweb_html('sale.report_saleorder', order.ids)[0]
        html = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn('o_cl_applied_promotions', html)
        self.assertIn('Ten Percent Off', html)
        self.assertIn('(until', html)
        self.assertIn('o_cl_promotion_savings', html)

    def test_invoice_savings_from_invoiced_lines(self):
        if not self.env['account.journal'].search(
                [('type', '=', 'sale'), *self.env['account.journal']._check_company_domain(self.company)],
                limit=1):
            self.skipTest("No sales journal: install a chart of accounts to run this test.")
        self._percent_promotion('Ten Percent Off', 10)
        order = self._order()
        order.action_confirm()
        self.assertAlmostEqual(order.cl_promotion_savings, 10.0)

        self.env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=order.ids, active_id=order.id,
        ).create({
            'advance_payment_method': 'percentage',
            'amount': 50,
        }).create_invoices()
        down_payment = order.invoice_ids
        self.assertEqual(len(down_payment), 1)
        self.assertAlmostEqual(down_payment.cl_promotion_savings, 0.0)

        final = order._create_invoices(final=True)
        self.assertAlmostEqual(final.cl_promotion_savings, 10.0)
        self.assertAlmostEqual(down_payment.cl_promotion_savings, 0.0)
