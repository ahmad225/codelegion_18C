# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class OrderChecklistLine(models.Model):
    """A checklist item on one order: ticked or not, by whom and when."""
    _name = 'cl.order.checklist.line'
    _description = 'Order Checklist Line'
    _order = 'sequence, id'

    item_id = fields.Many2one(
        'cl.order.checklist.item', string='Item', required=True,
        ondelete='cascade', index=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', ondelete='cascade', index=True)
    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order', ondelete='cascade', index=True)

    name = fields.Char(related='item_id.name')
    guidance = fields.Text(related='item_id.guidance')
    blocking = fields.Boolean(related='item_id.blocking')
    sequence = fields.Integer(related='item_id.sequence', store=True)

    done = fields.Boolean(string='Done')
    done_by_id = fields.Many2one('res.users', string='Ticked By', readonly=True)
    done_on = fields.Datetime(string='Ticked On', readonly=True)

    _sql_constraints = [
        ('cl_sale_order_item_uniq', 'unique(item_id, sale_order_id)',
         "This checklist item is already on the sales order."),
        ('cl_production_item_uniq', 'unique(item_id, production_id)',
         "This checklist item is already on the manufacturing order."),
    ]

    def _cl_order(self):
        """The sales or manufacturing order this line belongs to."""
        self.ensure_one()
        return self.sale_order_id or self.production_id

    def write(self, vals):
        if self.env.su:
            return super().write(vals)
        # Users only tick and untick; everything else is managed by the app.
        if set(vals) - {'done'}:
            raise AccessError(_("Checklist lines can only be ticked or unticked."))
        done = bool(vals.get('done'))
        changed = self.filtered(lambda line: line.done != done)
        if not changed:
            return True
        for line in changed:
            # ticking is editing the order: it needs the same access
            order = line._cl_order()
            order.check_access('write')
        res = super(OrderChecklistLine, changed).write({
            'done': done,
            'done_by_id': self.env.uid if done else False,
            'done_on': fields.Datetime.now() if done else False,
        })
        changed._cl_log_on_order(done)
        return res

    def _cl_log_on_order(self, done):
        """One chatter note per order for what was just ticked / unticked."""
        lines_by_order = defaultdict(lambda: self.browse())
        for line in self:
            lines_by_order[line._cl_order()] |= line
        title = _("Checklist ticked:") if done else _("Checklist unticked:")
        for order, lines in lines_by_order.items():
            if not order:
                continue
            order._message_log(body=Markup("%s<ul>%s</ul>") % (
                title,
                Markup("").join(Markup("<li>%s</li>") % line.name for line in lines),
            ))

    @api.depends('item_id.name')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.item_id.name
