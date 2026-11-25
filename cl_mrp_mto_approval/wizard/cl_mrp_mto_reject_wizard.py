# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ClMrpMtoRejectWizard(models.TransientModel):
    _name = 'cl.mrp.mto.reject.wizard'
    _description = 'Reject Make-to-Order Manufacturing Order'

    production_ids = fields.Many2many('mrp.production', string='Manufacturing Orders', required=True)
    reason = fields.Text(string='Reason', required=True,
                         help='Sent to the salesperson of the sales order.')
    cancel_production = fields.Boolean(
        string='Cancel the manufacturing order',
        help='Leave unticked to keep the order on hold: production can fix it and '
             'send it for approval again.')

    def action_cl_confirm_reject(self):
        self.ensure_one()
        self.production_ids._cl_reject(self.reason, cancel=self.cancel_production)
        return {'type': 'ir.actions.act_window_close'}
