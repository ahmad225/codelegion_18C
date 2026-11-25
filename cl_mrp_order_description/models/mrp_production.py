# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.tools import html2plaintext


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    cl_mo_description = fields.Text(
        string='Description', copy=True,
        help="Instructions for this order; printed on the Production Order PDF.")
    cl_shop_floor_note = fields.Text(
        string='Shop Floor Note', compute='_compute_cl_shop_floor_note',
        help="The note from Enterprise Shop Floor, when that module is installed.")

    @api.model
    def _cl_note_as_text(self, value, field_type):
        """Plain text of a note, whatever the type of the field it comes from."""
        if not value:
            return False
        if field_type == 'html':
            value = html2plaintext(value)
        return (value or '').strip() or False

    # log_note comes from Enterprise mrp_workorder: depend on it and read it
    # only when that field exists.
    @api.depends(lambda self: ('log_note',) if 'log_note' in self._fields else ())
    def _compute_cl_shop_floor_note(self):
        note_field = self._fields.get('log_note')
        for production in self:
            production.cl_shop_floor_note = self._cl_note_as_text(
                production.log_note, note_field.type) if note_field else False
