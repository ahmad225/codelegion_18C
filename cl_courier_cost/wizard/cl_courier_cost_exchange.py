# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import io
import math
import os

import xlsxwriter

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Column headers of the vendor sheet. Import finds columns by these names,
# so the courier may reorder or add columns; only "Actual Cost" and one of
# "Log ID" / "Reference" are required.
COL_LOG_ID = 'Log ID'
COL_REFERENCE = 'Reference'
COL_DATE = 'Delivery Date'
COL_CUSTOMER = 'Customer'
COL_CARRIER = 'Carrier'
COL_WEIGHT = 'Weight'
COL_EXPECTED = 'Expected Cost'
COL_ACTUAL = 'Actual Cost'
COL_NOTES = 'Notes'
HEADERS = [COL_LOG_ID, COL_REFERENCE, COL_DATE, COL_CUSTOMER, COL_CARRIER,
           COL_WEIGHT, COL_EXPECTED, COL_ACTUAL, COL_NOTES]

MIMETYPES = {
    '.csv': 'text/csv',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
}
MAX_PROBLEMS_SHOWN = 30


class ClCourierCostExchange(models.TransientModel):
    _name = 'cl.courier.cost.exchange'
    _description = 'Courier Vendor Sheet Export / Import'

    cl_mode = fields.Selection(
        [('export', 'Export'), ('import', 'Import')], string='Mode', required=True, default='export')
    # export
    cl_date_from = fields.Date(string='From')
    cl_date_to = fields.Date(string='To')
    cl_carrier_ids = fields.Many2many('delivery.carrier', string='Carriers',
                                      help="Leave empty for all carriers.")
    cl_only_unbilled = fields.Boolean(string='Only Deliveries Without Actual Cost', default=True)
    cl_export_file = fields.Binary(string='Vendor Sheet', attachment=False, readonly=True)
    cl_export_filename = fields.Char()
    # import
    cl_import_file = fields.Binary(string='Filled Sheet', attachment=False)
    cl_import_filename = fields.Char()
    cl_import_done = fields.Boolean(readonly=True)
    cl_count_updated = fields.Integer(string='Updated and Locked', readonly=True)
    cl_count_blank = fields.Integer(string='Skipped: Actual Cost Blank', readonly=True)
    cl_count_locked = fields.Integer(string='Skipped: Already Locked', readonly=True)
    cl_count_not_found = fields.Integer(string='Not Found', readonly=True)
    cl_count_invalid = fields.Integer(string='Invalid Amount', readonly=True)
    cl_import_problems = fields.Text(string='Details', readonly=True)

    @api.constrains('cl_date_from', 'cl_date_to')
    def _check_cl_dates(self):
        for wizard in self:
            if wizard.cl_date_from and wizard.cl_date_to and wizard.cl_date_from > wizard.cl_date_to:
                raise ValidationError(_("The start date must be before the end date."))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _cl_export_domain(self):
        self.ensure_one()
        domain = []
        if self.cl_date_from:
            domain.append(('cl_date', '>=', self.cl_date_from))
        if self.cl_date_to:
            domain.append(('cl_date', '<=', self.cl_date_to))
        if self.cl_carrier_ids:
            domain.append(('cl_carrier_id', 'in', self.cl_carrier_ids.ids))
        if self.cl_only_unbilled:
            domain.append(('cl_has_actual_cost', '=', False))
        return domain

    def action_cl_export(self):
        self.ensure_one()
        logs = self.env['cl.courier.cost'].search(self._cl_export_domain(), order='cl_date, id')
        if not logs:
            raise UserError(_("No courier cost logs match these filters."))
        filename = 'courier_vendor_sheet_%s.xlsx' % fields.Date.to_string(fields.Date.context_today(self))
        self.write({
            'cl_export_file': base64.b64encode(self._cl_build_xlsx(logs)),
            'cl_export_filename': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/cl_export_file/%s?download=true' % (self._name, self.id, filename),
            'target': 'self',
        }

    def _cl_build_xlsx(self, logs):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet('Vendor Sheet')
        header = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
        header_fill = workbook.add_format({'bold': True, 'bg_color': '#FFE699', 'border': 1})
        fill = workbook.add_format({'bg_color': '#FFF2CC', 'border': 1})
        fill_money = workbook.add_format({'bg_color': '#FFF2CC', 'border': 1, 'num_format': '#,##0.00'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        number = workbook.add_format({'num_format': '#,##0.000'})
        for col, title in enumerate(HEADERS):
            sheet.write_string(0, col, title, header_fill if title in (COL_ACTUAL, COL_NOTES) else header)
        for row, log in enumerate(logs, start=1):
            sheet.write_number(row, 0, log.id)
            sheet.write_string(row, 1, log.name or '')
            sheet.write_string(row, 2, fields.Date.to_string(log.cl_date) if log.cl_date else '')
            sheet.write_string(row, 3, log.cl_partner_id.display_name or '')
            sheet.write_string(row, 4, log.cl_carrier_id.display_name or '')
            sheet.write_number(row, 5, log.cl_weight, number)
            if log.state == 'ok':
                sheet.write_number(row, 6, log.cl_expected_cost, money)
            else:
                sheet.write_blank(row, 6, None)
            # Never pre-fill zero: a blank cell means "not billed yet" and is skipped on import.
            if log.cl_has_actual_cost:
                sheet.write_number(row, 7, log.cl_actual_cost, fill_money)
            else:
                sheet.write_blank(row, 7, None, fill_money)
            if log.cl_notes:
                sheet.write_string(row, 8, log.cl_notes, fill)
            else:
                sheet.write_blank(row, 8, None, fill)
        sheet.freeze_panes(1, 0)
        sheet.set_column(0, 0, 8)
        sheet.set_column(1, 1, 18)
        sheet.set_column(2, 2, 13)
        sheet.set_column(3, 4, 28)
        sheet.set_column(5, 7, 14)
        sheet.set_column(8, 8, 40)
        workbook.close()
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _cl_read_rows(self, content, filename):
        """Read a CSV / XLS / XLSX / ODS file with Odoo's own import engine."""
        extension = os.path.splitext(filename or '')[1].lower()
        importer = self.env['base_import.import'].create({
            'res_model': 'cl.courier.cost',
            'file': content,
            'file_name': filename,
            'file_type': MIMETYPES.get(extension, False),
        })
        encoding = ''  # let base_import detect it, unless the text is plain UTF-8
        try:
            content.decode('utf-8')
            encoding = 'utf-8-sig'
        except UnicodeDecodeError:
            pass
        try:
            result = importer._read_file({'quoting': '"', 'separator': '', 'encoding': encoding})
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001 - report any reader problem to the user
            raise UserError(_("The file could not be read: %s", exc)) from None
        return [list(row) for row in result[1]] if result else []

    @api.model
    def _cl_decimal_point(self):
        lang = self.env['res.lang'].sudo().with_context(active_test=False).search(
            [('code', '=', self.env.lang or 'en_US')], limit=1)
        return lang.decimal_point or '.'

    @api.model
    def _cl_parse_amount(self, text):
        """Return the amount written in ``text``, or None when it is not a valid amount.

        Number cells of a spreadsheet arrive as plain numbers. Amounts typed
        as text (CSV) may use either decimal sign: the right-most of ',' and
        '.' is the decimal sign and the other one groups thousands
        (1,234.50 and 1.234,50). A lone comma followed by exactly three digits
        (1,234) is read with the decimal sign of the user's language.
        """
        text = ''.join((text or '').split())  # also removes non-breaking spaces
        if ',' in text:
            last_comma, last_dot = text.rfind(','), text.rfind('.')
            if last_dot > last_comma:  # 1,234.50
                text = text.replace(',', '')
            elif last_dot >= 0:  # 1.234,50
                text = text.replace('.', '').replace(',', '.')
            elif text.count(',') > 1:  # 1,234,567
                text = text.replace(',', '')
            else:
                whole, decimals = text.split(',')
                if len(decimals) == 3 and whole.strip('+-0') and self._cl_decimal_point() != ',':
                    text = whole + decimals  # 1,234 where the decimal sign is a dot
                else:
                    text = '%s.%s' % (whole, decimals)  # 12,50
        elif text.count('.') > 1:  # 1.234.567
            text = text.replace('.', '')
        try:
            amount = float(text)
        except ValueError:
            return None
        # refuse negative amounts and nan / inf / 1e999
        return amount if math.isfinite(amount) and amount >= 0 else None

    def _cl_find_log(self, log_id_text, reference):
        cost_model = self.env['cl.courier.cost']
        if log_id_text:
            try:
                log_id = int(float(log_id_text))
            except (ValueError, OverflowError):  # text, nan, inf
                log_id = 0
            if not 0 < log_id < 2 ** 31:  # outside the range of a database id
                log_id = 0
            log = cost_model.search([('id', '=', log_id)]) if log_id else cost_model
            # the reference, when given, must agree with the id (protects against sheets from another database)
            if log and (not reference or log.name == reference):
                return log
            return cost_model
        if reference:
            logs = cost_model.search([('name', '=', reference)])
            return logs if len(logs) == 1 else cost_model
        return cost_model

    def action_cl_import(self):
        self.ensure_one()
        if not self.cl_import_file:
            raise UserError(_("Choose the filled vendor sheet to import."))
        rows = self._cl_read_rows(base64.b64decode(self.cl_import_file), self.cl_import_filename or '')
        if not rows:
            raise UserError(_("The file is empty."))
        header = [str(cell or '').strip().lower() for cell in rows[0]]

        def column(title):
            return header.index(title.lower()) if title.lower() in header else None

        id_col, ref_col = column(COL_LOG_ID), column(COL_REFERENCE)
        actual_col, notes_col = column(COL_ACTUAL), column(COL_NOTES)
        if actual_col is None or (id_col is None and ref_col is None):
            raise UserError(_(
                "The first row must contain the columns “%(actual)s” and “%(log_id)s” or “%(reference)s”.",
                actual=COL_ACTUAL, log_id=COL_LOG_ID, reference=COL_REFERENCE))

        counts = dict.fromkeys(('updated', 'blank', 'locked', 'not_found', 'invalid'), 0)
        problems = []
        for line_number, row in enumerate(rows[1:], start=2):
            def cell(index, row=row):
                if index is None or index >= len(row) or row[index] is None:
                    return ''
                return str(row[index]).strip()

            raw_amount = cell(actual_col)
            if not raw_amount:
                counts['blank'] += 1
                continue
            reference = cell(ref_col)
            log = self._cl_find_log(cell(id_col), reference)
            if not log:
                counts['not_found'] += 1
                problems.append(_("Row %(row)s: delivery %(ref)s not found.", row=line_number, ref=reference or cell(id_col)))
                continue
            if log.cl_is_locked:
                counts['locked'] += 1
                continue
            amount = self._cl_parse_amount(raw_amount)
            if amount is None:
                counts['invalid'] += 1
                problems.append(_("Row %(row)s: “%(value)s” is not a valid amount.", row=line_number, value=raw_amount))
                continue
            vals = {'cl_actual_cost': amount, 'cl_has_actual_cost': True, 'cl_is_locked': True}
            notes = cell(notes_col)
            if notes:
                vals['cl_notes'] = notes
            log.write(vals)
            counts['updated'] += 1

        if len(problems) > MAX_PROBLEMS_SHOWN:
            problems = problems[:MAX_PROBLEMS_SHOWN] + [_("... and %s more.", len(problems) - MAX_PROBLEMS_SHOWN)]
        self.write({
            'cl_import_done': True,
            'cl_count_updated': counts['updated'],
            'cl_count_blank': counts['blank'],
            'cl_count_locked': counts['locked'],
            'cl_count_not_found': counts['not_found'],
            'cl_count_invalid': counts['invalid'],
            'cl_import_problems': '\n'.join(problems) or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Vendor Sheet'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
