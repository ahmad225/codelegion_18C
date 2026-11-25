# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import io

import xlsxwriter

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.cl_courier_cost.wizard.cl_courier_cost_exchange import HEADERS

from .common import ClCourierCostCommon


@tagged('post_install', '-at_install')
class TestVendorSheet(ClCourierCostCommon):

    def setUp(self):
        super().setUp()
        self.log_a = self._log(self._deliver(qty=1))
        self.log_b = self._log(self._deliver(qty=2))

    def _import(self, content, filename):
        wizard = self.env['cl.courier.cost.exchange'].with_user(self.courier_user).create({
            'cl_mode': 'import',
            'cl_import_file': base64.b64encode(content),
            'cl_import_filename': filename,
        })
        wizard.action_cl_import()
        return wizard

    def _csv(self, rows):
        lines = ['Log ID,Reference,Actual Cost,Notes'] + [','.join(str(cell) for cell in row) for row in rows]
        return ('\n'.join(lines) + '\n').encode()

    def test_import_skips_blank_rows_and_locks_filled_ones(self):
        content = self._csv([
            (self.log_a.id, self.log_a.name, '45.50', 'Bill 1001'),
            (self.log_b.id, self.log_b.name, '', ''),
        ])
        wizard = self._import(content, 'sheet.csv')
        self.assertEqual(wizard.cl_count_updated, 1)
        self.assertEqual(wizard.cl_count_blank, 1)
        self.assertAlmostEqual(self.log_a.cl_actual_cost, 45.5)
        self.assertTrue(self.log_a.cl_has_actual_cost)
        self.assertTrue(self.log_a.cl_is_locked)
        self.assertEqual(self.log_a.cl_notes, 'Bill 1001')
        # the blank row is untouched: not zero, not billed, not locked
        self.assertFalse(self.log_b.cl_has_actual_cost)
        self.assertFalse(self.log_b.cl_is_locked)
        self.assertEqual(self.log_b.cl_actual_cost, 0.0)

        # a second import never overwrites a locked log and reports unknown rows
        content = self._csv([
            (self.log_a.id, self.log_a.name, '99', ''),
            (999999999, 'WH/OUT/NOPE', '12', ''),
            (self.log_b.id, self.log_b.name, 'abc', ''),
        ])
        wizard = self._import(content, 'sheet.csv')
        self.assertEqual(wizard.cl_count_locked, 1)
        self.assertEqual(wizard.cl_count_not_found, 1)
        self.assertEqual(wizard.cl_count_invalid, 1)
        self.assertEqual(wizard.cl_count_updated, 0)
        self.assertAlmostEqual(self.log_a.cl_actual_cost, 45.5)
        self.assertFalse(self.log_b.cl_has_actual_cost)

    def test_explicit_zero_is_a_value(self):
        wizard = self._import(self._csv([(self.log_b.id, self.log_b.name, '0', '')]), 'sheet.csv')
        self.assertEqual(wizard.cl_count_updated, 1)
        self.assertTrue(self.log_b.cl_has_actual_cost)
        self.assertTrue(self.log_b.cl_is_locked)

    def test_missing_columns(self):
        with self.assertRaises(UserError):
            self._import(b'Reference,Cost\nX,1\n', 'sheet.csv')

    def test_xlsx_export_and_import(self):
        export = self.env['cl.courier.cost.exchange'].with_user(self.courier_user).create({'cl_mode': 'export'})
        export.action_cl_export()
        content = base64.b64decode(export.cl_export_file)
        try:
            rows = export._cl_read_rows(content, 'sheet.xlsx')
        except UserError as exc:
            self.skipTest("No XLSX reader available for base_import: %s" % exc)
        self.assertEqual(rows[0], HEADERS)
        exported_ids = {int(float(row[0])) for row in rows[1:]}
        self.assertTrue({self.log_a.id, self.log_b.id} <= exported_ids)
        actual_index = HEADERS.index('Actual Cost')
        self.assertTrue(all(row[actual_index] == '' for row in rows[1:]))

        # the courier fills one row and leaves the other blank
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet()
        for col, title in enumerate(HEADERS):
            sheet.write_string(0, col, title)
        sheet.write_number(1, 0, self.log_a.id)
        sheet.write_string(1, 1, self.log_a.name)
        sheet.write_number(1, actual_index, 37.25)
        sheet.write_number(2, 0, self.log_b.id)
        sheet.write_string(2, 1, self.log_b.name)
        sheet.write_blank(2, actual_index, None)
        workbook.close()
        wizard = self._import(buffer.getvalue(), 'filled.xlsx')
        self.assertEqual(wizard.cl_count_updated, 1)
        self.assertEqual(wizard.cl_count_blank, 1)
        self.assertAlmostEqual(self.log_a.cl_actual_cost, 37.25)
        self.assertTrue(self.log_a.cl_is_locked)
        self.assertFalse(self.log_b.cl_is_locked)

    def test_amount_formats(self):
        parse = self.env['cl.courier.cost.exchange'].with_context(lang='en_US')._cl_parse_amount
        for text, expected in (
                ('45.50', 45.5), ('12,50', 12.5), ('1,234.50', 1234.5), ('1.234,50', 1234.5),
                ('1,234,567', 1234567.0), ('1.234.567', 1234567.0), ('1\xa0234,50', 1234.5),
                (' 7 ', 7.0), ('0,125', 0.125), ('1,234', 1234.0), ('0', 0.0), ('1.234', 1.234)):
            self.assertAlmostEqual(parse(text), expected, msg=text)
        for text in ('abc', '', '-5', 'inf', 'nan', '1e999', '12,50,1.5.2', '$5'):
            self.assertIsNone(parse(text), msg=text)

    def test_crafted_sheet_values_are_reported_not_fatal(self):
        content = self._csv([
            ('inf', self.log_a.name, '10', ''),
            ('nan', self.log_a.name, '10', ''),
            ('99999999999999999999', self.log_a.name, '10', ''),
            (self.log_a.id, 'WH/OUT/OTHER', '10', ''),
            (self.log_b.id, self.log_b.name, 'inf', ''),
            (self.log_b.id, self.log_b.name, '1e999', ''),
            (self.log_b.id, self.log_b.name, '=1+1', ''),
        ])
        wizard = self._import(content, 'sheet.csv')
        self.assertEqual(wizard.cl_count_not_found, 4)
        self.assertEqual(wizard.cl_count_invalid, 3)
        self.assertEqual(wizard.cl_count_updated, 0)
        self.assertFalse(self.log_a.cl_has_actual_cost)
        self.assertFalse(self.log_b.cl_has_actual_cost)

    def test_european_amount_is_not_divided_by_a_thousand(self):
        content = ('Log ID;Reference;Actual Cost;Notes\n%s;%s;1.234,50;\n' % (
            self.log_a.id, self.log_a.name)).encode()
        wizard = self._import(content, 'sheet.csv')
        self.assertEqual(wizard.cl_count_updated, 1)
        self.assertAlmostEqual(self.log_a.cl_actual_cost, 1234.5)
