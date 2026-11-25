# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _cl_parent_production(self, moves):
        """Manufacturing order that consumes what these moves supply, directly or
        through transfers in between (pick components, 2 and 3 step manufacturing)."""
        seen = self.env['stock.move']
        while moves:
            parent = moves.raw_material_production_id[:1]
            if parent:
                return parent
            seen |= moves
            moves = moves.move_dest_ids - seen
        return self.env['mrp.production']

    def _cl_mto_approval_vals(self, values, company):
        """Approval values for a manufacturing order created by a procurement.

        The sales order is found from the procurement itself, never from the
        Source text:
        * a component of a manufacturing order that is linked to a sales order
          (sub-assembly, also when it is picked to production first) follows the
          approval of that order;
        * otherwise the sales order line of the procurement, of its destination
          move, or the sales order of its procurement group.
        Procurements from reordering rules are never linked.
        """
        values = values or {}
        if values.get('orderpoint_id'):
            return {}
        dest_moves = values.get('move_dest_ids') or self.env['stock.move']
        dest_moves = dest_moves.sudo()

        parent = self._cl_parent_production(dest_moves)
        if parent:
            if not parent.cl_mto_sale_order_id:
                return {}
            vals = {'cl_mto_sale_order_id': parent.cl_mto_sale_order_id.id}
            if parent.cl_approval_state in ('pending', 'rejected'):
                vals.update(cl_approval_state='pending', cl_approval_parent_id=parent.id)
            elif parent.cl_approval_state == 'approved':
                vals.update(cl_approval_state='approved', cl_approval_parent_id=parent.id)
            return vals

        order = self.env['sale.order']
        sale_line = values.get('sale_line_id')
        if sale_line:
            if isinstance(sale_line, models.BaseModel):
                order = sale_line.sudo().order_id
            else:
                order = self.env['sale.order.line'].sudo().browse(sale_line).order_id
        if not order:
            order = dest_moves.sale_line_id.order_id[:1]
        if not order and values.get('group_id'):
            order = values['group_id'].sudo().sale_id
        if not order:
            return {}
        vals = {'cl_mto_sale_order_id': order.id}
        if company and company.cl_mto_approval_required:
            vals['cl_approval_state'] = 'pending'
        return vals

    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_dest_id, name, origin,
                         company_id, values, bom):
        res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_dest_id, name,
                                       origin, company_id, values, bom)
        res.update(self._cl_mto_approval_vals(values, company_id))
        return res

    def _make_mo_get_domain(self, procurement, bom):
        domain = super()._make_mo_get_domain(procurement, bom)
        vals = self._cl_mto_approval_vals(procurement.values, procurement.company_id)
        if vals.get('cl_approval_state') == 'pending':
            # Only add to a waiting order of the same sales order (and same parent):
            # never merge demand of different sales orders, never grow an approved order.
            extra = (
                ('cl_mto_sale_order_id', '=', vals['cl_mto_sale_order_id']),
                ('cl_approval_state', '=', 'pending'),
                ('cl_approval_parent_id', '=', vals.get('cl_approval_parent_id', False)),
            )
        else:
            # Other demand (reordering rules, manual, approval off) never lands in a waiting order.
            extra = (('cl_approval_state', 'not in', ('pending', 'rejected')),)
        return tuple(domain) + extra
