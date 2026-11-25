# Order Checklist (`cl_order_checklist`)

Things to check before a Sales Order is confirmed or a Manufacturing Order is marked as done — by [Code Legion](https://thecodelegion.com).

## What it does

- You list the **items to check** for Sales Orders and for Manufacturing Orders. An item belongs to one company or to all of them, and is either **required** or a simple reminder.
- Every order gets a **Checklist tab** with its own lines. Tick a line on the order: the line keeps **who ticked it and when**, and the tick (or untick) is logged in the chatter. A progress bar and the number of required items left are shown.
- A Sales Order can't be **confirmed**, and a Manufacturing Order can't be **marked as done**, until every required item is ticked. The error lists what is missing.
- An item added later is put on the orders that are **still open** (quotations, manufacturing orders not done). Archiving an item removes its unticked lines; ticked lines stay as a record.

## Behaves well

- **Automatic confirmations are never blocked.** eCommerce orders have no checklist at all. Orders confirmed in system mode (online payment, customer signature on the portal, subcontracting receipts, automations) go through, and a note on the order records the required items that were not ticked.
- **Checked on the server.** Ticking needs write access to the order; users can only tick and untick, the lines themselves are managed by the app.
- **Managers manage the items** — Sales Administrators and Manufacturing Administrators, not only the system administrator.
- **The manufacturing gate is "Mark as Done"** and says so: confirming, planning and producing are never held up.
- Orders that existed before the app was installed are covered: the required items are worked out from the item list, not from the lines an order happens to have.

## Configuration

- Sales items: **Sales ▸ Configuration ▸ Order Checklist**.
- Manufacturing items: **Manufacturing ▸ Configuration ▸ Order Checklist**.
- Code that must confirm without the check can pass the context key `cl_skip_checklist`.

## Good to know

- A duplicated order and a manufacturing backorder start with a fresh, unticked checklist.
- Lines can still be ticked or unticked after the order has passed its gate; every change is logged with the user.

## Technical

- Models: `cl.order.checklist.item` (the list), `cl.order.checklist.line` (one per item and order), and the abstract `cl.order.checklist.mixin` used by `sale.order` and `mrp.production`.
- Tests: `odoo -i cl_order_checklist --test-tags /cl_order_checklist`.
- Odoo 18.0 · depends on `sale`, `mrp`, `mail` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
