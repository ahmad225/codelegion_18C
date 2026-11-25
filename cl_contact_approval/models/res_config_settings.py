# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

from .res_company import CL_MANDATORY_FIELD_DOMAIN


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_contact_approval_enabled = fields.Boolean(
        related='company_id.cl_contact_approval_enabled', readonly=False)
    cl_contact_mandatory_field_ids = fields.Many2many(
        related='company_id.cl_contact_mandatory_field_ids', readonly=False,
        domain=CL_MANDATORY_FIELD_DOMAIN)
