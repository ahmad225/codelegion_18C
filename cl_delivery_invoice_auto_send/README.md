# Auto-send Invoice on Delivery (`cl_delivery_invoice_auto_send`)

Automatically send the customer invoice (with its PDF) once the delivery is validated — by [Code Legion](https://thecodelegion.com).

## What it does

- When an **outgoing delivery is validated**, the **posted** customer invoices of its sale order are sent to the customer automatically.
- When the invoice is posted **after** the goods have left (invoicing policy *delivered quantities*), it is sent as soon as it is **posted**.
- Sent through Odoo's standard **Send** queue (`account.move.send`), exactly as if you had selected the invoices and clicked *Send*: the **PDF is generated and attached**, the customer's preferred sending method and email template are used, and the invoice is marked as sent.
- Each invoice is sent **once**: invoices already sent by hand, by another automatic flow or by this app are left alone.

## Behaves well

- **Never blocks or slows down the warehouse.** Validating the delivery only puts the invoice in Odoo's background sending queue; the PDF and the email are produced by the standard scheduled action a moment later. An invoice that cannot be sent gets the standard error note in its chatter.
- **Works for warehouse users without accounting rights**: the automation runs with system rights, with the validating user as author.
- **Customer without an email address**: nothing is queued and a note on the invoice says why, instead of a silent skip.
- A note on the invoice names the delivery that triggered the sending.
- Deliveries are identified by the operation **type code** (outgoing), not by name — translating or renaming operation types won't break it. In multi-step shipping only the final delivery step counts.
- The setting is read from the **invoice's company**.

## Configuration

**Accounting ▸ Configuration ▸ Settings ▸ Customer Invoices ▸ Auto-send Invoice on Delivery** (per company).

The emails leave with the scheduled action *Send invoices automatically* (`account`), which this app triggers right away; it must be active, as it is by default.

## Good to know

- Only customer invoices (not credit notes) linked to a sale order are concerned.
- The customer's *Invoice sending* preference is respected: a customer set to another method than email (for example by post) gets the invoice that way.
- Dropshipping and returns do not trigger anything.
- If the sending fails in the background the invoice stays flagged as handled; send it again by hand after fixing the cause shown in its chatter.

## Technical

- `res.company.cl_send_invoices_when_delivered`; flag `cl_queued_on_delivery` on `account.move`.
- Triggers: `stock.picking._action_done` and `account.move._post`; both call `account.move._cl_queue_delivery_auto_send()`, which fills `sending_data` and triggers `account.ir_cron_account_move_send`.
- Tests: `odoo -i cl_delivery_invoice_auto_send --test-tags /cl_delivery_invoice_auto_send`.
- Odoo 18.0 · depends on `account`, `sale_stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
