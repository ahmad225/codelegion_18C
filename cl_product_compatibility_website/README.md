# Product Compatibility – eCommerce (`cl_product_compatibility_website`)

Companion of [`cl_product_compatibility`](../cl_product_compatibility) for the online shop — by [Code Legion](https://thecodelegion.com). Installed automatically when both Product Compatibility and eCommerce are installed.

- Checkout, address and payment steps send the customer back to the **cart** while it holds incompatible products, and the **Checkout button is disabled**.
- The cart lists each mismatch and the compatible options (**published products only**). The notice is part of the cart lines, so it appears and disappears as the customer changes the cart, without reloading the page.
- **Payment is refused on the server** for such a cart, express checkout included.
- Done through Odoo's standard hooks (`WebsiteSale._check_cart()`, `sale.order._is_cart_ready()` and `_check_cart_is_ready_to_be_paid()`) - **no custom checkout JavaScript**.
- Tests: `odoo -i cl_product_compatibility_website --test-tags /cl_product_compatibility_website`.

Odoo 18.0 · depends on `cl_product_compatibility`, `website_sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
