# Partner Payment Term Default (`cl_partner_payment_term_default`)

A company's payment terms apply to all its contacts — except the contacts you decide should keep their own — by [Code Legion](https://thecodelegion.com).

## The rule

A contact has the customer and vendor payment terms **of its company**, unless **Keep Own Payment Terms** is ticked on it.

## What it does

- **New contacts** of a company get the company's customer and vendor payment terms — whether they are created from the company form, the full contact form, an import or the website.
- **Changing the company's terms** updates all its contacts, at any depth (contacts of contacts too), archived ones included.
- **Give a contact different terms** and *Keep Own Payment Terms* is ticked for you: from then on the company's changes no longer touch it. In the form you see the box tick itself as soon as you pick other terms.
- **Untick** the box and the contact goes straight back to its company's terms.
- **Move a contact to another company** and it takes the terms of the new company.
- **Apply Company Payment Terms** (Actions menu on contacts, invoicing users) repairs existing data: select companies to realign all their contacts, or select individual contacts. It tells you how many were updated, already right, or left alone because they keep their own terms.

## Behaves well

- Payment terms are stored **per company**. A new or moved contact is aligned in **every company** of the database, and a change made while working in one company only touches that company's terms — exactly like the change itself.
- A contact that keeps its own terms is **never overwritten**, not by a change on the company and not by the manual action.
- A child **company** (a subsidiary recorded under its parent) is its own commercial entity, as in standard Odoo: it does not take the parent's terms, and its own contacts follow it.
- The empty payment-term fields that the contact form sends when a contact is created do not win over the company's terms.
- Works for users without access to every company: the alignment itself runs with system rights.

## Good to know

- In standard Odoo, payment terms are "commercial fields" that are force-copied from the company to its contacts. This app takes them out of that mechanism and applies the rule above instead; uninstalling it brings the standard behaviour back.
- Contacts that already differ from their company when the app is installed are left as they are until the company's terms change or you run **Apply Company Payment Terms**. Tick *Keep Own Payment Terms* first on those that must stay different.
- The setting is one box per contact for both customer and vendor terms.

## Technical

- `cl_keep_own_payment_term` on `res.partner`; `_commercial_fields` override; rule applied in `create` / `write` (`_cl_align_payment_terms`), three small onchanges for form feedback, and the server action `action_cl_sync_payment_terms`.
- Tests: `odoo -i cl_partner_payment_term_default --test-tags /cl_partner_payment_term_default`.
- Odoo 18.0 · depends on `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
