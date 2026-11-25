# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_mrp_production_count = fields.Integer(
        string='Manufacturing Orders (MTO)', compute='_compute_cl_mrp_production_count')

    def _compute_cl_mrp_production_count(self):
        # Counted with the user's own rights.
        data = self.env['mrp.production']._read_group(
            [('cl_mto_sale_order_id', 'in', self.ids)], ['cl_mto_sale_order_id'], ['__count'])
        counts = {order.id: count for order, count in data}
        for order in self:
            order.cl_mrp_production_count = counts.get(order.id, 0)

    def action_cl_view_mto_productions(self):
        """Read-only view of the manufacturing orders of this sales order."""
        self.ensure_one()
        productions = self.env['mrp.production'].search([('cl_mto_sale_order_id', '=', self.id)])
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'context': {'create': False, 'edit': False, 'delete': False},
        }
        if len(productions) == 1:
            action.update({'view_mode': 'form', 'res_id': productions.id})
        else:
            action.update({
                'name': _("Manufacturing of %s", self.name),
                'view_mode': 'list,form',
                'domain': [('id', 'in', productions.ids)],
            })
        return action
