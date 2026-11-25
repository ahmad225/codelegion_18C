# Customer Statements (`cl_customer_statement`)

Customer account statements and overdue statements — PDF, email, customer portal and monthly automatic sending. By [Code Legion](https://thecodelegion.com).

Built on Odoo's own receivable journal items.

## What it does

- **Account statement** for any period: opening balance; every invoice, credit note, payment and adjustment with debit, credit and running balance; closing balance.
- **Overdue statement**: open items past their due date, with days overdue.
- **Ageing** (not due / 1–30 / 31–60 / 61–90 / over 90 days) **by due date**, in **company currency**.
- **Print or email** for one or many customers (Contacts ▸ Action ▸ *Customer Statements*, or the *Statement* button on a customer). The **PDF is attached** to the email.
- **Statement Recipients** per customer (e.g. their accounts payable contact); otherwise the customer's own email.
- **Customer portal**: *My Account ▸ Account Statement* with a date filter and PDF downloads.
- **Monthly automatic sending** of last month's statement per company (Accounting settings), with a **Statements Sent** log.

## Behaves well

- **Nothing stored per customer** — every statement is computed from the ledger when requested, so it's never stale and opening contact screens never triggers recalculation.
- **No public files** — PDFs are private attachments on the customer; the portal streams them only to the logged-in customer.
- Portal customers **only ever see their own** statement (no portal access to statement tables).
- **All receivable entries** are listed (misc debits included), so one period's closing equals the next period's opening.
- Statements, and the emails that carry them, are worded in **each customer's language**.
- Automatic sending is **per company** and **idempotent** (one statement per customer per period). Customers are processed and **saved one by one**: a run that is interrupted carries on where it stopped, and when more than a batch is waiting the job tells the scheduler and is run again straight away. The cron is never reactivated by an upgrade.
- A customer without an email is **logged as "Not Sent"** (once, not every day) and gets the statement **automatically once an address is filled in**. A statement that failed for a technical reason is tried again the next day. *Statements Sent* always holds one line per customer and period for the automatic run.

## Good to know

- Amounts are in **company currency**, also for customers invoiced in another currency.
- Ageing and the overdue statement use the amounts **open today**; the date only decides how old each item is.
- The wizard prepares statements for a company that is ticked in the company switcher.
- The portal page shows the statement of the company the portal user belongs to.
- *Send by Email* in the wizard renders one PDF per customer while you wait: for hundreds of customers at once, prefer the monthly automatic run.

## Technical

- Engine on `res.partner`: `_cl_statement_data()`, `_cl_overdue_data()`, `_cl_ageing()`, `_cl_send_statement()`; cron `_cron_cl_send_monthly_statements()`.
- Report `cl_customer_statement.action_report_customer_statement`; wizard `cl.customer.statement.wizard`; log `cl.customer.statement.log`.
- Tests: `odoo -i cl_customer_statement --test-tags /cl_customer_statement`.
- Odoo 18.0 · depends on `account`, `portal` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
