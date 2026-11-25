# Product Allowed Units Filter (`cl_uom_filter`)

Choose the units each product may be handled in, and only those are offered on your documents. By [Code Legion](https://thecodelegion.com).

A product sold by the box and the pallet should not end up on an order in single units by mistake. Select the allowed units once on the product, and the unit drop-down on sales, purchase, inventory, manufacturing and invoice lines offers only those.

## What it does

- **Allowed Units on the product**: On the General Information tab, shared by all variants. Only units of the product's own unit category can be selected.
- **Sales and Purchase**: Sales order lines and purchase order lines offer only the allowed units.
- **Inventory**: The same on transfer lines.
- **Manufacturing**: The same on manufacturing orders and on their component and finished product lines.
- **Accounting**: The same on invoice and vendor bill lines.
- **Optional per product**: A product with no allowed units selected offers every unit of its unit category, as in standard Odoo.

## Behaves well

- Only the choice of units is narrowed. The unit Odoo proposes on a new line, its prices and its conversions are not changed, so include the product's own unit and its purchase unit in the allowed units.
- Existing documents are not touched: a line keeps the unit it already has.
- A selected unit of another category than the product's is ignored, so changing the unit of a product never leaves its lines without a choice.
- The field is hidden on services.
- Nothing else to configure and no new access rights.

## Technical

- `product_uom_ids` on `product.template` (relation `product_template_uom_rel`), shown as "Allowed Units"; `product.product._cl_get_allowed_uoms()` returns the units to offer.
- Computed `cl_allowed_uom_ids` on `sale.order.line`, `purchase.order.line`, `stock.move`, `mrp.production` and `account.move.line`, used as the domain of their unit field.
- The filter is a field domain applied by the screens, not a server-side constraint: an import or an API call can still set another unit of the product's category.
- Tests: `odoo -i cl_uom_filter --test-tags /cl_uom_filter`.
- Odoo 18.0 · depends on `product`, `uom`, `sale`, `purchase`, `stock`, `mrp`, `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
