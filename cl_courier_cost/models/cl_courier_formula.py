# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .cl_courier_engine import cl_evaluate, cl_referenced_codes


class ClCourierFormula(models.Model):
    _name = 'cl.courier.formula'
    _description = 'Courier Cost Formula'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    cl_expression = fields.Text(
        string='Expression', required=True,
        help="Variable codes with + - * / ( ), comparisons (> < >= <= == !=), and, or, not, "
             "and the functions min(a, b, ...), max(a, b, ...), round(x[, digits]), ceil(x), "
             "floor(x), iif(condition, value_if_true, value_if_false).")
    state = fields.Selection(
        [('draft', 'Draft'), ('validated', 'Validated')],
        string='Status', required=True, default='draft', copy=False, readonly=True,
        help="Only validated formulas are used to cost deliveries. Editing the expression "
             "puts the formula back to draft.")
    cl_validated_date = fields.Datetime(string='Validated On', copy=False, readonly=True)
    cl_variable_ids = fields.Many2many(
        'cl.courier.variable', 'cl_courier_formula_variable_rel', 'formula_id', 'variable_id',
        string='Variables Used', copy=False, readonly=True,
        help="Variables found when the formula was last validated, including those used by sub-formulas.")
    cl_carrier_ids = fields.One2many('delivery.carrier', 'cl_courier_formula_id', string='Delivery Methods')
    cl_description = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        formulas = super().create(vals_list)
        # e.g. an import with the Status column: validated means checked
        formulas.filtered(lambda f: f.state == 'validated')._cl_mark_validated()
        return formulas

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            self._cl_check_not_on_carrier(_('archived'))
        to_draft = self.browse()
        if 'cl_expression' in vals and 'state' not in vals:
            to_draft = self.filtered(lambda f: (f.cl_expression or '').strip() != (vals['cl_expression'] or '').strip())
        res = super().write(vals)
        if to_draft:
            super(ClCourierFormula, to_draft).write({'state': 'draft', 'cl_validated_date': False})
        if vals.get('state') == 'validated':
            # Whatever sets the status (button, import, API), the expression
            # is checked: a formula is never 'validated' without it.
            self._cl_mark_validated()
        return res

    def _cl_mark_validated(self):
        """Check each formula (raises UserError) and record when and with which variables."""
        for formula in self:
            variables = formula._cl_check()
            super(ClCourierFormula, formula).write({
                'cl_validated_date': fields.Datetime.now(),
                'cl_variable_ids': [(6, 0, variables.ids)],
            })

    @api.ondelete(at_uninstall=False)
    def _unlink_except_on_carrier(self):
        self._cl_check_not_on_carrier(_('deleted'))

    def _cl_check_not_on_carrier(self, action):
        carriers = self.env['delivery.carrier'].sudo().with_context(active_test=False).search(
            [('cl_courier_formula_id', 'in', self.ids)])
        if carriers:
            raise UserError(_(
                "This formula cannot be %(action)s while delivery methods use it: %(carriers)s.",
                action=action, carriers=', '.join(carriers.mapped('display_name'))))

    def action_cl_validate(self):
        self.write({'state': 'validated'})
        return True

    def action_cl_reset_draft(self):
        self.write({'state': 'draft', 'cl_validated_date': False})
        return True

    def _cl_check(self):
        """Raise UserError if the expression or a variable it uses is invalid."""
        self.ensure_one()
        try:
            codes = cl_referenced_codes(self.cl_expression)
            variables, _values = self.env['cl.courier.variable']._cl_resolve(codes, self.company_id)
        except UserError as exc:
            raise UserError(_("Formula %(name)s: %(error)s", name=self.name, error=exc.args[0])) from None
        return variables

    def _cl_compute(self, source_values):
        """Return (cost, {code: value}) for the given delivery values.

        Raises on any problem (invalid expression, unknown variable, division
        by zero, ...); callers decide how to report it.
        """
        self.ensure_one()
        codes = cl_referenced_codes(self.cl_expression)
        _variables, values = self.env['cl.courier.variable']._cl_resolve(
            codes, self.company_id, source_values=source_values)
        cost = cl_evaluate(self.cl_expression, {code: values[code] for code in codes})
        return cost, values
