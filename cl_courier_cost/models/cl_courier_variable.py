# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .cl_courier_engine import (
    RESERVED_NAMES, cl_evaluate, cl_referenced_codes, cl_referenced_codes_safe)

CODE_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')

# Numeric values taken from the delivery order (or, for the sales order
# preview, estimated from the order lines). See
# stock.picking._cl_courier_source_values and sale.order._cl_courier_source_values.
SOURCE_SELECTION = [
    ('shipping_weight', 'Shipping weight'),
    ('weight', 'Total product weight'),
    ('volume', 'Total product volume'),
    ('packages', 'Number of packages'),
    ('lines', 'Number of product lines'),
    ('quantity', 'Total quantity (product units)'),
    ('untaxed', 'Order untaxed amount (without delivery)'),
]


class ClCourierVariable(models.Model):
    _name = 'cl.courier.variable'
    _description = 'Courier Cost Variable'
    _order = 'cl_code'

    name = fields.Char(string='Name', required=True)
    cl_code = fields.Char(
        string='Code', required=True,
        help="Name used in formulas: lowercase letters, digits and underscores, starting with a letter.")
    cl_type = fields.Selection(
        [('fixed', 'Fixed value'), ('field', 'Delivery value'), ('formula', 'Sub-formula')],
        string='Type', required=True, default='fixed')
    cl_fixed_value = fields.Float(string='Value', digits=(16, 4))
    cl_source = fields.Selection(SOURCE_SELECTION, string='Delivery Value')
    cl_expression = fields.Char(
        string='Sub-formula',
        help="Expression using other variable codes, e.g. kg * rate_per_kg.")
    cl_description = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    _sql_constraints = [
        ('cl_code_company_uniq', 'unique(cl_code, company_id)',
         'Another variable of this company already uses this code.'),
    ]

    @api.constrains('cl_code')
    def _check_cl_code(self):
        for variable in self:
            if not CODE_PATTERN.match(variable.cl_code or ''):
                raise ValidationError(_(
                    "The code “%s” must use lowercase letters, digits and underscores only, "
                    "and start with a letter.", variable.cl_code))
            if variable.cl_code in RESERVED_NAMES:
                raise ValidationError(_("“%s” is a reserved word and cannot be used as a code.", variable.cl_code))

    @api.constrains('cl_type', 'cl_source', 'cl_expression', 'cl_code', 'active')
    def _check_cl_definition(self):
        for variable in self:
            if variable.cl_type == 'field' and not variable.cl_source:
                raise ValidationError(_("Choose which delivery value the variable %s reads.", variable.cl_code))
            if variable.cl_type != 'formula':
                continue
            try:
                codes = cl_referenced_codes(variable.cl_expression)
                # Unknown codes are accepted here (they may be created later);
                # the formula's Validate button reports them. Cycles are not.
                self._cl_resolve(codes, variable.company_id, ignore_unknown=True, path=(variable.cl_code,))
            except UserError as exc:
                raise ValidationError(_("Variable %(code)s: %(error)s", code=variable.cl_code, error=exc.args[0])) from None

    def write(self, vals):
        if 'cl_code' in vals:
            self.filtered(lambda v: v.cl_code != vals['cl_code'])._cl_check_unused(_('renamed'))
        if 'active' in vals and not vals['active']:
            self.filtered('active')._cl_check_unused(_('archived'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        self._cl_check_unused(_('deleted'))

    def _cl_check_unused(self, action):
        """Refuse to rename, archive or delete a variable a formula still uses."""
        for variable in self:
            company_domain = [('company_id', '=', variable.company_id.id)]
            formulas = self.env['cl.courier.formula'].sudo().with_context(active_test=False).search(company_domain)
            users = [f.name for f in formulas if variable.cl_code in cl_referenced_codes_safe(f.cl_expression)]
            others = self.sudo().with_context(active_test=False).search(
                company_domain + [('cl_type', '=', 'formula'), ('id', '!=', variable.id)])
            users += [v.cl_code for v in others if variable.cl_code in cl_referenced_codes_safe(v.cl_expression)]
            if users:
                raise UserError(_(
                    "Variable %(code)s cannot be %(action)s: it is used by %(users)s.",
                    code=variable.cl_code, action=action, users=', '.join(users)))

    @api.model
    def _cl_resolve(self, codes, company, source_values=None, ignore_unknown=False, path=()):
        """Follow the variables named in ``codes`` and the sub-formulas they use.

        Only variables that are actually referenced are visited, so two
        unrelated sub-formula variables never see each other. A code met again
        on its own dependency chain is a circular reference.

        :param source_values: delivery values ({source: number}). When given,
            every visited variable is evaluated.
        :return: (variables visited, {code: value})
        """
        records = {}
        values = {}
        done = set()
        visited = []

        def fetch(code):
            if code not in records:
                records[code] = self.search(
                    [('company_id', '=', company.id), ('cl_code', '=', code)], limit=1)
            return records[code]

        def visit(code, chain):
            if code in chain:
                raise UserError(_("Circular reference between variables: %s.", ' → '.join(chain + (code,))))
            if code in done:
                return
            variable = fetch(code)
            if not variable:
                if ignore_unknown:
                    done.add(code)
                    return
                raise UserError(_("Unknown variable “%s”.", code))
            sub_codes = set()
            if variable.cl_type == 'formula':
                sub_codes = cl_referenced_codes(variable.cl_expression)
                for sub_code in sorted(sub_codes):
                    visit(sub_code, chain + (code,))
            if source_values is not None:
                values[code] = variable._cl_value(source_values, {c: values[c] for c in sub_codes})
            visited.append(variable.id)
            done.add(code)

        for code in sorted(codes):
            visit(code, tuple(path))
        return self.browse(visited), values

    def _cl_value(self, source_values, sub_values):
        self.ensure_one()
        if self.cl_type == 'fixed':
            return self.cl_fixed_value
        if self.cl_type == 'field':
            if source_values.get(self.cl_source) is None:
                raise UserError(_("The delivery value of variable %s is not available.", self.cl_code))
            return float(source_values[self.cl_source])
        return cl_evaluate(self.cl_expression, sub_values)
