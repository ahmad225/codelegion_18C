# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

# Set while the module (or sale_loyalty under it) works on an order, so the
# order_line writes it makes do not start the automatic promotions again.
CL_SKIP_CTX = 'cl_skip_auto_promotion'
# Set only while the module itself claims a reward, to tell its lines apart
# from the rewards the salesperson applies.
CL_AUTO_CLAIM_CTX = 'cl_auto_promotion_claim'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_has_reward_choice = fields.Boolean(
        string='Promotion Choice Pending', copy=False, readonly=True,
        help="Several promotions compete on this quotation; the salesperson "
             "has to choose which one to apply.")
    cl_dismissed_reward_ids = fields.Many2many(
        comodel_name='loyalty.reward',
        relation='cl_sale_order_dismissed_reward_rel',
        column1='order_id', column2='reward_id',
        string='Dismissed Automatic Rewards', copy=False, readonly=True,
        help="Automatic rewards the salesperson removed from this quotation. "
             "They are not added again automatically.")
    # One notice for the quotation: its level drives the colour of the banner.
    cl_promo_expiry_level = fields.Selection(
        selection=[('soon', 'Ending Soon'), ('ended', 'Ended')],
        string='Promotion End Notice Level', compute='_compute_cl_promo_expiry')
    cl_promo_expiry_notice = fields.Text(
        string='Promotion End Notice', compute='_compute_cl_promo_expiry')
    cl_promotion_savings = fields.Monetary(
        string='Promotion Savings', currency_field='currency_id',
        compute='_compute_cl_promotion_savings',
        help="Promotion discounts and free products on this order, tax "
             "excluded. eWallet and gift card payments are not savings and "
             "are not counted.")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    def _cl_promo_expiry_line(self, program, days_left):
        """Sentence shown on the quotation for a promotion close to its end."""
        end_date = format_date(self.env, program.date_to)
        if days_left < 0:
            return _(
                "\"%(promotion)s\" ended on %(date)s: its reward is dropped the "
                "next time this quotation is updated or confirmed.",
                promotion=program.name, date=end_date)
        if not days_left:
            return _("\"%(promotion)s\" ends today.", promotion=program.name)
        return _(
            "\"%(promotion)s\" ends on %(date)s (%(days)s days left).",
            promotion=program.name, date=end_date, days=days_left)

    @api.depends(
        'state',
        'company_id.cl_promo_expiry_notice_days',
        'order_line.reward_id',
    )
    def _compute_cl_promo_expiry(self):
        today = fields.Date.context_today(self)
        for order in self:
            level, lines = False, []
            if order.state in ('draft', 'sent'):
                horizon = order.company_id.cl_promo_expiry_notice_days
                dated_programs = order.sudo().order_line.reward_id.program_id.filtered('date_to')
                for program in dated_programs.sorted('date_to'):
                    days_left = (program.date_to - today).days
                    if days_left > horizon:
                        continue
                    if days_left < 0:
                        level = 'ended'
                    lines.append(order._cl_promo_expiry_line(program, days_left))
                if lines and not level:
                    level = 'soon'
            order.cl_promo_expiry_level = level
            order.cl_promo_expiry_notice = '\n'.join(lines) if lines else False

    @api.depends(
        'currency_id',
        'order_line.reward_id',
        'order_line.price_subtotal',
        'order_line.price_unit',
        'order_line.product_uom_qty',
        'order_line.tax_id',
    )
    def _compute_cl_promotion_savings(self):
        for order in self:
            savings = sum(line._cl_get_promotion_saving() for line in order.order_line)
            order.cl_promotion_savings = order.currency_id.round(savings) if order.currency_id else savings

    def _cl_get_applied_promotions(self):
        """Promotions that give a reward on this order, for the quotation PDF.

        eWallets and gift cards are a means of payment and are left out.
        """
        self.ensure_one()
        programs = self.sudo().order_line.reward_id.program_id
        return programs.filtered(lambda program: not program.is_payment_program)

    # ------------------------------------------------------------------
    # ORM / flow hooks
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        if not self.env.context.get(CL_SKIP_CTX):
            orders._cl_apply_auto_promotions()
        return orders

    def write(self, vals):
        run = not self.env.context.get(CL_SKIP_CTX) and any(
            fname in vals for fname in ('order_line', 'pricelist_id'))
        if run and 'order_line' in vals:
            self._cl_remember_dismissed_rewards(vals['order_line'])
        res = super().write(vals)
        if run:
            self._cl_apply_auto_promotions()
        return res

    def copy(self, default=None):
        # sale_loyalty drops the copied reward lines after the copy: apply the
        # promotions once that is done, not in the create() of the copy.
        new_orders = super(SaleOrder, self.with_context(**{CL_SKIP_CTX: True})).copy(default=default)
        new_orders = new_orders.with_env(self.env)
        if not self.env.context.get(CL_SKIP_CTX):
            new_orders._cl_apply_auto_promotions()
        return new_orders

    def action_confirm(self):
        # sale_loyalty validates and refreshes the rewards itself on confirm.
        return super(SaleOrder, self.with_context(**{CL_SKIP_CTX: True})).action_confirm()

    def _update_order_line_info(self, product_id, quantity, **kwargs):
        # The product catalog creates and edits lines without writing the order.
        price_unit = super()._update_order_line_info(product_id, quantity, **kwargs)
        if not self.env.context.get(CL_SKIP_CTX):
            self._cl_apply_auto_promotions()
        return price_unit

    # ------------------------------------------------------------------
    # sale_loyalty overrides: keep track of the lines this module added
    # ------------------------------------------------------------------

    def _update_programs_and_rewards(self):
        auto_keys = self._cl_auto_reward_keys()
        res = super(SaleOrder, self.with_context(**{CL_SKIP_CTX: True}))._update_programs_and_rewards()
        # Reward lines are reset and reused by sale_loyalty: put the mark back
        # on the lines that still carry an automatically claimed reward.
        self._cl_sync_auto_flags(auto_keys)
        return res

    def _apply_program_reward(self, reward, coupon, **kwargs):
        self.ensure_one()
        auto_keys = self._cl_auto_reward_keys()
        is_auto_claim = bool(self.env.context.get(CL_AUTO_CLAIM_CTX))
        result = super(SaleOrder, self.with_context(**{CL_SKIP_CTX: True}))._apply_program_reward(
            reward, coupon, **kwargs)
        if not result.get('error'):
            if is_auto_claim:
                auto_keys.add((reward.id, coupon.id))
            elif self.cl_has_reward_choice and reward.program_id._cl_is_automatic_promotion():
                # The salesperson picked one of the competing promotions.
                self.with_context(**{CL_SKIP_CTX: True}).cl_has_reward_choice = False
        self._cl_sync_auto_flags(auto_keys)
        return result

    # ------------------------------------------------------------------
    # Automatic promotions
    # ------------------------------------------------------------------

    def _cl_auto_promotion_applicable(self):
        self.ensure_one()
        if self.state not in ('draft', 'sent') or not self.company_id.cl_promo_auto_apply:
            return False
        # eCommerce carts have their own automatic rewards (website_sale_loyalty).
        if 'website_id' in self._fields and self.website_id:
            return False
        return True

    def _cl_apply_auto_promotions(self):
        for order in self.with_context(**{CL_SKIP_CTX: True}):
            if order._cl_auto_promotion_applicable():
                order._cl_refresh_auto_promotions()
            elif order.cl_has_reward_choice:
                order.cl_has_reward_choice = False

    def _cl_auto_reward_keys(self):
        self.ensure_one()
        return {
            (line.reward_id.id, line.coupon_id.id)
            for line in self.order_line
            if line.cl_auto_applied and line.reward_id
        }

    def _cl_sync_auto_flags(self, auto_keys):
        self.ensure_one()
        to_mark = self.env['sale.order.line']
        to_unmark = self.env['sale.order.line']
        for line in self.order_line:
            flag = bool(line.reward_id) and (line.reward_id.id, line.coupon_id.id) in auto_keys
            if flag and not line.cl_auto_applied:
                to_mark |= line
            elif not flag and line.cl_auto_applied:
                to_unmark |= line
        if to_mark:
            to_mark.cl_auto_applied = True
        if to_unmark:
            to_unmark.cl_auto_applied = False

    def _cl_remember_dismissed_rewards(self, commands):
        """Remember automatic rewards whose lines the salesperson deleted."""
        if not isinstance(commands, (list, tuple)):
            return
        line_ids = [
            command[1] for command in commands
            if isinstance(command, (list, tuple)) and len(command) > 1
            and command[0] in (Command.DELETE, Command.UNLINK)
        ]
        if not line_ids:
            return
        lines = self.env['sale.order.line'].browse(line_ids).exists().filtered(
            lambda line: line.cl_auto_applied and line.reward_id and line.order_id in self)
        for order in lines.order_id:
            rewards = lines.filtered(lambda line: line.order_id == order).reward_id
            order.with_context(**{CL_SKIP_CTX: True}).write({
                'cl_dismissed_reward_ids': [Command.link(reward.id) for reward in rewards],
            })

    def _cl_forget_stale_dismissals(self):
        """Forget the removed rewards whose promotion stopped applying.

        A reward the salesperson removed stays away only while the quotation
        keeps earning its promotion. Once the promotion no longer applies
        (lines removed, quantity lowered, quotation emptied) the removal is
        forgotten, so the promotion is offered again if it is earned later.
        """
        self.ensure_one()
        dismissed = self.cl_dismissed_reward_ids
        if not dismissed:
            return
        earned_programs = self.env['loyalty.program']
        if self.order_line:
            earned_programs = self.coupon_point_ids.coupon_id.program_id
        stale = dismissed.filtered(lambda reward: reward.program_id not in earned_programs)
        if stale:
            self.cl_dismissed_reward_ids = [Command.unlink(reward.id) for reward in stale]

    def _cl_refresh_auto_promotions(self):
        """Recompute the automatic promotions of the quotation.

        Lines added by this module are removed and claimed again from scratch.
        Lines the salesperson applied (coupons, codes, eWallet, rewards chosen
        in the wizard) are never removed here; only the standard
        sale_loyalty update touches them, as the Reward button does.
        """
        self.ensure_one()
        had_lines = bool(self.order_line)
        before = self.order_line.filtered('cl_auto_applied').reward_id
        auto_lines = self.order_line.filtered(lambda line: line.cl_auto_applied and line.reward_id)
        if auto_lines:
            auto_lines._reset_loyalty(complete=True)
            self.write({'order_line': [Command.delete(line.id) for line in auto_lines]})

        has_choice = False
        if had_lines:
            self._update_programs_and_rewards()
        self._cl_forget_stale_dismissals()
        if had_lines and self.order_line:
            has_choice = self._cl_claim_auto_rewards()

        if has_choice != self.cl_has_reward_choice:
            self.cl_has_reward_choice = has_choice
        after = self.order_line.filtered('cl_auto_applied').reward_id
        if before != after:
            self._cl_notify_promotion_changes(added=after - before, removed=before - after)

    def _cl_claim_auto_rewards(self):
        """Claim the rewards of the automatic promotions earned by the order.

        :return: True when the salesperson has to choose between several
            promotions (nothing is picked for them in that case).
        """
        self.ensure_one()
        coupons = self.coupon_point_ids.coupon_id.filtered(
            lambda coupon: coupon.program_id._cl_is_automatic_promotion())
        if not coupons:
            return False
        dismissed = self.cl_dismissed_reward_ids
        auto_self = self.with_context(**{CL_AUTO_CLAIM_CTX: True})
        has_choice = False
        applied = False

        # 1. Free products: every promotion offering exactly one free product.
        for coupon, rewards in self._get_claimable_rewards(forced_coupons=coupons).items():
            rewards -= dismissed
            if len(rewards) != 1 or rewards.reward_type != 'product':
                continue
            if rewards.multi_product:
                has_choice = True  # the customer may pick the product
                continue
            applied |= auto_self._cl_try_apply_reward(rewards, coupon)

        # 2. Discounts: apply one only when it is the only option.
        manual_lines = self.order_line.filtered(lambda line: line.reward_id and not line.cl_auto_applied)
        discount_chosen = any(
            line.reward_id.reward_type == 'discount'
            and line.reward_id.program_id._cl_is_automatic_promotion()
            for line in manual_lines
        )
        manual_global = any(line.reward_id.is_global_discount for line in manual_lines)
        discount_options, other_options = [], []
        for coupon, rewards in self._get_claimable_rewards(forced_coupons=coupons).items():
            rewards -= dismissed
            if manual_global:
                # Never replace a global discount the salesperson applied.
                rewards = rewards.filtered(lambda reward: not reward.is_global_discount)
            for reward in rewards:
                if reward.reward_type == 'discount':
                    discount_options.append((coupon, reward))
                else:
                    other_options.append((coupon, reward))
        if other_options:
            has_choice = True
        if discount_chosen:
            # The salesperson already chose among the automatic discounts.
            discount_options = []
        if len(discount_options) == 1:
            coupon, reward = discount_options[0]
            if any(other_coupon == coupon for other_coupon, __ in other_options):
                # The same promotion also offers another reward: let them choose.
                has_choice = True
            else:
                applied |= auto_self._cl_try_apply_reward(reward, coupon)
        elif len(discount_options) > 1:
            has_choice = True

        if applied:
            # sale_loyalty expects an update after claiming, to order the discounts.
            self._update_programs_and_rewards()
        return has_choice

    def _cl_try_apply_reward(self, reward, coupon):
        self.ensure_one()
        try:
            result = self._apply_program_reward(reward, coupon)
        except UserError as error:
            _logger.info(
                "Automatic promotion %s not applied on %s: %s",
                reward.display_name, self.display_name, error)
            return False
        if result.get('error'):
            _logger.info(
                "Automatic promotion %s not applied on %s: %s",
                reward.display_name, self.display_name, result['error'])
            return False
        return True

    def _cl_notify_promotion_changes(self, added, removed):
        self.ensure_one()
        items = [_("Added: %s", reward.display_name) for reward in added]
        items += [_("Removed: %s", reward.display_name) for reward in removed]
        body = Markup("<p>%s</p><ul>%s</ul>") % (
            _("Automatic promotions updated."),
            Markup().join(Markup("<li>%s</li>") % item for item in items),
        )
        # A log note, not message_post: nobody has to be notified, and
        # message_post refuses users who have no email address.
        self._message_log(body=body)
        self.env.user._bus_send('simple_notification', {
            'type': 'info',
            'title': _("Promotions updated on %s", self.name),
            'message': "; ".join(items),
            'sticky': False,
        })
