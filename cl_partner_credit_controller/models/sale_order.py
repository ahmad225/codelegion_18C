# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

from .res_partner import cl_precreate_credit_controller_column


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_credit_controller_id = fields.Many2one(
        related='partner_id.commercial_partner_id.cl_credit_controller_id', store=True,
        index='btree_not_null', string='Credit Controller')

    def _auto_init(self):
        cl_precreate_credit_controller_column(self.env.cr, self._table)
        return super()._auto_init()
