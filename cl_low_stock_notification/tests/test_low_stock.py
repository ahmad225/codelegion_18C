# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestLowStock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.shelf = cls.env['stock.location'].create({
            'name': 'Low Stock Shelf', 'usage': 'internal',
            'location_id': cls.stock.id, 'company_id': cls.company.id})
        cls.supplier = cls.env.ref('stock.stock_location_suppliers')
        cls.recipient = new_test_user(
            cls.env, login='cl_low_stock_recipient', email='low.stock@example.com',
            groups='base.group_user')
        cls.company.write({
            'cl_low_stock_alert': True,
            'cl_low_stock_source': 'product',
            'cl_low_stock_basis': 'on_hand',
            'cl_low_stock_min_qty': 0.0,
            'cl_low_stock_location_ids': [(5, 0, 0)],
            'cl_low_stock_user_ids': [(6, 0, cls.recipient.ids)],
            'cl_low_stock_tz': 'UTC',
        })
        Product = cls.env['product.product']
        cls.low = Product.create({
            'name': 'CL Low Widget', 'type': 'consu', 'is_storable': True,
            'default_code': 'CL-LOW', 'cl_low_stock_min_qty': 5.0})
        cls.fine = Product.create({
            'name': 'CL Stocked Widget', 'type': 'consu', 'is_storable': True,
            'cl_low_stock_min_qty': 5.0})
        cls.unwatched = Product.create({
            'name': 'CL Unwatched Widget', 'type': 'consu', 'is_storable': True})
        cls.env['stock.quant']._update_available_quantity(cls.low, cls.stock, 2.0)
        cls.env['stock.quant']._update_available_quantity(cls.fine, cls.stock, 9.0)

    def _rows(self):
        return {row['product_id']: row for row in self.company._cl_low_stock_rows()}

    def _incoming(self, product, qty, location):
        move = self.env['stock.move'].create({
            'name': 'incoming %s' % product.name,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'location_id': self.supplier.id,
            'location_dest_id': location.id,
            'company_id': self.company.id,
        })
        move._action_confirm()
        return move

    # ------------------------------------------------------------------
    # Thresholds
    # ------------------------------------------------------------------

    def test_minimum_set_on_product(self):
        rows = self._rows()
        self.assertIn(self.low.id, rows)
        self.assertNotIn(self.fine.id, rows, "9 on hand is above the minimum of 5")
        self.assertNotIn(self.unwatched.id, rows, "no minimum means never reported")
        row = rows[self.low.id]
        self.assertEqual(row['on_hand'], 2.0)
        self.assertEqual(row['minimum'], 5.0)
        self.assertEqual(row['shortfall'], 3.0)
        self.assertEqual(row['reference'], 'CL-LOW')

    def test_one_minimum_for_all_products(self):
        self.company.write({'cl_low_stock_source': 'company', 'cl_low_stock_min_qty': 3.0})
        untracked = self.env['product.product'].create({
            'name': 'CL Untracked Goods', 'type': 'consu', 'is_storable': False})
        service = self.env['product.product'].create({
            'name': 'CL Service', 'type': 'service'})
        rows = self._rows()
        self.assertIn(self.low.id, rows)             # 2 < 3
        self.assertIn(self.unwatched.id, rows)       # 0 < 3
        self.assertNotIn(self.fine.id, rows)         # 9 >= 3
        self.assertNotIn(untracked.id, rows, "goods not tracked in stock have no quantity")
        self.assertNotIn(service.id, rows)
        self.company.cl_low_stock_min_qty = 0.0
        self.assertFalse(self._rows(), "a minimum of 0 reports nothing")

    def test_minimum_of_reordering_rules(self):
        self.company.cl_low_stock_source = 'orderpoint'
        Orderpoint = self.env['stock.warehouse.orderpoint']
        for product in (self.low, self.fine):
            Orderpoint.create({
                'product_id': product.id, 'location_id': self.stock.id,
                'warehouse_id': self.warehouse.id,
                'product_min_qty': 4.0, 'product_max_qty': 20.0})
        rows = self._rows()
        self.assertIn(self.low.id, rows)
        self.assertNotIn(self.fine.id, rows)
        self.assertEqual(rows[self.low.id]['minimum'], 4.0)
        self.assertEqual(rows[self.low.id]['location'], self.stock.display_name)

    # ------------------------------------------------------------------
    # Quantities
    # ------------------------------------------------------------------

    def test_forecast_counts_what_is_coming(self):
        self._incoming(self.low, 10.0, self.stock)
        self.assertIn(self.low.id, self._rows(), "on hand is still 2")
        self.company.cl_low_stock_basis = 'forecast'
        self.assertNotIn(self.low.id, self._rows(), "2 on hand + 10 incoming >= 5")

    def test_locations_scope_every_quantity(self):
        """Stock and receipts of other locations do not hide a shortage."""
        self.company.write({
            'cl_low_stock_basis': 'forecast',
            'cl_low_stock_location_ids': [(6, 0, self.shelf.ids)],
        })
        # 9 on hand in WH/Stock, nothing on the shelf, 50 expected in WH/Stock.
        self._incoming(self.fine, 50.0, self.stock)
        rows = self._rows()
        self.assertIn(self.fine.id, rows)
        row = rows[self.fine.id]
        self.assertEqual(row['on_hand'], 0.0)
        self.assertEqual(row['incoming'], 0.0)
        self.assertEqual(row['forecast'], 0.0)
        self.assertEqual(row['location'], self.shelf.display_name)
        # Goods expected on the shelf itself do count.
        self._incoming(self.fine, 50.0, self.shelf)
        self.assertNotIn(self.fine.id, self._rows())

    # ------------------------------------------------------------------
    # Product field
    # ------------------------------------------------------------------

    def test_template_mirrors_its_only_variant(self):
        template = self.low.product_tmpl_id
        self.assertEqual(template.cl_low_stock_min_qty, 5.0)
        template.cl_low_stock_min_qty = 8.0
        self.assertEqual(self.low.cl_low_stock_min_qty, 8.0)
        created = self.env['product.template'].create({
            'name': 'CL Template', 'type': 'consu', 'is_storable': True,
            'cl_low_stock_min_qty': 6.0})
        self.assertEqual(created.product_variant_id.cl_low_stock_min_qty, 6.0)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def test_excel_file(self):
        rows = self.company._cl_low_stock_rows()
        filename, content = self.company._cl_low_stock_xlsx(rows)
        self.assertTrue(filename.endswith('.xlsx'))
        self.assertTrue(content.startswith(b'PK'), "an xlsx file is a zip archive")

    def test_pdf_report_content(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'cl_low_stock_notification.report_low_stock', self.company.ids)[0]
        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn('CL Low Widget', html)
        self.assertNotIn('CL Stocked Widget', html)

    def test_report_is_for_inventory_administrators(self):
        Report = self.env['report.cl_low_stock_notification.report_low_stock']
        stock_user = new_test_user(
            self.env, login='cl_low_stock_plain_user',
            groups='base.group_user,stock.group_stock_user')
        with self.assertRaises(AccessError):
            Report.with_user(stock_user)._get_report_values(self.company.ids)
        manager = new_test_user(
            self.env, login='cl_low_stock_manager',
            groups='base.group_user,stock.group_stock_manager')
        values = Report.with_user(manager)._get_report_values(self.company.ids)
        low_ids = [row['product_id'] for row in values['sections'][self.company.id]['rows']]
        self.assertIn(self.low.id, low_ids)
        wizard = self.env['cl.low.stock.report.wizard'].with_user(manager).create({})
        self.assertTrue(wizard.action_download_xlsx())
        with self.assertRaises(AccessError):
            self.env['cl.low.stock.report.wizard'].with_user(stock_user).create({})

    def test_wizard_actions(self):
        wizard = self.env['cl.low.stock.report.wizard'].create({})
        self.assertEqual(wizard.company_id, self.company)
        action = wizard.action_download_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertTrue(wizard.xlsx_file)
        self.assertIn(wizard.xlsx_filename, action['url'])
        # A report action, or Odoo's document layout assistant on a new database.
        self.assertTrue(wizard.action_print_pdf().get('type'))
        self.assertEqual(wizard.action_send_now()['tag'], 'display_notification')

    def test_wizard_messages(self):
        wizard = self.env['cl.low.stock.report.wizard'].create({})
        self.low.cl_low_stock_min_qty = 0.0
        with self.assertRaises(UserError):
            wizard.action_print_pdf()       # nothing is low
        self.company.cl_low_stock_alert = False
        with self.assertRaises(UserError):
            wizard.action_download_xlsx()   # feature switched off

    # ------------------------------------------------------------------
    # E-mail
    # ------------------------------------------------------------------

    def test_email_is_queued_with_the_sheet_attached(self):
        mail = self.company._cl_low_stock_send()
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.state, 'outgoing', "queued, not sent inside the transaction")
        self.assertEqual(mail.recipient_ids, self.recipient.partner_id)
        self.assertEqual(len(mail.attachment_ids), 1)
        self.assertTrue(mail.attachment_ids.name.endswith('.xlsx'))
        self.assertIn('CL Low Widget', mail.body_html)
        self.assertIn(self.company.name, mail.subject)

    def test_no_email_when_nothing_is_low_or_nobody_listens(self):
        self.company.cl_low_stock_user_ids = [(5, 0, 0)]
        self.assertFalse(self.company._cl_low_stock_send())
        self.company.cl_low_stock_user_ids = [(6, 0, self.recipient.ids)]
        self.low.cl_low_stock_min_qty = 0.0
        self.assertFalse(self.company._cl_low_stock_send())

    def test_cron_only_handles_enabled_companies(self):
        other = self.env['res.company'].create({'name': 'CL Low Stock Other Co'})
        other.write({
            'cl_low_stock_alert': False,
            'cl_low_stock_user_ids': [(6, 0, self.recipient.ids)],
        })
        Mail = self.env['mail.mail']
        domain = [('model', '=', 'res.company'), ('res_id', 'in', (self.company | other).ids)]
        before = Mail.search(domain)
        self.env['res.company']._cron_cl_low_stock_notify()
        new_mails = Mail.search(domain) - before
        self.assertEqual(new_mails.mapped('res_id'), [self.company.id])
