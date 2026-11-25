# Incoming Purchases on Product (`cl_product_purchase_lines`)

See the open purchase order lines still to be received, directly on the product form — by [Code Legion](https://thecodelegion.com).

## What it does

- An **Incoming** smart button and an **Incoming Purchases** tab on the product template and variant.
- Lists every confirmed purchase order line that still has an **open receipt**: order, vendor, expected arrival, ordered / received / remaining quantity and receipt progress (*Nothing Received* / *Partly Received*), sorted by expected arrival.
- Works for all goods, storable or not; a product bought as a **kit** is listed while its components are still expected. Services have no receipt and never show the tab.
- **Open Order** button on each line (Purchase users).

## Who sees it

- **Purchase users** and **Inventory users**. Inventory users can already read purchase order lines in standard Odoo (through `purchase_stock`), so the module grants **no extra access**; nobody else can read the two fields.
- The price columns and the **Open Order** button are shown to Purchase users only. Rows do not open the purchase order line form.

## Behaves well

- **Outstanding = an open incoming receipt still exists.** Cancelled receipts and lines closed without a backorder drop off by themselves — no per-user "dismiss" table needed. Dropship orders are not listed: those goods never arrive in your warehouse.
- No viewer tick-box on the user form and no extra group: nothing to save in *My Preferences*, no hidden read access to every purchase order.
- All products on screen are resolved with **one query** on the open receipt moves; columns are standard optional columns instead of a dozen company settings.

## Technical

- `purchase.order.line._cl_outstanding_by_product()`, computed `cl_qty_to_receive` / `cl_receipt_progress` on the line; computed `cl_incoming_po_line_ids` / `cl_incoming_po_line_count` on `product.product` and `product.template` (restricted to `purchase.group_purchase_user` and `stock.group_stock_user`).
- Tests: `odoo -i cl_product_purchase_lines --test-tags /cl_product_purchase_lines`.
- Odoo 18.0 · depends on `purchase_stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
