# Last Purchase Price (`cl_last_po_price`)

Fills a purchase order line's price from the product's last confirmed purchase order — by [Code Legion](https://thecodelegion.com).

## What it does

- When a product is added to a purchase order, its unit price and discount are filled from the **last confirmed PO** for that product.
- Per-company options: on/off, last price taken from **the same vendor only** or **any vendor**, applied to **all products** or **products with variants only**.

## Behaves well

- Only **draft / sent** RFQs are filled; confirmed or already-billed lines are never overwritten.
- The "last" order is the one **confirmed** most recently (not the one created most recently).
- A price **typed by the user** on a saved line is kept when only the quantity changes, in the same cases standard Odoo keeps it (no vendor price list for that vendor). Changing the product, the unit of measure or the vendor fetches the last price again.
- A price given explicitly when the line is created (import, API) is never replaced.
- The last price is **converted** to the order's currency and unit of measure, and rounded like standard purchase prices.
- The last order's **discount** is carried over with the price, also on lines created without a price by an import, the API or the product catalog.
- The last lines of all products on the order are fetched in **one query** per company (no per-line searches, no redundant vendor onchange, no loading of the whole purchase history).

## Good to know

- When a product has a last purchase price, it wins over the vendor price list, including quantity price breaks.
- Lines created by reordering rules keep the price Odoo computed from the vendor price list: Odoo passes that price explicitly.

## Configuration

**Purchase ▸ Configuration ▸ Settings ▸ Last Purchase Price** (managers).

## Technical

- Extends `purchase.order.line._compute_price_unit_and_date_planned_and_name` and `create`; settings `cl_last_po_price`, `cl_last_po_price_vendor`, `cl_last_po_price_products` on `res.company`.
- Tests: `odoo -i cl_last_po_price --test-tags /cl_last_po_price`.
- Odoo 18.0 · depends on `purchase` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
