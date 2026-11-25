# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    # The same wizard reverses vendor bills and journal entries, so the field
    # is optional here; the form asks for it when a customer invoice is credited.
    cl_credit_reason_id = fields.Many2one(
        'cl.credit.note.reason', string='Credit Note Reason',
        domain="[('company_id', 'in', (False, company_id))]")
    cl_requires_return = fields.Boolean(
        related='cl_credit_reason_id.requires_return')

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if move.move_type == 'out_invoice' and self.cl_credit_reason_id:
            values['cl_credit_reason_id'] = self.cl_credit_reason_id.id
        return values
