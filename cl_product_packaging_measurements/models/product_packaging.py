# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models
from odoo.tools.misc import formatLang

from .res_company import length_uom_domain, weight_uom_domain

# Changing any of these changes what a quotation line shows for the packaging.
MEASUREMENT_FIELDS = frozenset({
    'cl_length', 'cl_width', 'cl_height', 'cl_length_uom_id',
    'cl_gross_weight', 'cl_weight_uom_id',
})


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    cl_length = fields.Float(string='Length', digits=(16, 2))
    cl_width = fields.Float(string='Width', digits=(16, 2))
    cl_height = fields.Float(string='Height', digits=(16, 2))
    cl_length_uom_id = fields.Many2one(
        'uom.uom', string='Dimension Unit', ondelete='restrict',
        domain=length_uom_domain,
        default=lambda self: self.env.company.cl_packaging_length_uom_id,
        help="Unit of the length, width and height. It follows the company "
             "setting unless packagings are allowed their own unit.")
    cl_gross_weight = fields.Float(
        string='Gross Weight', digits='Stock Weight',
        help="Weight of one full packaging, contents included.")
    cl_weight_uom_id = fields.Many2one(
        'uom.uom', string='Weight Unit', ondelete='restrict',
        domain=weight_uom_domain,
        default=lambda self: self.env.company.cl_packaging_weight_uom_id,
        help="Unit of the gross weight. It follows the company setting unless "
             "packagings are allowed their own unit.")

    # The views lock the unit columns when the company imposes one unit.
    cl_length_uom_locked = fields.Boolean(compute='_compute_cl_units_locked')
    cl_weight_uom_locked = fields.Boolean(compute='_compute_cl_units_locked')

    cl_dimensions = fields.Char(
        string='Dimensions', compute='_compute_cl_measurement_labels',
        help="Length x width x height, with the unit.")
    cl_gross_weight_label = fields.Char(
        string='Gross Weight (text)', compute='_compute_cl_measurement_labels')

    _sql_constraints = [
        ('cl_measurements_not_negative',
         'CHECK(cl_length >= 0 AND cl_width >= 0 AND cl_height >= 0 AND cl_gross_weight >= 0)',
         "The dimensions and the gross weight of a packaging cannot be negative."),
    ]

    # ------------------------------------------------------------------
    # Units
    # ------------------------------------------------------------------

    def _cl_measurement_company(self):
        """Company whose packaging settings apply to this packaging."""
        self.ensure_one()
        return self.company_id or self.product_id.company_id or self.env.company

    @api.depends('company_id', 'product_id.company_id')
    @api.depends_context('company')
    def _compute_cl_units_locked(self):
        for packaging in self:
            company = packaging._cl_measurement_company()
            packaging.cl_length_uom_locked = not company.cl_packaging_length_uom_free
            packaging.cl_weight_uom_locked = not company.cl_packaging_weight_uom_free

    def _cl_align_units(self, company=None):
        """Give the packagings the unit of their company wherever that company
        imposes one unit for all packagings (or when they have no unit yet).

        :param company: force the company to follow instead of the packaging's
        """
        for packaging in self:
            settings = company or packaging._cl_measurement_company()
            changes = {}
            for unit_field, company_field, free_field in (
                ('cl_length_uom_id', 'cl_packaging_length_uom_id', 'cl_packaging_length_uom_free'),
                ('cl_weight_uom_id', 'cl_packaging_weight_uom_id', 'cl_packaging_weight_uom_free'),
            ):
                imposed = settings[company_field]
                if not imposed or packaging[unit_field] == imposed:
                    continue
                if not settings[free_field] or not packaging[unit_field]:
                    changes[unit_field] = imposed.id
            if changes:
                packaging.with_context(cl_units_aligned=True).write(changes)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    @api.depends('cl_length', 'cl_width', 'cl_height', 'cl_length_uom_id',
                 'cl_gross_weight', 'cl_weight_uom_id')
    def _compute_cl_measurement_labels(self):
        for packaging in self:
            sides = (packaging.cl_length, packaging.cl_width, packaging.cl_height)
            if any(sides):
                # A side that was not measured is shown as a dash.
                size = " x ".join(
                    formatLang(self.env, side, digits=2) if side else "-" for side in sides)
                packaging.cl_dimensions = ("%s %s" % (
                    size, packaging.cl_length_uom_id.name or '')).strip()
            else:
                packaging.cl_dimensions = False
            if packaging.cl_gross_weight:
                packaging.cl_gross_weight_label = ("%s %s" % (
                    formatLang(self.env, packaging.cl_gross_weight, digits=2),
                    packaging.cl_weight_uom_id.name or '')).strip()
            else:
                packaging.cl_gross_weight_label = False

    # ------------------------------------------------------------------
    # Keeping units and quotations in step
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        packagings = super().create(vals_list)
        packagings._cl_align_units()
        return packagings

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('cl_units_aligned') and vals.keys() & {
                'company_id', 'product_id', 'cl_length_uom_id', 'cl_weight_uom_id'}:
            self._cl_align_units()
        if vals.keys() & MEASUREMENT_FIELDS:
            self._cl_refresh_quotation_lines()
        return result

    def _cl_refresh_quotation_lines(self):
        """Quotations show the current measurements of their packaging; orders
        that are already confirmed keep what they showed when the packaging was
        put on the line."""
        lines = self.env['sale.order.line'].sudo().search([
            ('product_packaging_id', 'in', self.ids),
            ('state', 'in', ('draft', 'sent')),
        ])
        if lines:
            for name in ('cl_packaging_dimensions', 'cl_packaging_weight'):
                self.env.add_to_compute(lines._fields[name], lines)
