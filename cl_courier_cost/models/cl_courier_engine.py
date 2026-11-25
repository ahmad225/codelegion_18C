# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Expression checking and evaluation for courier cost formulas.

An expression is parsed with the standard ``ast`` module and every node is
checked against a short allow-list (numbers, variable names, + - * /,
comparisons, and/or/not and a few functions). Only then is it handed to
Odoo's ``safe_eval``, with nothing in scope but the functions below and the
values of the variables the expression actually names.
"""

import ast
import keyword
import math

from odoo import _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

MAX_EXPRESSION_LENGTH = 2000
# Nesting allowed in an expression (a + b + c + ... nests once per term).
# Python's parser, ast.unparse and the compiler all recurse once or more per
# level, so a very deep expression would end in a RecursionError.
MAX_EXPRESSION_DEPTH = 100

# name -> (minimum number of arguments, maximum or None)
FUNCTIONS = {
    'min': (2, None),
    'max': (2, None),
    'round': (1, 2),
    'ceil': (1, 1),
    'floor': (1, 1),
    'iif': (3, 3),
}

# Codes a variable may not use: the functions above and Python keywords
# (and, or, not, if, ...), which would make expressions ambiguous.
RESERVED_NAMES = frozenset(FUNCTIONS) | frozenset(keyword.kwlist)

_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div,
    ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)

_SYMBOLS = {
    ast.Pow: '**', ast.FloorDiv: '//', ast.Mod: '%', ast.Attribute: '.',
    ast.Subscript: '[ ]', ast.List: '[ ]', ast.Tuple: ',', ast.Dict: '{ }',
    ast.Lambda: 'lambda', ast.IfExp: 'if / else', ast.keyword: '=',
}


def _node_label(node):
    return _SYMBOLS.get(type(node), type(node).__name__)


def _check_depth(tree):
    """Refuse expressions nested deeper than MAX_EXPRESSION_DEPTH (no recursion here)."""
    stack = [(tree.body, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_EXPRESSION_DEPTH:
            raise UserError(_(
                "The expression is nested too deeply (more than %s levels). "
                "Split it with sub-formula variables.", MAX_EXPRESSION_DEPTH))
        stack.extend(
            (child, depth + 1) for child in ast.iter_child_nodes(node)
            if isinstance(child, ast.expr))


def cl_parse(expression):
    """Check ``expression`` and return ``(tree, codes)``.

    ``codes`` is the set of variable codes the expression refers to.
    Raises UserError with a readable message when the expression is invalid.
    """
    text = (expression or '').strip()
    if not text:
        raise UserError(_("The expression is empty."))
    if len(text) > MAX_EXPRESSION_LENGTH:
        raise UserError(_("The expression is too long (maximum %s characters).", MAX_EXPRESSION_LENGTH))
    try:
        tree = ast.parse(text, mode='eval')
    except SyntaxError as exc:
        raise UserError(_(
            "Syntax error in “%(expression)s” near character %(position)s.",
            expression=text, position=exc.offset or '?')) from None
    except (ValueError, RecursionError, MemoryError):
        # null characters, or nesting too deep for the Python parser
        raise UserError(_("The expression cannot be read: it is too complex or contains invalid characters.")) from None
    _check_depth(tree)

    function_names = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UserError(_("“%s” cannot be used in a formula.", _node_label(node)))
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise UserError(_("Only numbers can be written in a formula (found %s).", repr(node.value)))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise UserError(_(
                    "Unknown function. Available functions: %s.", ', '.join(sorted(FUNCTIONS))))
            if node.keywords:
                raise UserError(_("Function arguments cannot be named (%s).", node.func.id))
            low, high = FUNCTIONS[node.func.id]
            count = len(node.args)
            if count < low or (high is not None and count > high):
                if high is None:
                    expected = _("at least %s", low)
                elif low == high:
                    expected = str(low)
                else:
                    expected = _("%(low)s or %(high)s", low=low, high=high)
                raise UserError(_(
                    "%(function)s() takes %(expected)s argument(s), %(count)s given.",
                    function=node.func.id, expected=expected, count=count))
            function_names.add(id(node.func))

    codes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and id(node) not in function_names:
            if node.id in FUNCTIONS:
                raise UserError(_("%s is a function: write it with brackets, e.g. %s(...).", node.id, node.id))
            codes.add(node.id)
    return tree, codes


def cl_referenced_codes(expression):
    """Variable codes used by ``expression`` (raises UserError when invalid)."""
    return cl_parse(expression)[1]


def cl_referenced_codes_safe(expression):
    """Like ``cl_referenced_codes`` but returns an empty set for invalid input."""
    try:
        return cl_referenced_codes(expression)
    except UserError:
        return set()


class _IifToConditional(ast.NodeTransformer):
    """Turn iif(c, a, b) into (a if c else b) so only the chosen branch runs.

    This lets ``iif(weight > 0, total / weight, 0)`` work when weight is 0.
    """

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'iif':
            test, body, orelse = node.args
            return ast.copy_location(ast.IfExp(test=test, body=body, orelse=orelse), node)
        return node


def _round(value, digits=0):
    # digits may come from a variable (always a float here)
    return round(value, int(digits))


def cl_evaluate(expression, values):
    """Evaluate ``expression`` with ``values`` ({code: number}) and return a float.

    Only the codes the expression names are put in scope. Runtime problems
    (division by zero, ...) are raised as the original Python exception.
    """
    tree, codes = cl_parse(expression)
    missing = codes - set(values)
    if missing:
        raise UserError(_("No value for: %s.", ', '.join(sorted(missing))))
    tree = ast.fix_missing_locations(_IifToConditional().visit(tree))
    scope = {code: float(values[code]) for code in codes}
    scope.update({
        'min': min,
        'max': max,
        'round': _round,
        'ceil': math.ceil,
        'floor': math.floor,
    })
    result = safe_eval(ast.unparse(tree), scope)
    if isinstance(result, bool):
        result = float(result)
    if not isinstance(result, (int, float)) or not math.isfinite(result):
        raise ValueError(_("The formula did not give a finite number (%s).", result))
    return float(result)
