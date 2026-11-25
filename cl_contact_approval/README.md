# Customer Approval (`cl_contact_approval`)

New customers are checked and approved before their orders can be confirmed. By [Code Legion](https://thecodelegion.com).

Switch it on in Sales settings, choose the fields a customer must have, and new customers start as Draft. Salespeople send them for approval; approvers check and approve; only then can their quotations be confirmed. Existing customers are approved at install.

## What it does

- **Mandatory fields**: Choose the fields a customer must have (VAT, phone, address...) before approval.
- **Approve or reject**: Approvers get an activity, check the customer and approve or reject; the salesperson is notified.
- **Revoke**: An approver can take an approval back with "Revoke Approval"; the customer and its contacts return to Draft.
- **Orders wait for approval**: Staff cannot confirm a quotation for an unapproved customer.
- **Company and contacts**: Approval is held by the company; its contact persons follow it automatically.

## Behaves well

- Existing customers are approved at install, so switching it on never blocks current customers.
- The approval status can only be changed by approvers, checked on the server for forms, imports and the API.
- Orders the customer accepts or pays online are never blocked; approvers get an activity to review them instead.
- Mass approval skips customers with missing fields and tells you which fields. "Send for Approval" is also available on a selection in the contact list.
- When one approver decides, the activities of the other approvers are removed: one line in the chatter, not one per approver.
- Works for users without an email address.

## Technical

- Field `cl_approval_state` on `res.partner`, synced to contacts as a commercial field.
- Group `cl_contact_approval.group_cl_contact_approver`; check in `sale.order._confirmation_error_message()`.
- Tests: `odoo -i cl_contact_approval --test-tags /cl_contact_approval`.
- Odoo 18.0 · depends on `sale`, `mail` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
