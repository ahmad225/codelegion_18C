# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'cl.order.checklist.mixin']

    _cl_checklist_type = 'sale'
    _cl_checklist_inverse = 'sale_order_id'

    cl_checklist_line_ids = fields.One2many(
        'cl.order.checklist.line', 'sale_order_id', string='Checklist', copy=False)
    cl_checklist_progress = fields.Float(
        string='Checklist Progress', compute='_compute_cl_checklist_progress')
    cl_checklist_required_left = fields.Integer(
        string='Required Items Left', compute='_compute_cl_checklist_progress')

    @api.model
    def _cl_checklist_open_domain(self):
        domain = [('state', 'in', ('draft', 'sent'))]
        if 'website_id' in self._fields:
            domain.append(('website_id', '=', False))
        return domain

    def _cl_checklist_exempt(self):
        # eCommerce orders are made and paid by the customer: no back-office
        # checklist applies to them
        self.ensure_one()
        return bool('website_id' in self._fields and self.website_id)

    def _cl_checklist_block_message(self, item_names):
        return _(
            "%(order)s cannot be confirmed yet. Tick these items in its "
            "Checklist tab first:\n%(items)s",
            order=self.display_name,
            items="\n".join("- %s" % name for name in item_names))

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._cl_checklist_sync()
        return orders

    def action_confirm(self):
        self._cl_checklist_gate()
        return super().action_confirm()

    def action_draft(self):
        res = super().action_draft()
        # Items added while the order was confirmed or cancelled have no line
        # on it yet: without one, a required item could never be ticked.
        self.filtered(lambda order: order.state in ('draft', 'sent'))._cl_checklist_sync()
        return res
