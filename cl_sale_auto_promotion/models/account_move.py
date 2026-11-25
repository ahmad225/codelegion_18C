# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    cl_promotion_savings = fields.Monetary(
        string='Promotion Savings', currency_field='currency_id',
        compute='_compute_cl_promotion_savings',
        help="Promotion discounts and free products invoiced on this "
             "document, tax excluded. eWallet and gift card payments are "
             "not savings and are not counted.")

    @api.depends(
        'move_type',
        'invoice_line_ids.sale_line_ids.reward_id',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.price_unit',
        'invoice_line_ids.quantity',
        'invoice_line_ids.tax_ids',
    )
    def _compute_cl_promotion_savings(self):
        for move in self:
            savings = 0.0
            # Only the lines of this invoice count, so a down payment or a
            # partial invoice shows the savings it actually carries.
            if move.move_type in ('out_invoice', 'out_receipt'):
                for line in move.invoice_line_ids:
                    savings += line._cl_get_promotion_saving()
            move.cl_promotion_savings = move.currency_id.round(savings) if move.currency_id else savings
