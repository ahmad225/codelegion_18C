# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from markupsafe import Markup

from odoo import Command, _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime, formatLang


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cl_require_photo_proof = fields.Boolean(related='picking_type_id.cl_require_photo_proof')

    def _cl_moves_needing_proof(self):
        """Lines about to be processed in transfers whose operation type requires proof."""
        return self.filtered('picking_type_id.cl_require_photo_proof').move_ids.filtered(
            lambda m: m._cl_is_processed())

    def _cl_check_photo_proof(self, moves):
        missing = moves.filtered(lambda m: not m.cl_proof_attachment_ids)
        if not missing:
            return
        details = [
            "%s: %s" % (picking.display_name, ', '.join(picking_moves.product_id.mapped('display_name')))
            for picking, picking_moves in missing.grouped('picking_id').items()
        ]
        raise UserError(_(
            "Photo proof is missing. Add at least one photo or PDF to each product you are "
            "processing before validating:\n%s", '\n'.join(details)))

    def _cl_post_photo_proof_note(self, moves):
        """One note per transfer; it links the existing proof files instead of copying them."""
        for picking, picking_moves in moves.grouped('picking_id').items():
            items = Markup().join(
                Markup("<li>%s</li>") % _(
                    "%(product)s (%(qty)s %(uom)s): %(count)s file(s)",
                    product=move.product_id.display_name,
                    qty=formatLang(self.env, move.quantity, dp='Product Unit of Measure'),
                    uom=move.product_uom.name,
                    count=move.cl_proof_count)
                for move in picking_moves
            )
            body = Markup("<p><strong>%s</strong></p><ul>%s</ul><p>%s</p>") % (
                _("Photo proof"),
                items,
                _("Validated by %(user)s on %(date)s.",
                  user=self.env.user.name, date=format_datetime(self.env, picking.date_done)),
            )
            # _message_log: an internal note that never needs the user's email address,
            # so a warehouse user without one can still validate.
            picking._message_log(
                body=body,
                attachment_ids=[Command.link(att_id) for att_id in picking_moves.cl_proof_attachment_ids.ids],
            )

    def _action_done(self):
        # Every validation path (form, backorder wizard, Barcode app, API) ends here,
        # before any stock is moved.
        moves = self._cl_moves_needing_proof()
        self._cl_check_photo_proof(moves)
        res = super()._action_done()
        done_moves = moves.exists().filtered(lambda m: m.state == 'done')
        if done_moves:
            self._cl_post_photo_proof_note(done_moves)
        return res
