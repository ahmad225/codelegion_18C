# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

from .res_company import length_uom_domain, weight_uom_domain


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_packaging_length_uom_id = fields.Many2one(
        related='company_id.cl_packaging_length_uom_id', readonly=False,
        domain=length_uom_domain)
    cl_packaging_length_uom_free = fields.Boolean(
        related='company_id.cl_packaging_length_uom_free', readonly=False)
    cl_packaging_weight_uom_id = fields.Many2one(
        related='company_id.cl_packaging_weight_uom_id', readonly=False,
        domain=weight_uom_domain)
    cl_packaging_weight_uom_free = fields.Boolean(
        related='company_id.cl_packaging_weight_uom_free', readonly=False)
