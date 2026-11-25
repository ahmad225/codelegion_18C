# Low Stock Notifications (`cl_low_stock_notification`)

A daily e-mail of the products below their minimum stock, with the full list as an Excel file, plus a PDF / Excel report on demand — by [Code Legion](https://thecodelegion.com).

## What it does

- Every day, each company that turned the alerts on e-mails its recipients the products that are below their minimum stock. The e-mail shows the ten most urgent lines; the **complete list is attached as an Excel file**.
- The same list is available at any time in **Inventory ▸ Reporting ▸ Low Stock**: *Print PDF*, *Download Excel*, or *Send E-mail Now* (handy to check the configuration).
- Three ways to define the minimum (per company): **one minimum for all products**, **a minimum set on each product** (*Low Stock Below*, Inventory tab of the product), or **the minimum of the reordering rules**, checked at each rule's location.
- Compare the minimum with the quantity **on hand** or the **forecasted** quantity; count **all warehouses** or only selected **locations**.
- Each line shows: product, internal reference, category, first vendor, location, unit, on hand, free to use, incoming, outgoing, forecast, minimum and missing quantity.

## Behaves well

- **One scope for every figure** — on hand, free, incoming, outgoing and forecast are all measured on the same locations, so goods expected in another warehouse never hide a shortage.
- **Nothing is stored** — the list is computed when needed. Printing never rewrites data and no file piles up in the database or filestore.
- **A real attachment** — the Excel file travels with the e-mail; there is no download link that stops working.
- **Queued e-mails** — messages go through Odoo's mail queue instead of being sent inside the scheduled job, so a failure never sends half of them twice.
- **Only tracked goods** — services and goods not tracked in stock are never reported as "low".
- **No e-mail when nothing is low**, or when no recipient has an e-mail address.
- **Multi-company** — settings, recipients and e-mail are per company; a company only sees its own stock.
- **Inventory Administrators only** for the report and its settings; recipients can be any internal user.

## Configuration

1. **Inventory ▸ Configuration ▸ Settings ▸ Low Stock Alerts**: turn the alerts on, choose the recipients and the timezone, where the minimum comes from, which quantity is compared and (optionally) the locations.
2. With *Minimum set on each product*: fill **Low Stock Below** in the Inventory tab of the products (per variant when the product has several).
3. The time of the daily e-mail is the next execution time of the scheduled action **Low Stock Alerts: daily e-mail**.

## Technical

- Settings on `res.company` (`cl_low_stock_*`), `cl_low_stock_min_qty` on `product.product` / `product.template`.
- `res.company._cl_low_stock_rows()` computes the list; `_cl_low_stock_xlsx()` builds the sheet (xlsxwriter, shipped with Odoo); `_cl_low_stock_send()` queues the e-mail; cron entry `res.company._cron_cl_low_stock_notify()`.
- PDF: QWeb report `cl_low_stock_notification.report_low_stock` on `res.company`. Wizard: transient `cl.low.stock.report.wizard`. No other model.
- Tests: `odoo -i cl_low_stock_notification --test-tags /cl_low_stock_notification`.
- Odoo 18.0 · depends on `stock`, `mail` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
