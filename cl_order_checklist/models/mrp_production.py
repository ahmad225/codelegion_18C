# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _


class MrpProduction(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'cl.order.checklist.mixin']

    _cl_checklist_type = 'mrp'
    _cl_checklist_inverse = 'production_id'

    cl_checklist_line_ids = fields.One2many(
        'cl.order.checklist.line', 'production_id', string='Checklist', copy=False)
    cl_checklist_progress = fields.Float(
        string='Checklist Progress', compute='_compute_cl_checklist_progress')
    cl_checklist_required_left = fields.Integer(
        string='Required Items Left', compute='_compute_cl_checklist_progress')

    @api.model
    def _cl_checklist_open_domain(self):
        return [('state', 'not in', ('done', 'cancel'))]

    def _cl_checklist_block_message(self, item_names):
        return _(
            "%(order)s cannot be marked as done yet. Tick these items in its "
            "Checklist tab first:\n%(items)s",
            order=self.display_name,
            items="\n".join("- %s" % name for name in item_names))

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        productions._cl_checklist_sync()
        return productions

    def button_mark_done(self):
        # The gate is where the order is closed: starting and producing are
        # never held up, only "Mark as Done".
        self._cl_checklist_gate()
        return super().button_mark_done()
