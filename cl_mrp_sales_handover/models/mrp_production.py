# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Writing any of these can change the (planned or actual) end of the order or its link.
SYNC_FIELDS = {'date_start', 'date_finished', 'state', 'procurement_group_id', 'sale_line_id'}
# Only set by the Hand Over / Undo Handover actions, never typed or imported.
HANDOVER_FIELDS = {'cl_handed_over', 'cl_handover_date', 'cl_handover_user_id'}


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    cl_sale_order_id = fields.Many2one(
        'sale.order', string='Customer Sales Order', compute='_compute_cl_sale_order_id',
        store=True, recursive=True, readonly=True, index='btree_not_null',
        help='Sales order this manufacturing order produces for: its sales line, its '
             'procurement group, the moves it supplies, or the sales order of the '
             'manufacturing order it supplies (sub-assemblies, at any level).')
    cl_event_date = fields.Date(
        related='cl_sale_order_id.cl_event_date', store=True, string='Event Date')
    cl_event_note = fields.Char(
        related='cl_sale_order_id.cl_event_note', store=True, string='Event Note')
    cl_event_at_risk = fields.Boolean(compute='_compute_cl_event_at_risk')
    cl_handed_over = fields.Boolean(
        string='Handed Over to Warehouse', copy=False, readonly=True, tracking=True)
    cl_handover_date = fields.Datetime(string='Handed Over On', copy=False, readonly=True)
    cl_handover_user_id = fields.Many2one('res.users', string='Handed Over By', copy=False, readonly=True)
    cl_handover_applicable = fields.Boolean(compute='_compute_cl_handover_applicable')

    @api.depends('sale_line_id.order_id', 'procurement_group_id.sale_id',
                 'move_dest_ids.group_id.sale_id',
                 'move_dest_ids.raw_material_production_id.cl_sale_order_id',
                 'move_dest_ids.move_dest_ids.raw_material_production_id.cl_sale_order_id')
    def _compute_cl_sale_order_id(self):
        for production in self:
            supplied = production.move_dest_ids
            # The order that consumes this one, directly or after a "pick components"
            # transfer: a sub-assembly of a sub-assembly has no sales order of its own
            # on its procurement groups, it takes the one of its parent.
            parents = (supplied | supplied.move_dest_ids).raw_material_production_id - production
            production.cl_sale_order_id = (
                production.sale_line_id.order_id
                or production.procurement_group_id.sale_id
                or supplied.group_id.sale_id
                or parents.cl_sale_order_id
            )[:1]

    @api.depends('cl_event_date', 'date_finished', 'state')
    def _compute_cl_event_at_risk(self):
        for production in self:
            production.cl_event_at_risk = bool(
                production.state not in ('done', 'cancel')
                and production.cl_event_date and production.date_finished
                and fields.Datetime.context_timestamp(production, production.date_finished).date()
                > production.cl_event_date)

    @api.depends('company_id.cl_handover_notify', 'state', 'move_dest_ids.raw_material_production_id')
    def _compute_cl_handover_applicable(self):
        for production in self:
            production.cl_handover_applicable = bool(
                production.company_id.cl_handover_notify
                and production.state != 'cancel'
                and not production.move_dest_ids.raw_material_production_id)

    def _cl_final_productions(self):
        """Orders that deliver the sold goods: not cancelled and not a sub-assembly
        consumed by another manufacturing order."""
        return self.filtered(
            lambda p: p.state != 'cancel' and not p.move_dest_ids.raw_material_production_id)

    def _cl_sync_sale_orders(self):
        if self.env.context.get('cl_handover_sync'):
            return
        orders = self.sudo().cl_sale_order_id
        if orders:
            orders._cl_sync_commitment_date()
            orders._cl_update_ready_activity()

    # ---- hooks ----

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        productions._cl_sync_sale_orders()
        return productions

    def write(self, vals):
        if HANDOVER_FIELDS.intersection(vals) and not self.env.su:
            # Otherwise anyone who may edit the order could undo a handover (managers
            # only) or mark an unfinished order as handed over, without the salesperson
            # being told.
            raise AccessError(_("Use the Hand Over to Warehouse and Undo Handover buttons of the "
                                "manufacturing order: the handover fields cannot be changed directly."))
        res = super().write(vals)
        if SYNC_FIELDS.intersection(vals):
            self._cl_sync_sale_orders()
        return res

    def _post_run_manufacture(self, procurements):
        # sale_mrp links the procurement group to the sales order here, after create.
        res = super()._post_run_manufacture(procurements)
        self._cl_sync_sale_orders()
        return res

    def _action_cancel(self):
        res = super()._action_cancel()
        self._cl_sync_sale_orders()
        return res

    # ---- handover ----

    def action_cl_hand_over(self):
        self.check_access('write')
        for production in self:
            if not production.company_id.cl_handover_notify:
                raise UserError(_("Handover to the warehouse is switched off for %s.",
                                  production.company_id.name))
            if production.state != 'done':
                raise UserError(_("%s is not finished yet. Only done manufacturing orders can "
                                  "be handed over to the warehouse.", production.name))
        todo = self.filtered(lambda p: not p.cl_handed_over)
        if not todo:
            return True
        # The user's right to change these orders was checked above.
        todo.sudo().write({
            'cl_handed_over': True,
            'cl_handover_date': fields.Datetime.now(),
            'cl_handover_user_id': self.env.uid,
        })
        for production in todo:
            production._message_log(body=_("Handed over to the warehouse by %s.", self.env.user.name))
        todo._cl_log_handover_on_orders(undo=False)
        return True

    def action_cl_undo_handover(self):
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_("Only manufacturing managers can undo a handover to the warehouse."))
        self.check_access('write')
        todo = self.filtered('cl_handed_over')
        if not todo:
            return True
        todo.sudo().write({'cl_handed_over': False, 'cl_handover_date': False, 'cl_handover_user_id': False})
        for production in todo:
            production._message_log(body=_("Handover to the warehouse undone by %s.", self.env.user.name))
        todo._cl_log_handover_on_orders(undo=True)
        return True

    def _cl_log_handover_on_orders(self, undo):
        # The user may change this MO (checked above); the sales order side is a system update.
        for order in self.sudo().cl_sale_order_id:
            finals = order.cl_production_ids._cl_final_productions()
            names = ', '.join(self.filtered(lambda p: p.cl_sale_order_id == order).mapped('name'))
            if undo:
                body = _("Handover to the warehouse undone for %(mos)s (%(done)s of %(total)s handed over).",
                         mos=names, done=len(finals.filtered('cl_handed_over')), total=len(finals))
            else:
                body = _("%(mos)s handed over to the warehouse (%(done)s of %(total)s).",
                         mos=names, done=len(finals.filtered('cl_handed_over')), total=len(finals))
            order._message_log(body=body)
            order._cl_update_ready_activity()
