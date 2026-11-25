# Product Packaging Measurements (`cl_product_packaging_measurements`)

Record the length, width, height and gross weight of product packagings and show them on sales order lines — by [Code Legion](https://thecodelegion.com).

## What it does

- **Length / Width / Height** and **Gross Weight** on every product packaging: in the packaging list (also the one inside the product form) and in the packaging form.
- **Units per company**: a dimension unit and a weight unit. By default every packaging uses them; optionally *each packaging can use its own dimension unit* and / or *its own weight unit*.
- A readable summary such as `120.00 x 80.00 x 100.00 cm` and `25.00 kg` on the packaging; a side that was not measured shows as a dash.
- Two optional columns on sales order lines: **Pkg. Dimensions** and **Pkg. Gross Weight**.

## Behaves well

- **Quotations follow, confirmed orders keep.** While an order is a quotation its lines show the packaging's current figures; once confirmed they stay as they were, even if the packaging is edited later.
- **Always in step with the line's packaging.** The figures are taken again whenever the packaging of the line changes — by the user, by Odoo when the quantity changes, by the website or by an import — also on a confirmed order.
- **Imposed units are really imposed.** When the company does not allow own units, a packaging cannot keep another unit, however it is created or edited; changing the company unit updates its packagings.
- Dimension units are limited to **length units** and weight units to **weight units**; negative figures are refused.
- Existing order lines are not recomputed when the module is installed.

## Configuration

**Inventory ▸ Configuration ▸ Settings ▸ Products**: turn on *Product Packagings* (standard Odoo), then set **Packaging Measurements** right below it: the two units and whether packagings may use their own.

Switching "own unit" off again brings every packaging of the company back to the company unit.

## Technical

- `product.packaging`: `cl_length`, `cl_width`, `cl_height`, `cl_length_uom_id`, `cl_gross_weight`, `cl_weight_uom_id`, computed `cl_dimensions` / `cl_gross_weight_label`.
- `res.company`: `cl_packaging_length_uom_id`, `cl_packaging_weight_uom_id`, `cl_packaging_length_uom_free`, `cl_packaging_weight_uom_free`.
- `sale.order.line`: stored computed `cl_packaging_dimensions` / `cl_packaging_weight`, depending on `product_packaging_id` only; `product.packaging.write()` schedules the recomputation for quotation lines.
- Tests: `odoo -i cl_product_packaging_measurements --test-tags /cl_product_packaging_measurements`.
- Odoo 18.0 · depends on `stock`, `sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
