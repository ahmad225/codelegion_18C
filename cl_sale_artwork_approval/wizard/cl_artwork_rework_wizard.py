# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ClArtworkReworkWizard(models.TransientModel):
    _name = 'cl.artwork.rework.wizard'
    _description = 'Request Artwork Rework'

    cl_artwork_id = fields.Many2one('cl.artwork', string='Artwork', required=True, ondelete='cascade')
    cl_comment = fields.Text(string='What should change?', required=True)

    def action_cl_confirm(self):
        self.ensure_one()
        self.cl_artwork_id._cl_request_rework(self.cl_comment)
        return {'type': 'ir.actions.act_window_close'}
