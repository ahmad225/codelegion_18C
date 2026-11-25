# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.fields import Command


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cl_compatibility_group_ids = fields.Many2many(
        'cl.product.compatibility.group', 'cl_product_compat_group_rel',
        'product_id', 'group_id', string='Compatibility Groups')

    # A compatibility link is one row "low fits high" in a single table, read
    # from both of its ends. Compatibility is therefore mutual by construction:
    # there is no second row to keep in step.
    cl_compatible_out_ids = fields.Many2many(
        'product.product', 'cl_product_compatible_rel', 'product_id', 'compatible_id',
        string='Compatibility Links (from this product)', copy=False)
    cl_compatible_in_ids = fields.Many2many(
        'product.product', 'cl_product_compatible_rel', 'compatible_id', 'product_id',
        string='Compatibility Links (to this product)', copy=False)
    cl_compatible_product_ids = fields.Many2many(
        'product.product', string='Compatible Products',
        compute='_compute_cl_compatible_product_ids',
        inverse='_inverse_cl_compatible_product_ids',
        search='_search_cl_compatible_product_ids',
        help="Products this one can be sold with. A link always works in both "
             "directions: the other product lists this one too.")

    @api.depends('cl_compatible_out_ids', 'cl_compatible_in_ids')
    def _compute_cl_compatible_product_ids(self):
        for product in self:
            linked = product.cl_compatible_out_ids | product.cl_compatible_in_ids
            product.cl_compatible_product_ids = linked - product

    def _inverse_cl_compatible_product_ids(self):
        for product in self:
            wanted = product.cl_compatible_product_ids - product
            outgoing = product.cl_compatible_out_ids
            incoming = product.cl_compatible_in_ids
            dropped = (outgoing | incoming) - wanted
            added = wanted - outgoing - incoming
            commands_out = [Command.unlink(other.id) for other in dropped & outgoing]
            commands_out += [Command.link(other.id) for other in added]
            commands_in = [Command.unlink(other.id) for other in dropped & incoming]
            vals = {}
            if commands_out:
                vals['cl_compatible_out_ids'] = commands_out
            if commands_in:
                vals['cl_compatible_in_ids'] = commands_in
            if vals:
                product.write(vals)

    def _search_cl_compatible_product_ids(self, operator, value):
        return [
            '|',
            ('cl_compatible_out_ids', operator, value),
            ('cl_compatible_in_ids', operator, value),
        ]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Shown on the template form for single-variant products, like Odoo does
    # for the barcode and internal reference.
    cl_compatibility_group_ids = fields.Many2many(
        'cl.product.compatibility.group', string='Compatibility Groups',
        compute='_compute_cl_compatibility', inverse='_inverse_cl_compatibility_groups')
    cl_compatible_product_ids = fields.Many2many(
        'product.product', string='Compatible Products',
        compute='_compute_cl_compatibility', inverse='_inverse_cl_compatible_products')

    def _get_related_fields_variant_template(self):
        # Values typed on a new product form are written again once the first
        # variant exists; without this they would be lost on creation.
        return super()._get_related_fields_variant_template() + [
            'cl_compatibility_group_ids', 'cl_compatible_product_ids']

    @api.depends('product_variant_ids.cl_compatibility_group_ids',
                 'product_variant_ids.cl_compatible_product_ids')
    def _compute_cl_compatibility(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                variant = template.product_variant_ids
                template.cl_compatibility_group_ids = variant.cl_compatibility_group_ids
                template.cl_compatible_product_ids = variant.cl_compatible_product_ids
            else:
                template.cl_compatibility_group_ids = False
                template.cl_compatible_product_ids = False

    def _inverse_cl_compatibility_groups(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.cl_compatibility_group_ids = template.cl_compatibility_group_ids

    def _inverse_cl_compatible_products(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.cl_compatible_product_ids = template.cl_compatible_product_ids
