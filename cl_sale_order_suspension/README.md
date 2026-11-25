# Suspend Quotations (`cl_sale_order_suspension`)

Put a quotation on hold with a reason and a follow-up date, without cancelling it. By [Code Legion](https://thecodelegion.com).

Waiting for artwork, a credit check or a customer answer? Suspend the quotation. It cannot be confirmed or emailed until it is resumed, and you get a To-Do on the follow-up date.

## What it does

- **Suspend with a reason**: Choose why and when to follow up. A To-Do is scheduled for you on that date.
- **Kept out of the flow**: A suspended quotation cannot be confirmed or emailed until someone resumes it. On the customer portal it cannot be signed or paid either.
- **Resume in one click**: Resume puts it back in the normal flow and closes the follow-up.
- **Customer warning**: Other quotations for the same customer (any of its contacts) show which of their quotations are on hold, as links you can open.

## Behaves well

- Only the "Suspend Quotations" group can suspend or resume, checked on the server, not only by hiding buttons. The suspension fields cannot be changed by anyone else, also not by import or API.
- No new order status: Odoo's own statuses, buttons and read-only rules are untouched.
- No scheduled job: the reminder is a normal activity with a due date.
- Cancelling a suspended quotation ends the suspension and closes its follow-up. Only the "Suspend Quotations" group can cancel a suspended quotation (a customer declining it on the portal still works), so cancel-and-reset is not a way around the hold.
- Suspending and resuming log a note in the chatter; they work for users without an email address.

## Technical

- Fields `cl_is_suspended`, `cl_suspended_by_id`, `cl_suspended_date`, `cl_suspension_reason`, `cl_other_suspended_order_ids` (computed) on `sale.order`; wizard `cl.sale.suspend.wizard`.
- Blocks confirmation through `_confirmation_error_message()` and the portal through `_has_to_be_signed()` / `_has_to_be_paid()`; group `cl_sale_order_suspension.group_cl_sale_suspension`.
- Tests: `odoo -i cl_sale_order_suspension --test-tags /cl_sale_order_suspension`.
- Odoo 18.0 · depends on `sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
