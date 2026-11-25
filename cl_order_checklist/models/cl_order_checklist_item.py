# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models

# checklist kind -> model whose orders carry that checklist
ORDER_MODELS = {
    'sale': 'sale.order',
    'mrp': 'mrp.production',
}


class OrderChecklistItem(models.Model):
    """One thing to check on every order of a kind. The orders themselves
    carry a ``cl.order.checklist.line`` per item, which is what gets ticked."""
    _name = 'cl.order.checklist.item'
    _description = 'Order Checklist Item'
    _order = 'applies_to, sequence, id'

    name = fields.Char(string='To Check', required=True, translate=True)
    applies_to = fields.Selection(
        selection=[('sale', 'Sales Orders'), ('mrp', 'Manufacturing Orders')],
        string='On', required=True, default='sale')
    blocking = fields.Boolean(
        string='Required', default=True,
        help="A sales order cannot be confirmed, and a manufacturing order "
             "cannot be marked as done, until this item is ticked. Untick to "
             "make the item a simple reminder.")
    guidance = fields.Text(
        string='How to Check', translate=True,
        help="Shown next to the item on the order.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company,
        help="Leave empty to use the item in every company.")

    # ------------------------------------------------------------------
    # Keep the open orders in step with the list of items
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        items = super().create(vals_list)
        items._cl_add_to_open_orders()
        return items

    def write(self, vals):
        res = super().write(vals)
        if {'applies_to', 'company_id', 'active'} & set(vals):
            # Lines not ticked yet may not apply any more; the ticked ones are
            # kept as a record of what was checked.
            self.env['cl.order.checklist.line'].sudo().search([
                ('item_id', 'in', self.ids), ('done', '=', False),
            ]).unlink()
            self._cl_add_to_open_orders()
        return res

    def _cl_add_to_open_orders(self):
        """Give every open order of the right kind a line for these items, so
        an item added today also shows on the quotations made yesterday."""
        Line = self.env['cl.order.checklist.line'].sudo()
        vals_list = []
        for item in self.filtered('active'):
            Order = self.env[ORDER_MODELS[item.applies_to]].sudo()
            domain = Order._cl_checklist_open_domain() + [
                ('cl_checklist_line_ids', 'not any', [('item_id', '=', item.id)]),
            ]
            if item.company_id:
                domain.append(('company_id', '=', item.company_id.id))
            inverse = Order._cl_checklist_inverse
            vals_list += [
                {'item_id': item.id, inverse: order_id}
                for order_id in Order.search(domain).ids
            ]
        if vals_list:
            Line.create(vals_list)
