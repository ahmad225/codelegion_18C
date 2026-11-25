# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_mto_approval_required = fields.Boolean(
        string='Approve Make-to-Order Manufacturing', default=True,
        help='Manufacturing orders created from confirmed sales orders wait for a '
             'Manufacturing Coordinator\'s approval before production can start.')
