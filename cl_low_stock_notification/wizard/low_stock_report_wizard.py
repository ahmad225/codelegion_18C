# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class LowStockReportWizard(models.TransientModel):
    _name = 'cl.low.stock.report.wizard'
    _description = 'Low Stock Report'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    # Reminder of how "low" is defined, straight from the company settings.
    source = fields.Selection(related='company_id.cl_low_stock_source', string='Threshold')
    basis = fields.Selection(related='company_id.cl_low_stock_basis', string='Compares')
    location_ids = fields.Many2many(
        related='company_id.cl_low_stock_location_ids', string='Locations')
    recipient_ids = fields.Many2many(
        related='company_id.cl_low_stock_user_ids', string='E-mail Recipients')
    # The sheet lives on the wizard only: it disappears with it.
    xlsx_file = fields.Binary(string='Excel File', readonly=True, attachment=False)
    xlsx_filename = fields.Char(string='Excel File Name', readonly=True)

    def _low_stock_rows(self):
        """Rows to report, or a clear message when there is nothing to show."""
        self.ensure_one()
        self.company_id.check_access('read')
        self.company_id._cl_low_stock_check_enabled()
        rows = self.company_id._cl_low_stock_rows()
        if not rows:
            raise UserError(_("Good news: no product is below its minimum stock."))
        return rows

    def action_print_pdf(self):
        self._low_stock_rows()
        return self.env.ref(
            'cl_low_stock_notification.action_report_cl_low_stock'
        ).report_action(self.company_id)

    def action_download_xlsx(self):
        rows = self._low_stock_rows()
        filename, content = self.company_id._cl_low_stock_xlsx(rows)
        self.write({'xlsx_file': base64.b64encode(content), 'xlsx_filename': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/xlsx_file/%s?download=true' % (
                self._name, self.id, filename),
            'target': 'self',
        }

    def action_send_now(self):
        """Send today's e-mail right away, e.g. to check the configuration."""
        self._low_stock_rows()
        if not self.company_id._cl_low_stock_recipients():
            raise UserError(_(
                "Nobody can receive the e-mail: add recipients with an e-mail address "
                "in Inventory > Configuration > Settings > Low Stock Alerts."))
        mail = self.company_id._cl_low_stock_send()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _(
                    "Low stock e-mail queued for %s.",
                    ", ".join(mail.recipient_ids.mapped('name'))),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
