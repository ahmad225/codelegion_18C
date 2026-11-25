# Allowed Pricelists per Customer (`cl_allowed_pricelist`)

Limit the pricelists a customer can be sold on — by [Code Legion](https://thecodelegion.com).

## What it does

- **Allowed Pricelists** on the customer form (*Sales & Purchase* tab, under the customer's own pricelist). The list is kept on the company, so it holds for all its contacts. Empty = any pricelist, as in standard Odoo.
- On a quotation for that customer the **Pricelist** field only offers the allowed ones, plus the pricelist set on the customer itself.
- A **new quotation starts on an allowed pricelist**: the customer's own one if there is one, otherwise the first of the list. This also applies when the quotation is created by an import or through the API, and when the customer of a draft quotation is changed.
- A **server-side check** refuses any other pricelist on a quotation, whatever the way it is written. The message names the pricelists that are allowed.
- Contacts filter **Restricted Pricelists** to find the customers that have a list.

## Good to know

- Only the pricelist somebody actually set on the customer counts as "its own". Odoo's automatic fallback (first pricelist of the country or company) is not added to the list.
- Pricelists of another company are ignored: a customer restricted in company A is not restricted in company B unless the list holds pricelists usable in B.
- **Not checked:** eCommerce orders (the website picks their pricelist), anything done by the system itself in superuser mode (connectors, scheduled jobs), confirmed and cancelled orders, and code that passes the context key `cl_skip_pricelist_check`.
- The field needs the *Pricelists* option of the Sales settings, like the customer's own pricelist.

## Technical

- `cl_order_pricelist_ids` on `res.partner`; on `sale.order`: `cl_pricelist_domain` (computed domain used by the form), an extension of `_compute_pricelist_id` and an `@api.constrains`.
- Tests: `odoo -i cl_allowed_pricelist --test-tags /cl_allowed_pricelist`.
- Odoo 18.0 · depends on `sale_management` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
