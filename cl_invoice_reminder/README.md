# Invoice Payment Reminders (`cl_invoice_reminder`)

Automatic email reminders for overdue customer invoices, stage by stage — by [Code Legion](https://thecodelegion.com).

## What it does

- **Reminder stages** per company: a name, a number of days after the due date and an email template (e.g. *Friendly reminder* after 7 days, *Second reminder* after 15, *Final notice* after 30).
- A **daily job** finds posted customer invoices that are not fully paid and emails each customer the reminder that is due.
- **One email per customer**: all the invoices of a customer that reached the same stage are listed in a single email.
- **Reminders Sent**: every reminder is recorded with the invoice, stage, address it went to, days overdue and amount due at the time. The *Reminders* button on an invoice opens its own reminders.
- **Overdue Invoices** work list with days overdue, amount due, stage reached and last reminder date.
- **Multi-company**: each company has its own schedule, sender address and batch size; one job serves them all.

## Set-up

1. **Accounting ▸ Configuration ▸ Invoicing ▸ Reminder Stages** (accounting managers): create the stages. Nothing is sent while a company has no stage.
2. Optional — **Accounting ▸ Configuration ▸ Settings ▸ Invoice Reminders**: number of customers emailed per run.
3. Daily use — **Accounting ▸ Customers ▸ Overdue Invoices** and **Reminders Sent**.

The job is the scheduled action *Invoice reminders: email customers about overdue invoices* (daily).

## How reminders are chosen

- The schedule is walked from its last stage to its first. An invoice gets each stage **once**, and **never a stage earlier than one it already received**. An invoice that is already 40 days overdue when you switch reminders on gets the 30-day reminder once — not the 7, 15 and 30-day reminders in a row.
- An archived stage stays in the history of the invoices that received it; re-creating it does not send it a second time.
- The email goes to the **invoice contact**; if that contact has no email (typically a plain invoice address), to the **company it belongs to**.
- A customer with **no email address** is not recorded as reminded. The invoice shows up under the *No Email Address* filter of Overdue Invoices and is reminded by the next run once an address is filled in.
- Customers are processed **one by one**. If the email of one customer cannot be prepared, the error goes to the server log and the others still get theirs.
- Each company emails at most its batch size per run; when customers are left over the job reports it and Odoo runs it again straight away.

## Email template

*Overdue invoices: reminder to the customer* is written for a contact (`res.partner`). Inside a template you can use:

- `ctx.get('cl_invoices')` — the overdue invoices of this email,
- `ctx.get('cl_stage')` — the reminder stage,
- `ctx.get('cl_company')` — the company sending the reminder.

The template and the scheduled action are loaded once (`noupdate`): your changes survive upgrades.

## Technical

- Models: `cl.invoice.reminder.stage` (schedule), `cl.invoice.reminder.log` (reminders sent). The reminder status of an invoice (`cl_reminder_stage_id`, `cl_reminder_date`, `cl_reminder_count`) is derived from its log lines only.
- `cl_days_overdue` on `account.move` is computed and searchable; the search agrees with the displayed value for every operator.
- Job: `account.move._cron_cl_send_invoice_reminders()`. It commits after each customer (never inside tests) and reports progress with `ir.cron._notify_progress`.
- Access: reminder stages are managed by accounting managers; billing and read-only accounting users can read stages and reminders sent.
- Tests: `odoo -i cl_invoice_reminder --test-tags /cl_invoice_reminder`.
- Odoo 18.0 · depends on `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
