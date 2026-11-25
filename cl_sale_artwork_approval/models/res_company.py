# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_artwork_block_sale = fields.Boolean(
        string='Block Orders Without Approved Artwork', default=True,
        help='Staff cannot confirm a quotation while a line whose product requires artwork '
             'has no approved artwork.')
    cl_artwork_block_production = fields.Boolean(
        string='Block Production Without Approved Artwork', default=False,
        help='Manufacturing orders made for a sales order cannot be started or produced while '
             'the artwork of a product that requires it is not approved.')
    cl_artwork_attach_production = fields.Boolean(
        string='Attach Approved Artwork to Manufacturing Orders', default=True,
        help='Attach a copy of the approved proof to manufacturing orders made for the order. '
             'The copy can be opened by everyone who can open the manufacturing order.')
