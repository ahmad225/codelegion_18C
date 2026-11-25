# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _cl_auto_send_delivery_invoices(self):
        """Queue the posted, not yet sent customer invoices of the sale orders
        whose outgoing delivery has just been validated."""
        # sudo: the person validating the delivery often has no access to
        # invoices at all; the setting is a company-wide automation.
        for picking in self.sudo():
            if picking.state != 'done' or picking.picking_type_id.code != 'outgoing':
                continue
            if not picking.company_id.cl_send_invoices_when_delivered:
                continue
            invoices = picking.sale_id.invoice_ids
            if invoices:
                invoices._cl_queue_delivery_auto_send(delivery=picking)

    def _action_done(self):
        res = super()._action_done()
        self._cl_auto_send_delivery_invoices()
        return res
