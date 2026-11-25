# Delete Confirmed Purchase Lines (`cl_purchase_line_control`)

Let authorised buyers remove a line from a confirmed purchase order, safely. By [Code Legion](https://thecodelegion.com).

The vendor can't supply one item? Authorised buyers can delete that line from the confirmed order. The receipt stops expecting it and the change is logged.

## What it does

- **Authorised users only**: members of the *Delete Confirmed Purchase Lines* group can delete a product line of a confirmed order. Everybody else gets Odoo's standard refusal.
- **Receipt updated**: the goods still to be received for that line are cancelled on the receipt (the receipt itself is cancelled when nothing else is expected).
- **Never once something happened**: a line with goods received (even if returned since) or on a vendor bill cannot be deleted. The error lists every blocked line with its reason.
- **Locked orders stay locked**: unlock the order first.
- **Logged**: one note on the purchase order and one on each open receipt list what was removed; the note's author is the user who did it. Notes are logged without e-mail, so they also work for users with no e-mail address.

## Behaves well

- Received or billed lines are protected, so stock and accounting stay correct.
- The product on a line can't be changed after goods were received for it.
- Draft orders and note/section lines behave exactly as in standard Odoo.
- Other lines' dates and prices are never touched.

## Configuration

Settings ▸ Users ▸ (user) ▸ *Purchase Line Deletion*: **Delete Confirmed Purchase Lines**. The group includes Purchase / User.

## Technical

- Group `cl_purchase_line_control.group_cl_po_line_delete`, in its own category.
- Extends the `purchase.order.line` ondelete rule `_unlink_except_purchase_or_done` (standard rule kept for non-members); `unlink()` checks first, lets `purchase_stock` cancel the open moves, then logs with `_message_log`.
- Tests: `odoo -i cl_purchase_line_control --test-tags /cl_purchase_line_control`.
- Odoo 18.0 · depends on `purchase_stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
