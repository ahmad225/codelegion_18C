# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.tools import SQL, float_compare, float_round


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        # A line created without a price (import, API, product catalog) gets
        # its price deduced by the standard onchange helper, which does not
        # bring the discount along. Complete those lines afterwards so the
        # last purchase price always comes with its own discount.
        deduced = [
            not vals.get('display_type')
            and 'price_unit' not in vals
            and 'discount' not in vals
            for vals in vals_list
        ]
        lines = super().create(vals_list)
        to_complete = lines.browse(
            [line.id for line, flag in zip(lines, deduced) if flag])
        last_lines = to_complete._cl_filter_last_price_lines()._cl_map_last_purchase_lines()
        for line in to_complete:
            match = last_lines.get(line.id)
            if match and match.discount:
                line.discount = match.discount
        return lines

    @api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        # Remember what each line carried before the standard computation, so a
        # price typed by the user can be told apart from one that was reset.
        previous = {line.id: (line.price_unit, line.discount) for line in self}

        super()._compute_price_unit_and_date_planned_and_name()

        applicable = self._cl_filter_last_price_lines()
        last_lines = applicable._cl_map_last_purchase_lines()
        for line in applicable:
            match = last_lines.get(line.id)
            if not match:
                continue
            old_price, old_discount = previous.get(line.id, (0.0, 0.0))
            if line._cl_keeps_current_price(old_price):
                # Standard Odoo resets the discount even when it keeps the
                # price; put back the one that goes with that price.
                line.discount = old_discount
                continue
            line.price_unit = self._cl_convert_last_price(match, line)
            line.discount = match.discount

    def _cl_filter_last_price_lines(self):
        """Lines that may receive the last purchase price: product lines of a
        draft or sent RFQ, not billed, in a company where the option is on."""
        return self.filtered(lambda l: (
            l.company_id.cl_last_po_price
            and l.product_id
            and l.order_id.partner_id
            and l.order_id.state in ('draft', 'sent')
            and not l.invoice_lines
            and (l.company_id.cl_last_po_price_products != 'variants'
                 or l.product_id.product_tmpl_id.attribute_line_ids)
        ))

    def _cl_map_last_purchase_lines(self):
        """Return ``{line.id: last confirmed purchase line}`` for the lines of
        ``self`` whose product was purchased before, following the vendor scope
        of each company. One query per company, whatever the number of lines."""
        result = {}
        for company in self.company_id:
            company_lines = self.filtered(lambda l: l.company_id == company)
            same_vendor = company.cl_last_po_price_vendor == 'same'
            last_lines = self._cl_get_last_purchase_lines(
                company,
                company_lines.product_id,
                company_lines.order_id.partner_id if same_vendor else None,
            )
            for line in company_lines:
                key = line.product_id.id
                if same_vendor:
                    key = (key, line.order_id.partner_id.id)
                if key in last_lines:
                    result[line.id] = last_lines[key]
        return result

    def _cl_keeps_current_price(self, previous_price):
        """Tell whether the line must keep the price it already has.

        That is the case for a saved line that already had a price, when the
        standard computation left that price alone and neither the product, the
        unit of measure nor the vendor changed: only the quantity moved, and
        the last purchase price does not depend on it. This protects a price
        typed by the user in the same situations standard Odoo protects it.
        """
        self.ensure_one()
        origin = self._origin
        if not previous_price or not origin:
            return False
        digits = self.env['decimal.precision'].precision_get('Product Price')
        if float_compare(self.price_unit, previous_price, precision_digits=digits) != 0:
            return False
        return (
            origin.product_id == self.product_id
            and origin.product_uom == self.product_uom
            and origin.order_id.partner_id == self.order_id.partner_id
        )

    @api.model
    def _cl_get_last_purchase_lines(self, company, products, partners=None):
        """Return the most recently confirmed purchase line of each product.

        :param company: company the purchase orders belong to
        :param products: product.product recordset to look up
        :param partners: optional res.partner recordset; when given, the result
            is split by vendor and only those vendors are considered
        :return: ``{product_id: line}``, or ``{(product_id, partner_id): line}``
            when ``partners`` is given (sudo records)
        """
        by_vendor = partners is not None
        # New (unsaved) products or vendors cannot have purchase history.
        product_ids = tuple(pid for pid in products.ids if isinstance(pid, int))
        partner_ids = tuple(
            pid for pid in (partners.ids if by_vendor else ()) if isinstance(pid, int))
        if not product_ids or (by_vendor and not partner_ids):
            return {}
        self.env['purchase.order.line'].flush_model(['product_id', 'company_id', 'order_id'])
        self.env['purchase.order'].flush_model(['state', 'partner_id', 'date_approve'])
        vendor_key = SQL(", po.partner_id") if by_vendor else SQL()
        vendor_filter = SQL("AND po.partner_id IN %s", partner_ids) if by_vendor else SQL()
        # One row per product (and vendor): the line of the latest confirmed
        # order. DISTINCT ON keeps the first row of each group in ORDER BY.
        self.env.cr.execute(SQL(
            """
            SELECT DISTINCT ON (pol.product_id%(vendor_key)s)
                   pol.product_id, po.partner_id, pol.id
              FROM purchase_order_line pol
              JOIN purchase_order po ON po.id = pol.order_id
             WHERE pol.product_id IN %(product_ids)s
               AND pol.company_id = %(company_id)s
               AND po.state IN ('purchase', 'done')
               %(vendor_filter)s
          ORDER BY pol.product_id%(vendor_key)s,
                   po.date_approve DESC NULLS LAST,
                   pol.id DESC
            """,
            vendor_key=vendor_key,
            product_ids=product_ids,
            company_id=company.id,
            vendor_filter=vendor_filter,
        ))
        lines = self.env['purchase.order.line'].sudo()
        result = {}
        for product_id, partner_id, line_id in self.env.cr.fetchall():
            key = (product_id, partner_id) if by_vendor else product_id
            result[key] = lines.browse(line_id)
        return result

    @api.model
    def _cl_convert_last_price(self, source_line, target_line):
        """Convert the source line's unit price to the target line's unit of
        measure and currency, rounded like standard purchase prices."""
        price = source_line.price_unit
        src_uom = source_line.product_uom
        dst_uom = target_line.product_uom
        if src_uom and dst_uom and src_uom != dst_uom:
            price = src_uom._compute_price(price, dst_uom)
        src_cur = source_line.currency_id
        dst_cur = target_line.currency_id
        if src_cur and dst_cur and src_cur != dst_cur:
            price = src_cur._convert(
                price, dst_cur, target_line.company_id,
                target_line.order_id.date_order or fields.Date.context_today(target_line),
                round=False)
        if dst_cur:
            digits = max(
                dst_cur.decimal_places,
                self.env['decimal.precision'].precision_get('Product Price'))
            price = float_round(price, precision_digits=digits)
        return price
