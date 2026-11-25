# Product Compatibility (`cl_product_compatibility`)

Stop products that don't fit together — like a cup and the wrong-size lid — from being sold on one order. By [Code Legion](https://thecodelegion.com).

## What it does

- **Compatibility groups** (e.g. *Cups & Lids*): the products checked against each other.
- **Fits With** on each product (12oz Cup ↔ 12oz Lid): a link is stored once and read from both ends, so it always works in **both directions**. Editable on the product form (Sales tab, *Sold Together*) for single-variant products, and on each variant - including the short variant form opened from the *Variants* button.
- A **warning banner** on the quotation lists each mismatch and the compatible options.
- **Confirmation is blocked** on the server for users while a mismatch remains; a **Sales Manager** can confirm anyway, and the override is logged.
- Orders confirmed **by the system or for the customer** (online payment, online signature, scheduled actions) are never refused - a paid order must not stay unconfirmed - but a log note lists the mismatches.
- With eCommerce, the auto-installed companion **`cl_product_compatibility_website`** keeps the customer on the cart until it's fixed, shows why, and refuses payment.

**Rule:** two products on the order that share a group, are not compatible, and neither of which has a compatible partner elsewhere on the order are flagged. 12oz cups + 12oz lids + 16oz cups + 16oz lids passes; 12oz cups + 16oz lids is caught.

## Behaves well

- **Enforced on confirm**, not just a dismissible pop-up; the override is limited to Sales Managers. Website orders confirmed by hand in the back office are checked too.
- Compatible options suggested in the warning are limited to the order's company.
- Mismatches are reported **even when there's nothing to suggest**.
- The warning is **computed on demand** — editing a group never mass-recomputes old orders.
- **One module, one set of fields**.
- No dependency on Inventory, and **no custom form/checkout JavaScript**.

## Technical

- Model `cl.product.compatibility.group`; `cl_compatibility_group_ids` / `cl_compatible_product_ids` on products (the latter computed from the single link table `cl_product_compatible_rel`, read through `cl_compatible_out_ids` and `cl_compatible_in_ids`); `_cl_compatibility_mismatches()` and override on `sale.order`.
- Context key `cl_skip_compatibility` skips the check for one confirmation (integrations).
- Website companion overrides `WebsiteSale._check_cart()`, `sale.order._is_cart_ready()` / `_check_cart_is_ready_to_be_paid()` and adds a cart notice.
- Tests: `odoo -i cl_product_compatibility --test-tags /cl_product_compatibility`.
- Odoo 18.0 · depends on `sale_management` (companion: `website_sale`) · LGPL-3.

---
© Code Legion — https://thecodelegion.com
