# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

# Contact fields that can sensibly be required before approval: stored,
# editable, and of a type where "empty" has a clear meaning.
CL_MANDATORY_FIELD_DOMAIN = [
    ('model', '=', 'res.partner'),
    ('store', '=', True),
    ('readonly', '=', False),
    ('ttype', 'in', ['char', 'text', 'html', 'selection', 'many2one', 'date', 'datetime']),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_contact_approval_enabled = fields.Boolean(
        string='Customer Approval',
        help='New customers must be approved before their sales orders can be confirmed.')
    cl_contact_mandatory_field_ids = fields.Many2many(
        'ir.model.fields', 'cl_contact_approval_company_field_rel', 'company_id', 'field_id',
        string='Mandatory Customer Fields', domain=CL_MANDATORY_FIELD_DOMAIN,
        help='Fields that must be filled in on the customer before it can be sent for approval or approved.')
