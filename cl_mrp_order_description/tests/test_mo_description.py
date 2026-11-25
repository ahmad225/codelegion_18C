# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMoDescription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        product = cls.env['product.product'].create({'name': 'Printed Cup', 'type': 'consu'})
        cls.mo = cls.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 10,
            'cl_mo_description': 'Print logo in Pantone 286C\nPack per 50'})

    def _render(self, mo):
        html, _fmt = self.env['ir.actions.report']._render_qweb_html(
            'mrp.action_report_production_order', mo.ids)
        return html.decode() if isinstance(html, bytes) else html

    def test_description_on_report(self):
        html = self._render(self.mo)
        self.assertIn('Pantone 286C', html)
        self.assertIn('Pack per 50', html)

    def test_report_without_description(self):
        # An order without description still prints, without the extra block.
        self.mo.cl_mo_description = False
        html = self._render(self.mo)
        self.assertIn(self.mo.name, html)
        self.assertNotIn('cl_mo_description_block', html)

    def test_shop_floor_note_safe_without_enterprise(self):
        # Never raises, whether or not mrp_workorder is installed.
        note = self.mo.cl_shop_floor_note
        if 'log_note' not in self.mo._fields:
            self.assertFalse(note)

    def test_note_as_text(self):
        # The Shop Floor note is read as plain text whatever its field type.
        Production = self.env['mrp.production']
        self.assertFalse(Production._cl_note_as_text(False, 'text'))
        self.assertFalse(Production._cl_note_as_text('<p><br></p>', 'html'))
        self.assertEqual(Production._cl_note_as_text('Glue twice', 'text'), 'Glue twice')
        self.assertEqual(Production._cl_note_as_text('<p>Glue twice</p>', 'html'), 'Glue twice')

    def test_description_copied_with_mo(self):
        self.assertEqual(self.mo.copy().cl_mo_description, self.mo.cl_mo_description)

    def test_description_has_a_label_on_the_form(self):
        # The field must be a direct child of a <group>, otherwise the form
        # shows it without its label.
        arch = self.env['mrp.production'].get_view(
            self.env.ref('mrp.mrp_production_form_view').id, 'form')['arch']
        node = etree.fromstring(arch).xpath("//field[@name='cl_mo_description']")
        self.assertEqual(len(node), 1)
        self.assertEqual(node[0].getparent().tag, 'group')

    def test_search_on_description(self):
        found = self.env['mrp.production'].search([('cl_mo_description', 'ilike', 'pantone')])
        self.assertIn(self.mo, found)
