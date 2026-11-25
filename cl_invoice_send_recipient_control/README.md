# Invoice Send Recipient Control (`cl_invoice_send_recipient_control`)

Send invoice emails only to the recipients you chose, not to the invoice's followers — by [Code Legion](https://thecodelegion.com).

## What it does

- A per-company setting, **Invoice Emails: Skip Followers**. When it is on, an invoice sent by email reaches only the recipients listed when sending: the **customer**, plus anyone **added in the Send window**. Followers of the invoice no longer get a copy automatically.
- A follower you add as a recipient on purpose still receives the email.
- If every recipient is removed in the Send window, nobody is emailed: followers do not get the invoice through the back door.

## Where it applies

- Everything that goes through Odoo's standard invoice sending: the **Send** window on one invoice, **Send** on several invoices (background batch), and automatic flows built on the same engine (online payment, subscriptions, Code Legion's *Auto-send Invoice on Delivery*).
- It does **not** change messages written in the chatter or emails sent by other means (a mail template run by an automation, for instance): those keep Odoo's normal follower rules.

## Behaves well

- The recipient list is **Odoo's own**, simply **filtered** to the chosen recipients — it does not re-implement core recipient logic, so other apps that extend invoice notifications keep working.

## Configuration

**Accounting ▸ Configuration ▸ Settings ▸ Customer Invoices ▸ Invoice Emails: Skip Followers**.

## Technical

- `res.company.cl_invoice_email_skip_followers` (exposed on `res.config.settings`).
- `account.move.send._send_mail` puts the chosen partner ids in the context (`cl_invoice_email_only_partner_ids`); `account.move._notify_get_recipients` filters super's result with that list.
- Tests: `odoo -i cl_invoice_send_recipient_control --test-tags /cl_invoice_send_recipient_control`.
- Odoo 18.0 · depends on `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
