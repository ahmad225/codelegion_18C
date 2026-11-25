# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_credit_block_overdue = fields.Boolean(
        related='company_id.cl_credit_block_overdue', readonly=False)
    cl_credit_grace_days = fields.Integer(
        related='company_id.cl_credit_grace_days', readonly=False)
    cl_credit_currency_id = fields.Many2one(
        related='company_id.currency_id', string="Credit Control Currency")
    cl_credit_min_overdue_amount = fields.Monetary(
        related='company_id.cl_credit_min_overdue_amount', readonly=False,
        currency_field='cl_credit_currency_id')
    cl_credit_block_limit = fields.Boolean(
        related='company_id.cl_credit_block_limit', readonly=False)
    cl_credit_skip_automatic = fields.Boolean(
        related='company_id.cl_credit_skip_automatic', readonly=False)

    @api.onchange('cl_credit_block_limit')
    def _onchange_cl_credit_block_limit(self):
        # The limit itself is Odoo's own feature: make sure it is on.
        if self.cl_credit_block_limit:
            self.account_use_credit_limit = True
