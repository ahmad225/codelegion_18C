# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from markupsafe import Markup

from odoo import api, models, _
from odoo.exceptions import UserError


class OrderChecklistMixin(models.AbstractModel):
    """What sales orders and manufacturing orders share: building their
    checklist lines, measuring progress and holding the order at its gate.

    The models that use it declare the one2many ``cl_checklist_line_ids`` and
    the two computed fields, and set the three class attributes below.
    """
    _name = 'cl.order.checklist.mixin'
    _description = 'Order Checklist Mixin'

    _cl_checklist_type = None      # value of cl.order.checklist.item.applies_to
    _cl_checklist_inverse = None   # field of cl.order.checklist.line pointing here

    # ------------------------------------------------------------------
    # To be adapted by the models
    # ------------------------------------------------------------------
    @api.model
    def _cl_checklist_open_domain(self):
        """Orders that have not passed their gate yet."""
        return []

    def _cl_checklist_exempt(self):
        """Orders the checklist does not apply to."""
        self.ensure_one()
        return False

    def _cl_checklist_block_message(self, item_names):
        """Error shown when the order is held at its gate."""
        raise NotImplementedError()

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    def _cl_checklist_items(self):
        """Items that apply to this order (its kind, its company)."""
        self.ensure_one()
        return self.env['cl.order.checklist.item'].sudo().search([
            ('applies_to', '=', self._cl_checklist_type),
            ('company_id', 'in', [False, self.company_id.id]),
        ])

    def _cl_checklist_sync(self):
        """Create the checklist lines these orders do not have yet."""
        vals_list = []
        items_by_company = {}
        for order in self:
            if order._cl_checklist_exempt():
                continue
            company = order.company_id
            if company not in items_by_company:
                items_by_company[company] = order._cl_checklist_items()
            missing = items_by_company[company] - order.cl_checklist_line_ids.item_id
            vals_list += [
                {'item_id': item.id, self._cl_checklist_inverse: order.id}
                for item in missing
            ]
        if vals_list:
            # the lines belong to the app: users only tick them
            self.env['cl.order.checklist.line'].sudo().create(vals_list)

    @api.depends('cl_checklist_line_ids.done', 'cl_checklist_line_ids.blocking')
    def _compute_cl_checklist_progress(self):
        for order in self:
            lines = order.cl_checklist_line_ids
            done = lines.filtered('done')
            order.cl_checklist_progress = 100.0 * len(done) / len(lines) if lines else 0.0
            order.cl_checklist_required_left = len(
                (lines - done).filtered('blocking'))

    # ------------------------------------------------------------------
    # Gate
    # ------------------------------------------------------------------
    def _cl_checklist_missing(self):
        """Required items of this order that are not ticked. Worked out from
        the items, so an order without lines is not let through by accident."""
        self.ensure_one()
        required = self._cl_checklist_items().filtered('blocking')
        ticked = self.sudo().cl_checklist_line_ids.filtered('done').item_id
        return required - ticked

    def _cl_checklist_gate(self):
        """Hold the orders whose required items are not all ticked."""
        if self.env.context.get('cl_skip_checklist'):
            return
        for order in self:
            if order._cl_checklist_exempt():
                continue
            missing = order._cl_checklist_missing()
            if not missing:
                continue
            names = missing.mapped('name')
            if self.env.su:
                # Done by the system (online payment, customer signature,
                # subcontracting receipt, automation): nobody is there to tick
                # anything, so the order goes through and the gap is recorded.
                order._message_log(body=Markup("%s<ul>%s</ul>") % (
                    _("Checklist not enforced (automatic operation). Not ticked:"),
                    Markup("").join(Markup("<li>%s</li>") % name for name in names),
                ))
                continue
            raise UserError(order._cl_checklist_block_message(names))
