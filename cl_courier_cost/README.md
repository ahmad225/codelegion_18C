# Courier Cost Control (`cl_courier_cost`)

Work out the expected courier cost of every delivery and check it against what the courier bills. By [Code Legion](https://thecodelegion.com).

Build a cost formula per delivery method from weight, volume, packages and fixed rates. Each validated delivery gets a cost log with the expected cost and its share of what the customer paid for shipping. Send the vendor sheet to your courier, import their actual charges, and compare.

## What it does

- **Cost formulas**: Variables and formulas with + - * /, min, max, round, ceil, floor and iif, checked before use.
- **Log per delivery**: Expected cost, variable values and the customer charge recorded when the delivery is validated.
- **Vendor sheet**: Export an Excel sheet for your courier and import their actual costs back.
- **Variance report**: Expected against actual, margin per delivery, by carrier and month.

## Behaves well

- A formula problem never blocks a delivery: the log records the error and the delivery is validated.
- Blank rows in the vendor sheet are skipped, never saved as zero or locked. Typed amounts are read in both notations (1,234.50 and 1.234,50); anything else is reported, not imported.
- A formula only becomes "Validated" through the check, also when the status is set by import or API.
- Managers can recompute many unbilled logs at once from the list's Action menu, for example after fixing a formula.
- Variance and margin are shown only once the courier's cost is known, so totals never count unbilled deliveries as profit.
- The customer's shipping charge is split across deliveries, so split orders are counted once.

## Technical

- Models `cl.courier.variable`, `cl.courier.formula`, `cl.courier.cost`; wizard `cl.courier.cost.exchange`.
- Formula on `delivery.carrier`; hook on `stock.picking._action_done()`; expressions checked with an allow-list and evaluated with `safe_eval`.
- Tests: `odoo -i cl_courier_cost --test-tags /cl_courier_cost`.
- Odoo 18.0 · depends on `stock_delivery`, `sale_stock`, `base_import` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
