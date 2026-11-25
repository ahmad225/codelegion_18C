# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import io
import logging

from odoo import _, api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import UserError
from odoo.tools import float_compare, split_every
from odoo.tools.misc import format_datetime, xlsxwriter

_logger = logging.getLogger(__name__)

# Products are read by slices so a large catalogue never sits in memory at once.
_SLICE = 1000
# Lines shown in the body of the e-mail; the attached sheet has them all.
_MAIL_PREVIEW_LINES = 10


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_low_stock_alert = fields.Boolean(
        string='Low Stock Alerts',
        help="Send a daily e-mail listing the products that are below their "
             "minimum stock, and enable the Low Stock report.")
    cl_low_stock_source = fields.Selection(
        selection=[
            ('company', 'One minimum for all products'),
            ('product', 'Minimum set on each product'),
            ('orderpoint', 'Minimum of the reordering rules'),
        ],
        string='Low Stock Threshold', default='company', required=True,
        help="Where the minimum quantity of a product comes from.")
    cl_low_stock_min_qty = fields.Float(
        string='Minimum for All Products', digits='Product Unit of Measure')
    cl_low_stock_basis = fields.Selection(
        selection=[
            ('on_hand', 'Quantity on hand'),
            ('forecast', 'Forecasted quantity'),
        ],
        string='Low Stock Compares', default='on_hand', required=True,
        help="Quantity on hand: what is physically in stock now.\n"
             "Forecasted quantity: on hand, plus what is coming in, minus what "
             "is going out.")
    cl_low_stock_location_ids = fields.Many2many(
        'stock.location', 'cl_low_stock_company_location_rel', 'company_id', 'location_id',
        string='Low Stock Locations',
        help="Only count the stock of these locations (and the locations inside "
             "them). Leave empty to count all the warehouses of the company.")
    cl_low_stock_user_ids = fields.Many2many(
        'res.users', 'cl_low_stock_company_user_rel', 'company_id', 'user_id',
        string='Low Stock Recipients',
        help="Users who receive the daily low stock e-mail.")
    cl_low_stock_tz = fields.Selection(
        _tz_get, string='Low Stock Timezone',
        default=lambda self: self.env.user.tz or 'UTC',
        help="Timezone of the date printed on the low stock report and e-mail.")

    # ------------------------------------------------------------------
    # What is low
    # ------------------------------------------------------------------

    def _cl_low_stock_scopes(self):
        """Tell what has to be checked, as a list of
        ``(locations, {product_id: minimum quantity})``.

        ``locations`` is the stock.location recordset whose stock is compared
        with the minimum; an empty recordset means all the company's warehouses.
        """
        self.ensure_one()
        if self.cl_low_stock_source == 'orderpoint':
            domain = [('company_id', '=', self.id)]
            if self.cl_low_stock_location_ids:
                domain.append(('location_id', 'child_of', self.cl_low_stock_location_ids.ids))
            # A rule watches one product at one location: compare there.
            per_location = {}
            for rule in self.env['stock.warehouse.orderpoint'].sudo().search(domain):
                per_location.setdefault(rule.location_id, {})[rule.product_id.id] = rule.product_min_qty
            return list(per_location.items())

        domain = [('is_storable', '=', True), ('company_id', 'in', (False, self.id))]
        if self.cl_low_stock_source == 'product':
            domain.append(('cl_low_stock_min_qty', '>', 0))
        elif self.cl_low_stock_min_qty <= 0:
            return []
        products = self.env['product.product'].sudo().search(domain)
        if self.cl_low_stock_source == 'product':
            minimums = {product.id: product.cl_low_stock_min_qty for product in products}
        else:
            minimums = dict.fromkeys(products.ids, self.cl_low_stock_min_qty)
        return [(self.cl_low_stock_location_ids, minimums)]

    def _cl_low_stock_rows(self):
        """Compute, without storing anything, the products of this company that
        are below their minimum.

        All the quantities of a row (on hand, free, incoming, outgoing,
        forecast) are measured on the same locations, so the forecast of a
        location is never hidden by goods expected somewhere else.

        :return: list of dicts sorted by location, then product
        """
        self.ensure_one()
        forecast = self.cl_low_stock_basis == 'forecast'
        Product = self.env['product.product'].sudo().with_context(
            allowed_company_ids=self.ids,
            lang=self.env.context.get('lang') or self.env.user.lang)
        rows = []
        for locations, minimums in self._cl_low_stock_scopes():
            if locations:
                scoped = Product.with_context(location=locations.ids)
                location_label = ", ".join(locations.mapped('display_name'))
            else:
                scoped = Product
                location_label = _("All warehouses")
            for product_ids in split_every(_SLICE, minimums):
                products = scoped.browse(product_ids)
                for product in products:
                    minimum = minimums[product.id]
                    compared = product.virtual_available if forecast else product.qty_available
                    if float_compare(
                            compared, minimum,
                            precision_rounding=product.uom_id.rounding) >= 0:
                        continue
                    rows.append({
                        'product_id': product.id,
                        'product': product.display_name,
                        'reference': product.default_code or '',
                        'category': product.categ_id.display_name or '',
                        'vendor': self._cl_low_stock_vendor(product),
                        'location': location_label,
                        'uom': product.uom_id.name,
                        'on_hand': product.qty_available,
                        'free': product.free_qty,
                        'incoming': product.incoming_qty,
                        'outgoing': product.outgoing_qty,
                        'forecast': product.virtual_available,
                        'minimum': minimum,
                        'shortfall': minimum - compared,
                    })
                # Free the slice before reading the next one.
                products.invalidate_recordset()
        rows.sort(key=lambda row: (row['location'], row['product'], row['product_id']))
        return rows

    def _cl_low_stock_vendor(self, product):
        """Name of the first vendor in the product's purchase tab that is valid
        for this company and this variant."""
        sellers = product.seller_ids.filtered(
            lambda seller: seller.company_id in (self, self.browse())
            and seller.product_id in (product, product.browse()))
        return sellers[:1].partner_id.display_name or ''

    def _cl_low_stock_summary(self, rows):
        """Header information shared by the e-mail, the PDF and the sheet."""
        self.ensure_one()
        labels = {
            name: dict(self._fields[name]._description_selection(self.env)).get(self[name], '')
            for name in ('cl_low_stock_source', 'cl_low_stock_basis')
        }
        return {
            'company': self.name,
            'threshold': labels['cl_low_stock_source'],
            'basis': labels['cl_low_stock_basis'],
            'locations': (
                ", ".join(self.cl_low_stock_location_ids.mapped('display_name'))
                or _("All warehouses")),
            'product_count': len({row['product_id'] for row in rows}),
            'line_count': len(rows),
            'date': format_datetime(
                self.env, fields.Datetime.now(), tz=self.cl_low_stock_tz or 'UTC'),
        }

    def _cl_low_stock_check_enabled(self):
        self.ensure_one()
        if not self.cl_low_stock_alert:
            raise UserError(_(
                "Low Stock Alerts are not enabled for %s. Turn them on in "
                "Inventory > Configuration > Settings > Low Stock Alerts.", self.name))

    # ------------------------------------------------------------------
    # Excel sheet
    # ------------------------------------------------------------------

    @api.model
    def _cl_low_stock_columns(self):
        """Columns of the detailed list: ``(title, row key, is a quantity)``."""
        return [
            (_("Product"), 'product', False),
            (_("Internal Reference"), 'reference', False),
            (_("Category"), 'category', False),
            (_("Vendor"), 'vendor', False),
            (_("Location"), 'location', False),
            (_("Unit"), 'uom', False),
            (_("On Hand"), 'on_hand', True),
            (_("Free to Use"), 'free', True),
            (_("Incoming"), 'incoming', True),
            (_("Outgoing"), 'outgoing', True),
            (_("Forecast"), 'forecast', True),
            (_("Minimum"), 'minimum', True),
            (_("Missing"), 'shortfall', True),
        ]

    def _cl_low_stock_xlsx(self, rows):
        """Build the Excel sheet of ``rows``.

        :return: ``(file name, file content as bytes)``
        """
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_("The Python library xlsxwriter is needed to build the Excel file."))
        summary = self._cl_low_stock_summary(rows)
        columns = self._cl_low_stock_columns()
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(_("Low Stock")[:31])
        title_style = workbook.add_format({'bold': True, 'font_size': 14})
        label_style = workbook.add_format({'bold': True})
        head_style = workbook.add_format(
            {'bold': True, 'bg_color': '#E7E9ED', 'border': 1, 'text_wrap': True})
        qty_style = workbook.add_format({'num_format': '#,##0.00'})
        missing_style = workbook.add_format({'num_format': '#,##0.00', 'bold': True})

        sheet.write(0, 0, _("Low Stock - %s", summary['company']), title_style)
        details = [
            (_("Date"), summary['date']),
            (_("Threshold"), summary['threshold']),
            (_("Compared quantity"), summary['basis']),
            (_("Locations"), summary['locations']),
            (_("Products below minimum"), summary['product_count']),
        ]
        for offset, (label, value) in enumerate(details, start=2):
            sheet.write(offset, 0, label, label_style)
            sheet.write(offset, 1, value)

        head_row = len(details) + 3
        for col, (title, key, is_qty) in enumerate(columns):
            sheet.write(head_row, col, title, head_style)
            sheet.set_column(col, col, 14 if is_qty else (40 if key == 'product' else 22))
        for line, row in enumerate(rows, start=head_row + 1):
            for col, (_title, key, is_qty) in enumerate(columns):
                if is_qty:
                    sheet.write_number(
                        line, col, row[key],
                        missing_style if key == 'shortfall' else qty_style)
                else:
                    sheet.write(line, col, row[key])
        sheet.freeze_panes(head_row + 1, 1)
        if rows:
            sheet.autofilter(head_row, 0, head_row + len(rows), len(columns) - 1)
        workbook.close()

        today = fields.Date.context_today(self.with_context(tz=self.cl_low_stock_tz or 'UTC'))
        return 'low_stock_%s_%s.xlsx' % (self.id, today), buffer.getvalue()

    # ------------------------------------------------------------------
    # E-mail
    # ------------------------------------------------------------------

    def _cl_low_stock_recipients(self):
        """Partners of the configured users that can receive an e-mail."""
        self.ensure_one()
        return self.cl_low_stock_user_ids.filtered('active').partner_id.filtered('email')

    def _cl_low_stock_send(self):
        """Queue the low stock e-mail of this company, with the Excel sheet
        attached. Nothing is queued when no product is low or nobody can
        receive it. The mail queue sends it, outside of this transaction.

        :return: the queued mail.mail (empty recordset when nothing was queued)
        """
        self.ensure_one()
        Mail = self.env['mail.mail'].sudo()
        template = self.env.ref(
            'cl_low_stock_notification.mail_template_cl_low_stock', raise_if_not_found=False)
        recipients = self._cl_low_stock_recipients()
        if not template or not recipients:
            _logger.info(
                "Low stock alert of %s skipped: %s.", self.name,
                "no recipient with an e-mail address" if template else "mail template deleted")
            return Mail
        rows = self._cl_low_stock_rows()
        if not rows:
            _logger.info("Low stock alert of %s: nothing is low.", self.name)
            return Mail
        filename, content = self._cl_low_stock_xlsx(rows)
        most_urgent = sorted(rows, key=lambda row: -row['shortfall'])[:_MAIL_PREVIEW_LINES]
        mail_id = template.with_context(
            cl_low_stock=self._cl_low_stock_summary(rows),
            cl_low_stock_rows=most_urgent,
        ).send_mail(self.id, force_send=False, email_values={
            'recipient_ids': [(4, partner.id) for partner in recipients],
            'attachments': [(filename, base64.b64encode(content))],
        })
        _logger.info(
            "Low stock alert of %s queued: %s line(s), %s recipient(s).",
            self.name, len(rows), len(recipients))
        return Mail.browse(mail_id)

    @api.model
    def _cron_cl_low_stock_notify(self):
        """Daily job: one e-mail per company that enabled the alerts."""
        for company in self.sudo().search([('cl_low_stock_alert', '=', True)]):
            company._cl_low_stock_send()
