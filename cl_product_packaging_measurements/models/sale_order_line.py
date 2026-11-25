# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

_SNAPSHOT_FIELDS = ('cl_packaging_dimensions', 'cl_packaging_weight')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Stored copies of the packaging's measurements. They only depend on which
    # packaging is on the line, so they are taken again each time the packaging
    # of the line changes (by the user, the website or Odoo itself when the
    # quantity changes) and are not affected by later edits of the packaging.
    # Quotations are refreshed by product.packaging when it is edited.
    cl_packaging_dimensions = fields.Char(
        string='Pkg. Dimensions', compute='_compute_cl_packaging_measurements',
        store=True,
        help="Length x width x height of the packaging. Follows the packaging "
             "while the order is a quotation; kept as it was once confirmed.")
    cl_packaging_weight = fields.Char(
        string='Pkg. Gross Weight', compute='_compute_cl_packaging_measurements',
        store=True,
        help="Gross weight of one packaging. Follows the packaging while the "
             "order is a quotation; kept as it was once confirmed.")

    def _auto_init(self):
        # When the module is installed no packaging has measurements yet, so
        # every existing line would compute to "empty". Create the columns
        # directly instead of computing each line of a large order history.
        for name in _SNAPSHOT_FIELDS:
            if not column_exists(self.env.cr, self._table, name):
                create_column(self.env.cr, self._table, name, 'varchar')
        return super()._auto_init()

    @api.depends('product_packaging_id')
    def _compute_cl_packaging_measurements(self):
        for line in self:
            packaging = line.product_packaging_id
            line.cl_packaging_dimensions = packaging.cl_dimensions or False
            line.cl_packaging_weight = packaging.cl_gross_weight_label or False
