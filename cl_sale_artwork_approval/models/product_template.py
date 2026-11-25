# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models

ARTWORK_READERS = ('sales_team.group_sale_salesman,mrp.group_mrp_user,'
                   'cl_sale_artwork_approval.group_cl_artwork_designer')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cl_artwork_required = fields.Boolean(
        string='Requires Artwork',
        help='Each customer needs an approved artwork (logo, print design) for this product. '
             'Depending on the Sales settings, orders cannot be confirmed without it.')
    cl_artwork_count = fields.Integer(
        string='Approved Artworks', compute='_compute_cl_artwork_count', groups=ARTWORK_READERS)

    def _compute_cl_artwork_count(self):
        counts = dict(self.env['cl.artwork']._read_group(
            [('product_tmpl_id', 'in', self.ids), ('state', '=', 'approved')],
            ['product_tmpl_id'], ['__count']))
        for template in self:
            template.cl_artwork_count = counts.get(template, 0)

    def action_cl_view_artworks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_sale_artwork_approval.action_cl_artwork')
        action.update({
            'name': _('Approved Artworks'),
            'domain': [('product_tmpl_id', '=', self.id), ('state', '=', 'approved')],
            'context': {'default_product_tmpl_id': self.id, 'create': False},
        })
        return action
