# Customer Credit Controller (`cl_partner_credit_controller`)

Give every customer a credit controller, kept the same on all its contacts, orders and invoices. By [Code Legion](https://thecodelegion.com).

Set the credit controller on the customer's company next to the salesperson. It is copied to every contact person automatically and shown on sales orders and invoices. Each controller gets a list of their own customers' overdue invoices.

## What it does

- **On every contact**: Set it once on the company: all its contacts, at every level, follow it.
- **Orders and invoices**: Shown on sales orders and customer invoices, searchable and groupable. Vendor bills are left alone.
- **My invoices to chase**: One filter lists the overdue invoices of the controller's own customers.
- **On the invoice PDF**: Optionally printed on invoices, so customers know who to contact.

## Behaves well

- Uses Odoo's own commercial-field sync, like the VAT number, so contacts at every level stay in step.
- A contact moved to another company takes that company's controller.
- No view patching at run time and no Studio fields.
- Only internal users can be credit controllers (checked on save, not only in the drop-down); the repair action is limited to contact managers.
- Installing on a large database is quick: the order and invoice columns are created empty instead of being computed record by record.

## Technical

- Field `cl_credit_controller_id` on `res.partner` (commercial field), stored related fields on `sale.order` and `account.move`.
- Setting `cl_print_credit_controller` (Accounting > Customer Invoices); server action "Sync Credit Controller to Contacts".
- Tests: `odoo -i cl_partner_credit_controller --test-tags /cl_partner_credit_controller`.
- Odoo 18.0 · depends on `sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
