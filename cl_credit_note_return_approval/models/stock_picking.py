# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Set by the approval of a return request, never by hand: it is what makes
    # a credit note postable. Not copied, so duplicating a return transfer or
    # returning it again does not create a second "authorised" return.
    cl_return_request_id = fields.Many2one(
        'cl.return.request', string='Return Request',
        readonly=True, copy=False, index='btree_not_null')

    def write(self, vals):
        if 'cl_return_request_id' in vals and not self.env.su:
            raise AccessError(_(
                "The return request of a transfer is set by the approval of "
                "the request and cannot be changed."))
        return super().write(vals)

    def _create_backorder(self, backorder_moves=None):
        # What is left of an authorised return is still part of it: the credit
        # note waits for the backorder too (or for its cancellation).
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        for backorder in backorders.sudo():
            backorder.cl_return_request_id = backorder.backorder_id.cl_return_request_id
        return backorders

    def button_validate(self):
        self.filtered('cl_return_request_id').move_ids._cl_check_not_over_returned()
        return super().button_validate()


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _cl_done_qty(self):
        """Quantity of the move in the product's unit of measure: what was
        moved for a done move, what is planned otherwise."""
        self.ensure_one()
        if self.state == 'done':
            return self.product_uom._compute_quantity(
                self.quantity, self.product_id.uom_id, round=False)
        return self.product_qty

    def _cl_returnable_qty(self):
        """Of a done delivery: what has neither come back nor is on a return
        transfer yet, in the product's unit of measure."""
        self.ensure_one()
        coming_back = sum(
            move._cl_done_qty()
            for move in self.returned_move_ids if move.state != 'cancel')
        return max(self._cl_done_qty() - coming_back, 0.0)

    def _cl_check_not_over_returned(self):
        """Receiving an authorised return: the customer cannot send back more
        than was delivered, whatever was typed on the transfer."""
        for move in self:
            delivery = move.origin_returned_move_id
            if not delivery or move.state in ('done', 'cancel'):
                continue
            uom = move.product_id.uom_id
            receiving = move.product_uom._compute_quantity(
                move.quantity, uom, round=False)
            received_before = sum(
                other._cl_done_qty()
                for other in delivery.returned_move_ids
                if other.state == 'done' and other != move)
            delivered = delivery._cl_done_qty()
            if float_compare(receiving + received_before, delivered,
                             precision_rounding=uom.rounding) > 0:
                raise UserError(_(
                    "%(product)s: %(qty)s %(uom)s would be returned in total, "
                    "but only %(delivered)s %(uom)s were delivered.",
                    product=move.product_id.display_name,
                    qty=receiving + received_before, delivered=delivered,
                    uom=uom.name))
