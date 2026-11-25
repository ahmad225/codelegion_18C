# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, models
from odoo.exceptions import UserError

# Changing one of these changes what the file is, or which record it belongs to.
CL_PROOF_LOCKED_FIELDS = frozenset({
    'raw', 'datas', 'db_datas', 'store_fname', 'checksum', 'mimetype', 'type', 'url',
    'res_model', 'res_id', 'res_field',
})


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _cl_check_not_done_proof(self):
        """The proof files of a done transfer line are evidence: locking the
        link on the line is not enough, the files themselves must stay too.
        Any Inventory user may otherwise delete them (e.g. from the chatter
        note of the transfer) or replace their content.
        """
        if self.env.su or not self.ids:
            return
        move = self.env['stock.move'].sudo().search(
            [('cl_proof_attachment_ids', 'in', self.ids), ('state', '=', 'done')], limit=1)
        if move:
            raise UserError(_(
                "This file is the photo proof of a done transfer (%(transfer)s, %(product)s): "
                "it cannot be changed or deleted.",
                transfer=move.picking_id.display_name or move.reference or '',
                product=move.product_id.display_name))

    def write(self, vals):
        if CL_PROOF_LOCKED_FIELDS.intersection(vals):
            self._cl_check_not_done_proof()
        return super().write(vals)

    def unlink(self):
        self._cl_check_not_done_proof()
        return super().unlink()
