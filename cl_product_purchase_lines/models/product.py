# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models

# Both groups can already read purchase order lines in standard Odoo
# (Inventory users through purchase_stock), so showing them the list grants
# no additional access.
_GROUPS = 'purchase.group_purchase_user,stock.group_stock_user'


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cl_incoming_po_line_ids = fields.Many2many(
        'purchase.order.line', string='Incoming Purchases',
        compute='_compute_cl_incoming_po_lines', groups=_GROUPS)
    cl_incoming_po_line_count = fields.Integer(
        string='Incoming', compute='_compute_cl_incoming_po_lines', groups=_GROUPS)

    @api.depends_context('company', 'allowed_company_ids')
    def _compute_cl_incoming_po_lines(self):
        POL = self.env['purchase.order.line']
        by_product = POL._cl_outstanding_by_product(self)
        for product in self:
            lines = by_product.get(product.id, POL)
            product.cl_incoming_po_line_ids = lines
            product.cl_incoming_po_line_count = len(lines)

    def action_cl_view_incoming_po_lines(self):
        self.ensure_one()
        return self.env['purchase.order.line']._cl_get_incoming_action(
            self.cl_incoming_po_line_ids)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cl_incoming_po_line_ids = fields.Many2many(
        'purchase.order.line', string='Incoming Purchases',
        compute='_compute_cl_incoming_po_lines', groups=_GROUPS)
    cl_incoming_po_line_count = fields.Integer(
        string='Incoming', compute='_compute_cl_incoming_po_lines', groups=_GROUPS)

    @api.depends_context('company', 'allowed_company_ids')
    def _compute_cl_incoming_po_lines(self):
        POL = self.env['purchase.order.line']
        by_product = POL._cl_outstanding_by_product(self.product_variant_ids)
        for template in self:
            lines = POL
            for variant in template.product_variant_ids:
                lines |= by_product.get(variant.id, POL)
            lines = lines.sorted(lambda l: (l.date_planned or l.date_order, l.id))
            template.cl_incoming_po_line_ids = lines
            template.cl_incoming_po_line_count = len(lines)

    def action_cl_view_incoming_po_lines(self):
        self.ensure_one()
        return self.env['purchase.order.line']._cl_get_incoming_action(
            self.cl_incoming_po_line_ids)
