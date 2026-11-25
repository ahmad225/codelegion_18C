# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools.float_utils import float_is_zero, float_round


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    cl_qty_to_receive = fields.Float(
        string='To Receive', digits='Product Unit of Measure',
        compute='_compute_cl_receipt_progress',
        help="Ordered quantity that has not been received yet.")
    cl_receipt_progress = fields.Selection(
        selection=[('none', 'Nothing Received'), ('part', 'Partly Received')],
        string='Receipt Progress', compute='_compute_cl_receipt_progress')

    @api.depends('product_qty', 'qty_received', 'product_uom')
    def _compute_cl_receipt_progress(self):
        default_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            # Compare in the line's own unit; lines without a unit (sections,
            # notes) fall back on the database precision.
            precision = (
                {'precision_rounding': line.product_uom.rounding}
                if line.product_uom.rounding else {'precision_digits': default_digits})
            outstanding = float_round(line.product_qty - line.qty_received, **precision)
            line.cl_qty_to_receive = outstanding if outstanding > 0 else 0.0
            line.cl_receipt_progress = (
                'none' if float_is_zero(line.qty_received, **precision) else 'part')

    @api.model
    def _cl_outstanding_by_product(self, products):
        """Confirmed purchase lines of ``products`` that still have an open
        incoming receipt, as ``{product_id: lines}`` sorted by expected arrival
        (one query for all products).

        The lines are found through their open receipt moves, so a product
        bought as a kit is listed on the kit itself while its components are
        still expected.
        """
        # Services have no receipt; goods (storable or not) do.
        products = products.filtered(lambda p: p.type == 'consu')
        if not products:
            return {}
        moves = self.env['stock.move'].search([
            ('purchase_line_id.product_id', 'in', products.ids),
            ('state', 'not in', ('done', 'cancel')),
            ('picking_id.picking_type_id.code', '=', 'incoming'),
        ])
        line_ids = defaultdict(list)
        for line in moves.purchase_line_id.sorted(lambda l: (l.date_planned or l.date_order, l.id)):
            if line.display_type or line.state not in ('purchase', 'done'):
                continue
            line_ids[line.product_id.id].append(line.id)
        return {product_id: self.browse(ids) for product_id, ids in line_ids.items()}

    @api.model
    def _cl_get_incoming_action(self, lines):
        """Window action listing ``lines`` with the Incoming Purchases list."""
        list_view = self.env.ref('cl_product_purchase_lines.cl_incoming_po_line_list')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Incoming Purchases"),
            'res_model': 'purchase.order.line',
            'view_mode': 'list',
            'views': [(list_view.id, 'list')],
            'domain': [('id', 'in', lines.ids)],
            'context': {'create': False},
        }
