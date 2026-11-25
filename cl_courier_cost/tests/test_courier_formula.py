# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.cl_courier_cost.models.cl_courier_engine import (
    MAX_EXPRESSION_DEPTH, cl_evaluate, cl_parse)

from .common import ClCourierCostCommon


@tagged('post_install', '-at_install')
class TestCourierFormula(ClCourierCostCommon):

    def _sub_formula(self, code, expression):
        return self.env['cl.courier.variable'].create({
            'name': code, 'cl_code': code, 'cl_type': 'formula', 'cl_expression': expression})

    def test_validated_formula_computes(self):
        self.assertEqual(self.formula.state, 'validated')
        self.assertEqual(set(self.formula.cl_variable_ids.mapped('cl_code')), {'kg', 'rate', 'fee'})
        cost, values = self.formula._cl_compute({'shipping_weight': 4.0})
        self.assertAlmostEqual(cost, 30.0)
        self.assertEqual(values['kg'], 4.0)

    def test_unknown_variable_is_rejected(self):
        formula = self._create_formula('Unknown', 'kg * not_a_variable', validate=False)
        with self.assertRaisesRegex(UserError, 'not_a_variable'):
            formula.action_cl_validate()
        self.assertEqual(formula.state, 'draft')

    def test_syntax_errors_are_rejected(self):
        for expression in ('(kg * rate', 'kg ** 2', 'kg.real', "__import__('os')", 'sum(kg, fee)',
                           'min(kg)', 'round', 'kg if fee else rate', "kg + 'a'"):
            formula = self._create_formula('Bad', expression, validate=False)
            with self.assertRaises(UserError, msg=expression):
                formula.action_cl_validate()
            self.assertEqual(formula.state, 'draft')

    def test_variable_code_rules(self):
        with self.assertRaises(ValidationError):
            self.env['cl.courier.variable'].create({'name': 'Bad', 'cl_code': 'Rate Kg', 'cl_fixed_value': 1})
        with self.assertRaises(ValidationError):
            self.env['cl.courier.variable'].create({'name': 'Reserved', 'cl_code': 'max', 'cl_fixed_value': 1})

    def test_cycle_between_sub_formulas(self):
        self._sub_formula('cycle_a', 'cycle_b + 1')
        with self.assertRaisesRegex(ValidationError, 'Circular'):
            self._sub_formula('cycle_b', 'cycle_a * 2')
        with self.assertRaisesRegex(ValidationError, 'Circular'):
            self._sub_formula('cycle_self', 'cycle_self + 1')

    def test_unrelated_sub_formulas_are_not_a_cycle(self):
        self._sub_formula('double_rate', 'rate * 2')
        self._sub_formula('fee_plus_one', 'fee + 1')
        # shared dependency (diamond): both branches use double_rate
        self._sub_formula('combined', 'double_rate + fee_plus_one')
        formula = self._create_formula('Subs', 'double_rate + fee_plus_one + combined')
        self.assertEqual(formula.state, 'validated')
        cost, _values = formula._cl_compute({'shipping_weight': 0.0})
        self.assertAlmostEqual(cost, 42.0)

    def test_iif_only_runs_the_chosen_branch(self):
        formula = self._create_formula('Safe', 'iif(kg > 0, fee / kg, 0)')
        self.assertAlmostEqual(formula._cl_compute({'shipping_weight': 0.0})[0], 0.0)
        self.assertAlmostEqual(formula._cl_compute({'shipping_weight': 2.0})[0], 5.0)
        formula = self._create_formula('Funcs', 'max(ceil(kg) * rate, 25) + round(floor(fee / 3), 0)')
        self.assertAlmostEqual(formula._cl_compute({'shipping_weight': 1.2})[0], 28.0)

    def test_editing_expression_resets_to_draft(self):
        formula = self._create_formula('Editable', 'kg * rate')
        formula.cl_description = 'Notes do not reset it'
        self.assertEqual(formula.state, 'validated')
        formula.cl_expression = 'kg * rate + fee'
        self.assertEqual(formula.state, 'draft')

    def test_formula_on_carrier_cannot_be_archived_or_deleted(self):
        with self.assertRaises(UserError):
            self.formula.write({'active': False})
        with self.assertRaises(UserError):
            self.formula.action_archive()
        with self.assertRaises(UserError):
            self.formula.unlink()
        self.assertTrue(self.formula.active)

    def test_used_variable_cannot_be_renamed_or_archived(self):
        with self.assertRaises(UserError):
            self.var_rate.cl_code = 'rate_kg'
        with self.assertRaises(UserError):
            self.var_rate.action_archive()
        self.var_rate.cl_fixed_value = 6.0  # changing the value is fine

    def test_status_cannot_be_set_without_the_check(self):
        """Status written directly (import, API) goes through the same check as the button."""
        formula = self._create_formula('Direct', 'kg * not_a_variable', validate=False)
        with self.assertRaisesRegex(UserError, 'not_a_variable'):
            formula.write({'state': 'validated'})
        self.assertEqual(formula.state, 'draft')
        with self.assertRaises(UserError):
            formula.write({'cl_expression': "__import__('os')", 'state': 'validated'})
        with self.assertRaises(UserError):
            self.env['cl.courier.formula'].create({
                'name': 'Imported', 'cl_expression': 'kg ** 2', 'state': 'validated'})
        # a correct one is validated and stamped like with the button
        formula.write({'cl_expression': 'kg * rate', 'state': 'validated'})
        self.assertEqual(formula.state, 'validated')
        self.assertTrue(formula.cl_validated_date)
        self.assertEqual(set(formula.cl_variable_ids.mapped('cl_code')), {'kg', 'rate'})
        created = self.env['cl.courier.formula'].create({
            'name': 'Imported', 'cl_expression': 'fee', 'state': 'validated'})
        self.assertEqual(created.cl_variable_ids, self.var_fee)

    def test_engine_refuses_everything_but_arithmetic(self):
        for expression in (
                "kg.__class__", "kg[0]", "(lambda: 1)()", "[x for x in (1,)]", "min(*kg)",
                "min(1, key=2)", "kg // 2", "kg % 2", "1j", "None", "True", "f'{kg}'",
                "min(1, 2)(3)", "kg in kg", "kg is kg", "(1, 2)", "eval('1')", "getattr(kg, 'x')",
                "open('x')", "kg; fee", "~kg", "kg << 2", "kg | 1", "kg := 3", "",
                # too deep for the Python compiler: refused with a message, not a crash
                "-" * 1990 + "1", "1" + "+1" * (MAX_EXPRESSION_DEPTH + 50), "not " * 400 + "1",
                "(" * 300 + "1" + ")" * 300):
            with self.assertRaises(UserError, msg=expression[:40]):
                cl_parse(expression)
        # a long but reasonable sum is fine
        self.assertAlmostEqual(cl_evaluate("1" + "+1" * 60, {}), 61.0)
        # results that are not a finite number are errors, never stored
        for expression in ("1e308 * 10", "ceil(1e308 * 10)", "fee / (kg - kg)"):
            with self.assertRaises(Exception, msg=expression):
                cl_evaluate(expression, {'kg': 1.0, 'fee': 1.0})
