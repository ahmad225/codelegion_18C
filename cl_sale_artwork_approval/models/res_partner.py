# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models

from .product_template import ARTWORK_READERS


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Artwork belongs to the company (commercial partner): contacts show their company's artwork.
    cl_artwork_count = fields.Integer(
        string='Approved Artworks', compute='_compute_cl_artwork_count', groups=ARTWORK_READERS)

    def _compute_cl_artwork_count(self):
        counts = dict(self.env['cl.artwork']._read_group(
            [('partner_id', 'in', self.commercial_partner_id.ids), ('state', '=', 'approved')],
            ['partner_id'], ['__count']))
        for partner in self:
            partner.cl_artwork_count = counts.get(partner.commercial_partner_id, 0)

    def action_cl_view_artworks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_sale_artwork_approval.action_cl_artwork')
        action.update({
            'name': _('Approved Artworks'),
            'domain': [('partner_id', '=', self.commercial_partner_id.id), ('state', '=', 'approved')],
            'context': {'default_partner_id': self.commercial_partner_id.id, 'create': False},
        })
        return action
