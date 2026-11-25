# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

from .res_partner import cl_precreate_credit_controller_column


class AccountMove(models.Model):
    _inherit = 'account.move'

    cl_credit_controller_id = fields.Many2one(
        related='commercial_partner_id.cl_credit_controller_id', store=True, index='btree_not_null',
        string='Credit Controller')

    def _auto_init(self):
        # Journal entries can be counted in millions: do not compute an empty
        # value for each of them when the module is installed.
        cl_precreate_credit_controller_column(self.env.cr, self._table)
        return super()._auto_init()
