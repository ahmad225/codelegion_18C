# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Courier Cost Control',
    'summary': 'Estimate what each delivery should cost you from a formula per '
               'delivery method, then reconcile it with what the courier billed.',
    'description': """
Courier Cost Control
====================
Know what every shipment costs you, not only what the customer paid for it.

* Variables: fixed rates (per kg, fuel fee, minimum charge), values taken from
  the delivery (shipping weight, product weight, volume, packages, product
  lines, quantity, order untaxed amount) or a sub-formula built from other
  variables.
* Formulas: type the expression with variable codes, + - * / ( ), comparisons
  and the functions min, max, round, ceil, floor and iif(condition, a, b).
  "Validate" checks syntax and unknown or circular variables. Only validated
  formulas are used; editing a formula puts it back to draft.
* Attach a formula to a delivery method. When a delivery order with that
  method is validated, a cost log records the expected courier cost, the
  values used, and the customer delivery charge shared out over the order's
  deliveries.
* The sales order shows the expected courier cost next to the shipping
  buttons, using units of measure correctly.
* Vendor sheet: export the deliveries of a period or carrier to Excel, let the
  courier fill in the "Actual Cost" column, import it back. Filled rows are
  updated and locked; blank rows are left alone.
* Courier Cost users can also type the actual cost in the list and lock it.
* Cost log list, pivot and graph by carrier and month, with filters for
  deliveries without a bill yet, billed above estimate, errors and locked rows.
* Managers can recompute one unbilled log, or many at once from the list's
  Action menu (for example after fixing a formula).

Behaves well:

* A formula problem (division by zero, missing variable, draft formula) never
  blocks a delivery: the log is saved in "Error" with the reason and a note is
  posted on the delivery.
* Sub-formulas resolve only the variables they actually use, with a real
  circular-reference check.
* Variance and margin are computed only once an actual cost is entered, so a
  delivery that has not been billed yet never shows as pure profit.
* The customer charge of an order is counted once, shared over its
  deliveries by shipping weight (equal split when nothing has a weight), and
  converted to the company currency.
* Changing the carrier of a done delivery never deletes a log that has an
  actual cost; it only recomputes unbilled estimates and leaves a note.
* A blank cell in the imported sheet is skipped, never read as zero. Amounts
  typed as text are read in both notations (1,234.50 and 1.234,50); anything
  that is not a plain positive amount is reported, not imported.
* Formulas are evaluated with Odoo's safe_eval on a checked expression; no
  Python code can be typed in. A formula only becomes "Validated" through
  the check, also when the status is set by import or API.
  Multi-company record rules on all data.
* Works for warehouse users without an email address: notes on the delivery
  are logged, nobody is notified.
* No accounting entries, no customer price changes, no extra Python library
  (Excel files are read with Odoo's own import engine).
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Inventory/Delivery',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['stock_delivery', 'sale_stock', 'base_import'],
    'data': [
        'security/cl_courier_cost_security.xml',
        'security/ir.model.access.csv',
        'views/cl_courier_variable_views.xml',
        'views/cl_courier_formula_views.xml',
        'views/cl_courier_cost_views.xml',
        'views/delivery_carrier_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
        'wizard/cl_courier_cost_exchange_views.xml',
        'views/cl_courier_cost_menus.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
