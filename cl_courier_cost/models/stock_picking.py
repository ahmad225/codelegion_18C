# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

import psycopg2
from markupsafe import Markup

from odoo import _, fields, models

from .cl_courier_cost import USER_GROUP

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cl_courier_cost_ids = fields.One2many(
        'cl.courier.cost', 'cl_picking_id', string='Courier Cost Logs', groups=USER_GROUP)
    cl_courier_cost_count = fields.Integer(
        string='Courier Cost Logs', compute='_compute_cl_courier_cost_count', groups=USER_GROUP)

    def _compute_cl_courier_cost_count(self):
        counts = dict(self.env['cl.courier.cost']._read_group(
            [('cl_picking_id', 'in', self.ids)], ['cl_picking_id'], ['__count']))
        for picking in self:
            picking.cl_courier_cost_count = counts.get(picking, 0)

    def action_cl_open_courier_costs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Courier Cost'),
            'res_model': 'cl.courier.cost',
            'view_mode': 'list,form',
            'domain': [('cl_picking_id', '=', self.id)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def _action_done(self):
        res = super()._action_done()
        self._cl_courier_pickings()._cl_record_courier_cost()
        return res

    def write(self, vals):
        if 'carrier_id' not in vals:
            return super().write(vals)
        old_carriers = {picking.id: picking.carrier_id for picking in self}
        res = super().write(vals)
        changed = self.filtered(
            lambda p: p.state == 'done' and p.picking_type_code == 'outgoing'
            and old_carriers[p.id] != p.carrier_id)
        for picking in changed:
            picking._cl_guarded(picking._cl_on_carrier_changed, old_carriers[picking.id])
        return res

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cl_courier_pickings(self):
        return self.filtered(
            lambda p: p.state == 'done' and p.picking_type_code == 'outgoing'
            and p.carrier_id.sudo().cl_courier_formula_id)

    def _cl_record_courier_cost(self):
        cost_model = self.env['cl.courier.cost'].sudo()
        for picking in self:
            picking._cl_guarded(cost_model._cl_record_for_picking, picking.sudo())

    def _cl_guarded(self, method, *args):
        """Run ``method`` so that no failure can undo the delivery validation."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                method(*args)
        except psycopg2.OperationalError:
            raise  # concurrency errors: let Odoo retry the whole request
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Courier cost could not be recorded for %s", self.name)
            # sudo + _message_log: this note must never fail itself (message_post
            # refuses users without an email address, common in a warehouse).
            self.sudo()._message_log(
                body=Markup("<p><b>%s</b></p><p>%s</p>") % (
                    _("The courier cost could not be recorded."), str(exc)))

    def _cl_on_carrier_changed(self, old_carrier):
        """The carrier of a done delivery changed: keep billed logs, refresh estimates."""
        self.ensure_one()
        cost_model = self.env['cl.courier.cost'].sudo()
        log = cost_model.search([('cl_picking_id', '=', self.id)], limit=1)
        new_carrier = self.carrier_id
        formula = new_carrier.sudo().cl_courier_formula_id
        old_name = old_carrier.display_name or _('none')
        new_name = new_carrier.display_name or _('none')
        if log and (log.cl_has_actual_cost or log.cl_is_locked):
            note = _(
                "Carrier changed from %(old)s to %(new)s. The courier cost log was kept unchanged "
                "because an actual cost has been entered.", old=old_name, new=new_name)
            log._message_log(body=note)
        elif formula:
            cost_model._cl_record_for_picking(self.sudo())
            note = _(
                "Carrier changed from %(old)s to %(new)s. The expected courier cost was recomputed.",
                old=old_name, new=new_name)
        elif log:
            log.unlink()
            cost_model._cl_refresh_customer_charges(self.sale_id)
            note = _(
                "Carrier changed from %(old)s to %(new)s, which has no courier cost formula. "
                "The unbilled courier cost estimate was removed.", old=old_name, new=new_name)
        else:
            return
        self.sudo()._message_log(body=note)

    def _cl_courier_source_values(self):
        """Numeric delivery values available to 'Delivery value' variables."""
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state == 'done')
        quantity = sum(
            move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id)
            for move in moves)
        order = self.sale_id
        return {
            'shipping_weight': self.shipping_weight or self.weight,
            'weight': self.weight,
            'volume': self.shipping_volume,
            # a delivery that was not put in packages travels as one parcel
            'packages': float(len(self.move_line_ids.result_package_id) or 1),
            'lines': float(len(moves)),
            'quantity': quantity,
            'untaxed': order._cl_goods_untaxed_company() if order else 0.0,
        }
