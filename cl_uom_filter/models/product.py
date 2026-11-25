# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Same field name and relation table as the module
    # "Odoo Select Product UOM In Website" (website_uom_select_suggetion_spt),
    # so units already selected with that module are kept and the two modules
    # can be installed side by side. This module does not depend on it.
    product_uom_ids = fields.Many2many(
        'uom.uom', 'product_template_uom_rel', 'product_id', 'uom_id',
        string="Product UOMs",
        help="Units this product may be handled in. When set, only these units "
             "can be chosen on sales, purchase, inventory, manufacturing and "
             "invoice lines. Leave empty to allow every unit of the product's "
             "unit category.",
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _cl_get_allowed_uoms(self):
        """Return the units that may be chosen for this product on documents.

        * Units are selected in "Product UOMs" on the product: exactly those
          units (units of another category than the product's are ignored).
        * Nothing selected: every unit of the product's unit category, which is
          what Odoo offers by default.
        * No product: no unit.
        """
        if not self:
            return self.env['uom.uom']
        self.ensure_one()
        category = self.uom_id.category_id
        allowed = self.product_uom_ids.filtered(lambda uom: uom.category_id == category)
        # ``uom_ids`` is read through the ORM prefetch: one query for all the
        # lines of a document, instead of one search per line.
        return allowed or category.uom_ids
