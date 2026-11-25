# Payment Unreconcile Warning (`cl_payment_unreconcile_warning`)

A confirmation dialog before a reconciled payment is removed from an invoice or bill — by [Code Legion](https://thecodelegion.com).

## What it does

- When you click **Unreconcile** in the payment widget of an invoice, bill, credit note or receipt, a confirmation dialog appears first.
- The dialog names **what is removed** (the payment, credit note or other entry), the **amount** and the **document it is removed from**, and reminds you that the payment itself is not cancelled.
- **Unreconcile** proceeds, **Keep it** leaves the reconciliation untouched.

## Behaves well

- Purely a confirmation step: it **never hides or disables** the standard *Reset to Draft* button and keeps **no extra flag** on the invoice — so there's no stuck state and nothing to get out of sync.
- Names the two sides the right way round, including invoice / credit-note matches seen from either document.
- Once confirmed, the **standard** Odoo method removes the reconciliation, so other apps that extend it keep working.
- If the wording cannot be worked out (the reconciliation is already gone, or the server call fails) a generic question is asked instead: the dialog never blocks the action.
- Other ways of unreconciling (the *Unreconcile* action on journal items, bank reconciliation) are not changed; Odoo already asks for confirmation there.

## Technical

- Patches the backend `AccountPaymentField` widget: `removeMoveReconcile` asks first, then calls the original method.
- One read-only helper, `account.move.cl_unreconcile_warning_message(partial_id)`, called on the document on screen; no new fields, models or views.
- Tests: `odoo -i cl_payment_unreconcile_warning --test-tags /cl_payment_unreconcile_warning`.
- Odoo 18.0 · depends on `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
