# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models


class ClProductCompatibilityGroup(models.Model):
    """Products in the same group are checked against each other on orders."""
    _name = 'cl.product.compatibility.group'
    _description = 'Product Compatibility Group'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Colour')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help="Leave empty to use the group in every company.")
    product_ids = fields.Many2many(
        'product.product', 'cl_product_compat_group_rel', 'group_id', 'product_id',
        string='Products')
    product_count = fields.Integer(string='Products in Group', compute='_compute_product_count')
    description = fields.Text()

    @api.depends('product_ids')
    def _compute_product_count(self):
        for group in self:
            group.product_count = len(group.product_ids)
