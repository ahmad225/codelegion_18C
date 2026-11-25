# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, models
from odoo.exceptions import AccessError


class LowStockReport(models.AbstractModel):
    _name = 'report.cl_low_stock_notification.report_low_stock'
    _description = 'Low Stock Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """One section per company, computed when the report is printed.
        Nothing is stored or rewritten by printing."""
        companies = self.env['res.company'].browse(docids)
        # The figures are read with elevated rights, so the door is checked here:
        # Inventory Administrators only, and only for their own companies.
        if not self.env.su:
            if not self.env.user.has_group('stock.group_stock_manager'):
                raise AccessError(_("Only Inventory Administrators can print the low stock report."))
            companies.check_access('read')
        sections = {}
        for company in companies:
            rows = company._cl_low_stock_rows()
            sections[company.id] = {
                'rows': rows,
                'summary': company._cl_low_stock_summary(rows),
            }
        return {
            'doc_ids': companies.ids,
            'doc_model': 'res.company',
            'docs': companies,
            'sections': sections,
        }
