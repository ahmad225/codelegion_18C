# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models


class CreditReject(models.TransientModel):
    _name = 'cl.credit.reject'
    _description = "Reject Credit Request"

    order_id = fields.Many2one(
        'sale.order', string="Quotation", required=True, readonly=True, ondelete='cascade')
    reason = fields.Text(string="Reason", required=True)

    def action_reject(self):
        self.ensure_one()
        self.order_id._cl_credit_reject(self.reason)
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
