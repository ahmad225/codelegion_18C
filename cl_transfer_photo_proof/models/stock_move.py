# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


def cl_is_proof_mimetype(mimetype):
    """Photos (any image type except SVG, which is a script-capable document) and PDFs."""
    mimetype = (mimetype or '').lower()
    if mimetype == 'application/pdf':
        return True
    return mimetype.startswith('image/') and 'svg' not in mimetype


class StockMove(models.Model):
    _inherit = 'stock.move'

    cl_proof_attachment_ids = fields.Many2many(
        'ir.attachment', 'cl_stock_move_proof_attachment_rel', 'move_id', 'attachment_id',
        string='Photo Proof', copy=False,
        help="Photos or PDF files proving this product line was processed.")
    cl_proof_count = fields.Integer(string='Proofs', compute='_compute_cl_proof_count')
    cl_require_photo_proof = fields.Boolean(
        related='picking_id.picking_type_id.cl_require_photo_proof')

    @api.depends('cl_proof_attachment_ids')
    def _compute_cl_proof_count(self):
        for move in self:
            move.cl_proof_count = len(move.cl_proof_attachment_ids)

    def _cl_is_own_proof(self, attachment):
        """A proof file is a file uploaded for this line: stored on the line, or
        just uploaded by the current user and not stored on any record yet
        (it is then moved to the line, see _cl_attach_pending_proofs)."""
        self.ensure_one()
        if attachment.res_model == self._name and attachment.res_id == self.id:
            return True
        return bool(not attachment.res_id and attachment.res_model in (False, self._name)
                    and attachment.create_uid == self.env.user)

    @api.constrains('cl_proof_attachment_ids')
    def _check_cl_proof_file_types(self):
        for move in self:
            # sudo: this only reads technical values to decide; a file the
            # user may not see is refused below like any other foreign file.
            proofs = move.cl_proof_attachment_ids.sudo()
            # Linking by id (API, import) a file that belongs to another
            # document would make it "proof" without any upload, show it in
            # the transfer's chatter and lock it once the transfer is done.
            foreign = proofs.filtered(lambda a: not move._cl_is_own_proof(a))
            if foreign:
                raise ValidationError(_(
                    "A file that belongs to another document cannot be used as proof "
                    "(%(product)s). Upload the photo or PDF on the line itself.",
                    product=move.product_id.display_name))
            wrong = proofs.filtered(lambda a: not cl_is_proof_mimetype(a.mimetype))
            if wrong:
                raise ValidationError(_(
                    "Only photos and PDF files can be used as proof (%(product)s): %(files)s",
                    product=move.product_id.display_name, files=', '.join(wrong.mapped('name'))))
            empty = proofs.filtered(lambda a: a.type != 'binary' or not a.file_size)
            if empty:
                raise ValidationError(_(
                    "A proof must be a real file, not a link or an empty file (%(product)s): %(files)s",
                    product=move.product_id.display_name, files=', '.join(empty.mapped('name'))))

    def _cl_is_processed(self):
        """True when validating the transfer now would actually process this line:
        the same lines stock.move._action_done treats as done (picked, with a quantity,
        not cancelled). Lines left at zero go to the backorder or are cancelled."""
        self.ensure_one()
        return bool(
            self.state not in ('done', 'cancel')
            and self.picked
            and not self.scrapped
            and float_compare(self.quantity, 0.0, precision_rounding=self.product_uom.rounding) > 0
        )

    def _cl_attach_pending_proofs(self):
        """Files uploaded before the line was saved have no record yet (res_id 0) and would
        only be readable by their uploader. Link them to the line so every user who can
        read the line can open them."""
        for move in self:
            pending = move.cl_proof_attachment_ids.filtered(
                lambda a: not a.res_id and a.res_model in (False, self._name)
                and a.create_uid == self.env.user)
            if pending:
                pending.write({'res_model': self._name, 'res_id': move.id})

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        with_proof = [move.id for move, vals in zip(moves, vals_list) if vals.get('cl_proof_attachment_ids')]
        if with_proof:
            self.browse(with_proof)._cl_attach_pending_proofs()
        return moves

    def write(self, vals):
        if 'cl_proof_attachment_ids' in vals and not self.env.su:
            locked = self.filtered(lambda m: m.state in ('done', 'cancel'))
            if locked:
                raise UserError(_(
                    "The photo proof of a done or cancelled transfer line cannot be changed: %s",
                    ', '.join(locked.product_id.mapped('display_name'))))
        res = super().write(vals)
        if 'cl_proof_attachment_ids' in vals:
            self._cl_attach_pending_proofs()
        return res

    def unlink(self):
        # sudo: the files belong to the lines being deleted; do not leave them orphaned,
        # an attachment whose record is gone is no longer protected by that record's rights.
        proofs = self.sudo().cl_proof_attachment_ids.filtered(
            lambda a: a.res_model == self._name and a.res_id in self.ids)
        res = super().unlink()
        proofs.unlink()
        return res

    def action_cl_open_photo_proof(self):
        self.ensure_one()
        view = self.env.ref('cl_transfer_photo_proof.view_move_form_cl_photo_proof')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Photo Proof: %s', self.product_id.display_name),
            'res_model': 'stock.move',
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'res_id': self.id,
            'target': 'new',
        }
