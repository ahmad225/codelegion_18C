# Credit Note & Return Approval (`cl_credit_note_return_approval`)

Customer credit notes under control, tied to the goods coming back — by [Code Legion](https://thecodelegion.com).

## What it does

- **Credit note reasons.** A reason is chosen in the *Reverse* wizard when a customer invoice is credited, and shown on the credit note. A reason can state that the **goods must come back**.
- **Limits against the invoice.** A credit note made from an invoice cannot credit a product that was not invoiced, more quantity than is left after the other credit notes, a higher unit price, or more than the invoice's untaxed total. Everything that is wrong is listed in one message.
- **Return requests.** When the goods must come back, accounting clicks **Request Return** on the draft credit note. The request lists the goods (as far as they were delivered and are not already coming back) and waits for a **Return Approver**, who gets an activity.
  - **Approve** creates the return transfers from the original deliveries, most recent first.
  - **Reject** creates nothing: the warehouse never sees a return nobody agreed to.
  - **Cancel Request** withdraws a request and cancels its transfers that are not received yet — for instance to change the credit note and ask again.
- **Posting waits for the goods.** A credit note whose reason requires a return can only be posted when its request is approved and the goods are received (every transfer done or cancelled, at least one done — back orders included). The *Goods Return* badge on the credit note shows where things stand.
- **Returned Goods** analysis (Accounting ▸ Reporting ▸ Management): quantity received and value credited by reason, product, category, customer and salesperson.

## Set-up

1. Give the group **Customer Returns ▸ Return Approver** to the people who decide (it includes Inventory user rights).
2. **Accounting ▸ Configuration ▸ Invoicing ▸ Credit Note Reasons**: review the reasons and tick *Goods Must Come Back* where it applies. Four reasons are created at installation.

Daily use: **Accounting ▸ Customers ▸ Return Requests**, and **Inventory ▸ Operations ▸ Returns To Approve** for approvers.

## How it behaves

- The checks run in `_post()`, the one door every posting goes through: the Confirm button, *Reverse and Create Invoice*, automatic posting. *Reverse and Create Invoice* is also hidden when the chosen reason requires a return.
- **Approval is a right, not a hidden button.** Approving or rejecting — or writing the decision directly through the API — is refused to anyone who is not a Return Approver. A request always starts "To Approve", cannot be moved to another credit note, and the link between a transfer and its request cannot be set by hand.
- **No new transfer state**: approval lives on the request, so cancelling, back orders and uninstalling behave as in standard Odoo. A back order of an authorised return stays part of it.
- **A return cannot bring back more than was delivered**, whatever is typed on the transfer; only authorised returns are checked, ordinary returns are untouched.
- Lines **without a product** are allowed. Quantities and prices are compared in the **product's unit of measure**. **Services** are never asked back.
- The reason is asked for **customer invoices only**; vendor bills and journal entries reversed with the same wizard are left alone.
- The person preparing the credit note **does not need Inventory access**, and the approver does not need Accounting access.
- Approver activities go to the approvers **of the company concerned**; the requester is notified of the decision.

## Good to know

- Returns are created from the deliveries of the **sales order(s)** behind the invoice. An invoice that was not delivered from a sales order has nothing to return: choose a reason that does not require a return.
- Price and total limits are compared when the credit note is in the invoice's currency.
- The value in the analysis is the quantity received × the credit note's unit price for the product, in company currency.
- Products delivered as kits (components shipped instead of the invoiced product) are not matched.

## Technical

- Models: `cl.credit.note.reason`, `cl.return.request` (+ `.line`), `cl.return.analysis` (SQL view). Fields `cl_credit_reason_id`, `cl_return_status` on `account.move`; `cl_return_request_id` on `stock.picking`. Group `group_cl_return_approver` in its own category.
- Tests: `odoo -i cl_credit_note_return_approval --test-tags /cl_credit_note_return_approval`.
- Odoo 18.0 · depends on `account`, `sale_stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
