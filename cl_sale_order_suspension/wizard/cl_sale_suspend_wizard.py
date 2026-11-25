# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from datetime import timedelta

from odoo import fields, models


class ClSaleSuspendWizard(models.TransientModel):
    _name = 'cl.sale.suspend.wizard'
    _description = 'Suspend Quotation'

    def _default_follow_up_date(self):
        return fields.Date.context_today(self) + timedelta(
            days=max(self.env.company.cl_suspension_followup_days, 0))

    order_ids = fields.Many2many('sale.order', string='Quotations', required=True)
    reason = fields.Text(string='Reason', required=True)
    follow_up_date = fields.Date(string='Follow up on', required=True, default=_default_follow_up_date)

    def action_suspend(self):
        self.ensure_one()
        self.order_ids._cl_suspend(self.reason, self.follow_up_date)
        return {'type': 'ir.actions.act_window_close'}
