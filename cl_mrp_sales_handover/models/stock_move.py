# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_assign(self, force_qty=False):
        # Every reservation path ends here: picking "Check Availability", the scheduler,
        # and the next step of a chain once the previous step (pick, MO) is done.
        res = super()._action_assign(force_qty=force_qty)
        pickings = self.picking_id.filtered(
            lambda p: p.picking_type_code == 'outgoing' and not p.cl_collection_ready_sent)
        if pickings:
            pickings._cl_notify_collection_ready()
        return res
