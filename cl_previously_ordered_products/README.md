# Previously Ordered Products (`cl_previously_ordered_products`)

A page in the customer's account that lists what they bought before, ready to be ordered again — by [Code Legion](https://thecodelegion.com).

## What it does

- Adds a **Previously Ordered** page to the website customer portal (`/my/previously-ordered`), with a card on the portal home page and a breadcrumb.
- Lists the products of the customer's latest confirmed orders, most recent first: image, name (linked to the product page), reference, variant, date and quantity of the last order, and how many times it was ordered.
- Each product has a **quantity** and its own **add to cart** button. **Add all to cart** puts the whole list in the cart with the quantities shown on the page.
- **Search** by product name or reference.

## Behaves well

- **B2B aware** — orders of the whole company are included (commercial partner), so users see colleagues' orders, not only their own contact's.
- **Standard cart, no custom JavaScript** — products are added through Odoo's own cart method, so prices, taxes, stock rules ("continue selling", limits) and promotions apply exactly as in the shop.
- **Only what can be bought again** — products still published and for sale on this website. Shipping lines, down payments and loyalty rewards are not listed. Orders of another company are ignored.
- **Right unit** — the shop sells in the product's own unit, so a past order of 2 Dozens is offered as 24 Units. Quantities are whole numbers, as in the shop.
- **Safe form** — only products of the customer's own history can be added from the page, quantities must be positive, and a product that is no longer sold is skipped with a message instead of an error.
- The home card's counter is only computed when the portal home asks for it.

## Configuration

**Website ▸ Configuration ▸ Settings ▸ Shop - Checkout Process ▸ Previously Ordered Page**, for the website selected at the top of the settings:

- **Look at the last N confirmed orders** (default 20; 0 leaves the page empty).
- **Add All to Cart Button** (on by default).

The home card can be switched off in the website editor (*Customize*), like the other portal cards. It only shows when the customer has something to reorder.

## Technical

- Options on `website` (`cl_reorder_orders_scanned`, `cl_reorder_add_all`), related on the settings.
- `sale.order._cl_reorder_history(partner, website, limit=None)` builds the list.
- Routes: `GET /my/previously-ordered`, `POST /my/previously-ordered/add` (one form: `qty_<product id>` fields, `only=<product id>` for a single row).
- Tests: `odoo -i cl_previously_ordered_products --test-tags /cl_previously_ordered_products`.
- Odoo 18.0 · depends on `website_sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
