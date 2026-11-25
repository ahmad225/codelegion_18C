# Manufacturing Order Description (`cl_mrp_order_description`)

A description on every manufacturing order, printed for the shop floor. By [Code Legion](https://thecodelegion.com).

Add free-text instructions to a manufacturing order and they print on the production order PDF, right under the product.

## What it does

- **Description field**: A Description field on the manufacturing order, just below the bill of materials.
- **Printed on the order**: The production order PDF prints the description under the product.
- **Copied with the order**: Duplicating a manufacturing order keeps its description, and so does a backorder.
- **Searchable**: Find manufacturing orders by a word of their description.
- **Shop floor note**: With Enterprise shop floor installed, its note prints too. Without it, nothing breaks.

## Behaves well

- Plain text, kept on the order itself: no extra models, no extra tables.
- Works on Community and Enterprise; the shop floor note is read only if that app is installed.
- Extends Odoo's own production order report instead of replacing it.

## Technical

- Field `cl_mo_description` on `mrp.production`; computed `cl_shop_floor_note` (plain text of the Shop Floor `log_note`, whether that field is text or HTML).
- Inherits report template `mrp.report_mrporder`.
- Tests: `odoo -i cl_mrp_order_description --test-tags /cl_mrp_order_description`.
- Odoo 18.0 · depends on `mrp` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
