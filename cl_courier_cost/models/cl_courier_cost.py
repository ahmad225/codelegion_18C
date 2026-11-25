# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import json
import logging

import psycopg2
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

USER_GROUP = 'cl_courier_cost.group_cl_courier_user'
MANAGER_GROUP = 'cl_courier_cost.group_cl_courier_manager'

# What a Courier Cost user (not manager) may change on a log.
USER_FIELDS = frozenset({'cl_actual_cost', 'cl_has_actual_cost', 'cl_notes', 'cl_is_locked'})


class ClCourierCost(models.Model):
    _name = 'cl.courier.cost'
    _description = 'Courier Cost Log'
    _inherit = ['mail.thread']
    _order = 'cl_date desc, id desc'

    name = fields.Char(related='cl_picking_id.name', string='Reference', store=True, index=True)
    cl_picking_id = fields.Many2one(
        'stock.picking', string='Delivery Order', required=True, readonly=True,
        index=True, ondelete='cascade')
    cl_sale_id = fields.Many2one('sale.order', string='Sales Order', readonly=True, index='btree_not_null')
    cl_partner_id = fields.Many2one('res.partner', string='Customer', readonly=True, index=True)
    cl_carrier_id = fields.Many2one('delivery.carrier', string='Carrier', readonly=True, index=True)
    cl_formula_id = fields.Many2one('cl.courier.formula', string='Formula', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')
    cl_date_done = fields.Datetime(string='Validated On', readonly=True)
    cl_date = fields.Date(
        string='Delivery Date', readonly=True, index=True,
        help="Date the delivery was validated, in the local time zone (used for monthly reporting).")
    cl_weight = fields.Float(string='Weight', digits='Stock Weight', readonly=True)
    state = fields.Selection(
        [('ok', 'Computed'), ('error', 'Error')], string='Status', required=True,
        default='ok', readonly=True)
    cl_error_message = fields.Text(string='Error', readonly=True)
    cl_formula_expression = fields.Text(string='Expression Used', readonly=True)
    cl_variable_values = fields.Text(string='Values Used', readonly=True, help="Variable values (JSON).")

    cl_expected_cost = fields.Monetary(string='Expected Cost', readonly=True)
    cl_customer_charge = fields.Monetary(
        string='Customer Charge', readonly=True,
        help="Untaxed delivery charge of the sales order shared over its validated deliveries by "
             "shipping weight (equal split when none has a weight), in company currency.")
    cl_actual_cost = fields.Monetary(string='Actual Cost', tracking=True)
    cl_has_actual_cost = fields.Boolean(
        string='Billed', tracking=True, index=True,
        help="Ticked once the courier's actual cost has been entered. Variance and margin are only "
             "computed for billed deliveries.")
    cl_notes = fields.Text(string='Notes')
    cl_is_locked = fields.Boolean(
        string='Locked', tracking=True, index=True,
        help="Set when the actual cost is imported or confirmed. Only managers can change a locked log.")

    cl_billed_expected_cost = fields.Monetary(
        string='Expected Cost (billed)', compute='_compute_cl_results', store=True,
        help="Expected cost of billed deliveries only, to compare with the actual cost.")
    cl_variance = fields.Monetary(
        string='Variance', compute='_compute_cl_results', store=True,
        help="Actual cost minus expected cost (positive: the courier billed more than expected).")
    cl_margin = fields.Monetary(
        string='Margin', compute='_compute_cl_results', store=True,
        help="Customer charge minus actual cost.")
    cl_expected_margin = fields.Monetary(
        string='Expected Margin', compute='_compute_cl_results', store=True,
        help="Customer charge minus expected cost.")
    cl_is_overrun = fields.Boolean(
        string='Billed Above Estimate', compute='_compute_cl_results', store=True)

    _sql_constraints = [
        ('cl_picking_uniq', 'unique(cl_picking_id)', 'A delivery order can only have one courier cost log.'),
    ]

    @api.depends('state', 'cl_expected_cost', 'cl_customer_charge', 'cl_actual_cost', 'cl_has_actual_cost')
    def _compute_cl_results(self):
        for log in self:
            computed = log.state == 'ok'
            billed = log.cl_has_actual_cost
            log.cl_expected_margin = log.cl_customer_charge - log.cl_expected_cost if computed else 0.0
            log.cl_margin = log.cl_customer_charge - log.cl_actual_cost if billed else 0.0
            log.cl_billed_expected_cost = log.cl_expected_cost if billed and computed else 0.0
            log.cl_variance = log.cl_actual_cost - log.cl_expected_cost if billed and computed else 0.0
            log.cl_is_overrun = bool(
                billed and computed
                and log.currency_id.compare_amounts(log.cl_actual_cost, log.cl_expected_cost) > 0)

    def write(self, vals):
        vals = dict(vals)
        if 'cl_has_actual_cost' in vals and not vals['cl_has_actual_cost']:
            vals['cl_actual_cost'] = 0.0
        elif 'cl_actual_cost' in vals and 'cl_has_actual_cost' not in vals:
            vals['cl_has_actual_cost'] = True
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            forbidden = set(vals) - USER_FIELDS
            if forbidden:
                raise AccessError(_(
                    "Only Courier Cost managers can change: %s.", ', '.join(sorted(forbidden))))
            if 'cl_is_locked' in vals and not vals['cl_is_locked']:
                raise AccessError(_("Only Courier Cost managers can unlock a courier cost log."))
            locked = self.filtered('cl_is_locked')
            if locked:
                raise UserError(_(
                    "These courier cost logs are locked: %s. Ask a manager to unlock them.",
                    ', '.join(locked.mapped('name'))))
        if vals.get('cl_is_locked'):
            unbilled = self if not vals.get('cl_has_actual_cost') else self.browse()
            unbilled = unbilled.filtered(lambda log: not log.cl_has_actual_cost)
            if unbilled:
                raise UserError(_(
                    "Enter the actual cost before locking: %s.", ', '.join(unbilled.mapped('name'))))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_cl_lock(self):
        self.filtered(lambda log: not log.cl_is_locked).write({'cl_is_locked': True})
        return True

    def action_cl_unlock(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_("Only Courier Cost managers can unlock a courier cost log."))
        self.write({'cl_is_locked': False})
        return True

    def action_cl_recompute(self):
        """Recompute unbilled logs with the delivery's current carrier and formula."""
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_("Only Courier Cost managers can recompute courier costs."))
        billed = self.filtered(lambda log: log.cl_has_actual_cost or log.cl_is_locked)
        if billed:
            raise UserError(_(
                "These logs already have an actual cost and are not recomputed: %s. "
                "Clear the actual cost first.", ', '.join(billed.mapped('name'))))
        for log in self:
            self.sudo()._cl_record_for_picking(log.cl_picking_id.sudo())
        return True

    def action_cl_open_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': self.cl_picking_id.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    @api.model
    def _cl_local_date(self, picking):
        stamp = picking.date_done or fields.Datetime.now()
        tz = self.env.user.tz or picking.company_id.partner_id.tz or 'UTC'
        return fields.Datetime.context_timestamp(self.with_context(tz=tz), stamp).date()

    @api.model
    def _cl_record_for_picking(self, picking):
        """Create or refresh the log of a validated outgoing delivery.

        Must be called with sudo: it runs for warehouse users who do not
        manage courier costs. A log that already has an actual cost (or is
        locked) is never changed. Evaluation problems never raise: the log is
        stored as 'error' with the reason and a note is posted on the delivery.
        """
        log = self.search([('cl_picking_id', '=', picking.id)], limit=1)
        if log and (log.cl_has_actual_cost or log.cl_is_locked):
            return log
        carrier = picking.carrier_id
        formula = carrier.cl_courier_formula_id
        vals = {
            'cl_picking_id': picking.id,
            'cl_sale_id': picking.sale_id.id,
            'cl_partner_id': picking.partner_id.id,
            'cl_carrier_id': carrier.id,
            'cl_formula_id': formula.id,
            'company_id': picking.company_id.id,
            'cl_date_done': picking.date_done,
            'cl_date': self._cl_local_date(picking),
            'cl_weight': picking.shipping_weight or picking.weight,
            'cl_formula_expression': formula.cl_expression,
        }
        error = False
        source_values = {}
        try:
            source_values = picking._cl_courier_source_values()
            if not formula:
                raise UserError(_("The delivery method %s has no courier cost formula.", carrier.display_name))
            if formula.state != 'validated':
                raise UserError(_(
                    "The formula %s is not validated, so it was not used. Validate it, then recompute.",
                    formula.name))
            cost, values = formula._cl_compute(source_values)
            vals.update({
                'state': 'ok',
                'cl_expected_cost': picking.company_id.currency_id.round(cost),
                'cl_error_message': False,
                'cl_variable_values': json.dumps(values, sort_keys=True),
            })
        except psycopg2.Error:
            raise
        except Exception as exc:  # noqa: BLE001 - an estimate must never block a delivery
            error = exc.args[0] if isinstance(exc, UserError) else '%s: %s' % (type(exc).__name__, exc)
            vals.update({
                'state': 'error',
                'cl_expected_cost': 0.0,
                'cl_error_message': error,
                'cl_variable_values': json.dumps(source_values, sort_keys=True),
            })
        if log:
            log.write(vals)
        else:
            # The user validating the delivery must not become a follower of
            # a cost log they are not allowed to read.
            log = self.with_context(mail_create_nosubscribe=True).create(vals)
        if error:
            # _message_log: a note for whoever opens the delivery, nobody is notified
            picking._message_log(
                body=Markup("<p><b>%s</b></p><p>%s</p>") % (
                    _("The courier cost could not be computed (delivery validated anyway)."), error))
        self._cl_refresh_customer_charges(picking.sale_id)
        return log

    @api.model
    def _cl_refresh_customer_charges(self, orders):
        """Share each order's delivery charge over its validated outgoing deliveries.

        Rule: the untaxed total of the order's delivery lines, converted to the
        company currency, is split in proportion to each delivery's shipping
        weight (product weight when no shipping weight is set). When none of
        the deliveries has a weight, it is split equally. Every validated
        outgoing delivery of the order takes its share, with or without a log,
        so the order's charge is counted exactly once. Shares of earlier
        deliveries are updated when a later one (e.g. a backorder) is validated;
        rounding differences go to the last delivery.
        """
        for order in orders:
            deliveries = order.picking_ids.filtered(
                lambda p: p.state == 'done' and p.picking_type_code == 'outgoing').sorted('id')
            logs = self.search([('cl_picking_id', 'in', deliveries.ids)])
            if not logs:
                continue
            company = order.company_id
            currency = company.currency_id
            total = sum(order.order_line.filtered('is_delivery').mapped('price_subtotal'))
            if order.currency_id and order.currency_id != currency:
                dates = [d for d in deliveries.mapped('date_done') if d]
                date = max(dates) if dates else fields.Datetime.now()
                total = order.currency_id._convert(total, currency, company, date.date())
            weights = [d.shipping_weight or d.weight or 0.0 for d in deliveries]
            total_weight = sum(weights)
            count = len(deliveries)
            charges = {}
            remaining = total
            for index, delivery in enumerate(deliveries):
                if index == count - 1:
                    amount = currency.round(remaining)
                else:
                    share = weights[index] / total_weight if total_weight > 0 else 1.0 / count
                    amount = currency.round(total * share)
                remaining -= amount
                charges[delivery.id] = amount
            for log in logs:
                amount = charges[log.cl_picking_id.id]
                if currency.compare_amounts(log.cl_customer_charge, amount):
                    log.cl_customer_charge = amount
