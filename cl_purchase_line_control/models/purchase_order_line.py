# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang

DELETE_GROUP = 'cl_purchase_line_control.group_cl_po_line_delete'


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # ------------------------------------------------------------------
    # What may be deleted
    # ------------------------------------------------------------------

    def _cl_confirmed_product_lines(self):
        """The lines standard Odoo refuses to delete: product lines of a
        confirmed (or locked) order. Sections and notes are never concerned."""
        return self.filtered(
            lambda line: line.order_id.state in ('purchase', 'done') and not line.display_type)

    def _cl_goods_received(self):
        """Goods came in for this line, even if they were returned since."""
        self.ensure_one()
        if any(move.state == 'done' for move in self.move_ids):
            return True
        precision = (
            {'precision_rounding': self.product_uom.rounding}
            if self.product_uom.rounding else {'precision_digits': 2})
        return not float_is_zero(self.qty_received, **precision)

    def _cl_delete_blocker(self):
        """Reason why this confirmed line must stay, or ``False`` when it may
        be deleted by an authorised user."""
        self.ensure_one()
        if self.order_id.state == 'done':
            return _("the order is locked; unlock it first")
        if self._cl_goods_received():
            return _("goods have already been received for it")
        if self.invoice_lines or self.qty_invoiced:
            return _("it is already on a vendor bill")
        return False

    @api.ondelete(at_uninstall=False)
    def _unlink_except_purchase_or_done(self):
        """Standard rule for everybody; members of the deletion group may
        delete a confirmed line as long as nothing happened on it yet."""
        if not self.env.user.has_group(DELETE_GROUP):
            return super()._unlink_except_purchase_or_done()
        problems = []
        for line in self._cl_confirmed_product_lines():
            reason = line._cl_delete_blocker()
            if reason:
                problems.append(_(
                    "- %(order)s, %(line)s: %(reason)s",
                    order=line.order_id.name,
                    line=line.product_id.display_name or line.name,
                    reason=reason))
        if problems:
            raise UserError(_(
                "Some lines cannot be deleted from their confirmed purchase order:\n%s",
                "\n".join(problems)))

    # ------------------------------------------------------------------
    # Deleting
    # ------------------------------------------------------------------

    def unlink(self):
        confirmed = self._cl_confirmed_product_lines()
        if not confirmed:
            return super().unlink()
        # Refuse before anything is touched, with the complete list of problems.
        confirmed._unlink_except_purchase_or_done()
        notes = confirmed._cl_prepare_deletion_notes()
        # purchase_stock cancels the receipt moves of the deleted lines.
        result = super().unlink()
        for record, body in notes:
            record._message_log(body=body)
        return result

    def _cl_prepare_deletion_notes(self):
        """Build one log note per purchase order and per open receipt, listing
        the lines about to be deleted. Must be called before the deletion.

        :return: list of ``(record, html body)``
        """
        per_order = defaultdict(list)
        per_picking = defaultdict(list)
        for line in self:
            label = "%s - %s %s" % (
                line.product_id.display_name or line.name,
                formatLang(self.env, line.product_qty, dp='Product Unit of Measure'),
                line.product_uom.name or '',
            )
            per_order[line.order_id].append(label)
            open_pickings = line.move_ids.filtered(
                lambda move: move.state not in ('done', 'cancel')).picking_id
            for picking in open_pickings:
                per_picking[picking].append((line.order_id.name, label))

        def bullet_list(labels):
            return Markup("<ul>%s</ul>") % Markup().join(
                Markup("<li>%s</li>") % label for label in labels)

        notes = []
        for order, labels in per_order.items():
            notes.append((order, Markup("<p>%s</p>%s") % (
                _("Deleted from this confirmed order:"), bullet_list(labels))))
        for picking, entries in per_picking.items():
            orders = ", ".join(sorted({order_name for order_name, _label in entries}))
            notes.append((picking, Markup("<p>%s</p>%s") % (
                _("No longer expected, the purchase line was deleted from %s:", orders),
                bullet_list(label for _order_name, label in entries))))
        return notes

    # ------------------------------------------------------------------
    # Product of a received line
    # ------------------------------------------------------------------

    def write(self, vals):
        if 'product_id' in vals:
            received = self.filtered(
                lambda line: line.product_id
                and line.product_id.id != vals['product_id']
                and line._cl_goods_received())
            if received:
                raise UserError(_(
                    "The product cannot be changed on a line that already has goods "
                    "received: %s. Add a new line for the other product instead.",
                    ", ".join(received.mapped('product_id.display_name'))))
        return super().write(vals)
