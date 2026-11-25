# Click & Collect PIN (`cl_collection_pin`)

Hand click-and-collect orders only to the right customer, with a one-time PIN. By [Code Legion](https://thecodelegion.com).

When a collection order is ready, the customer receives a 6-digit PIN by email. Staff must enter it before the collection can be validated, and every attempt is logged.

## What it does

- **Collection methods**: Mark any delivery method as "Customer Collection".
- **PIN when ready**: The PIN is emailed when picking is done, or at confirmation for one-step warehouses.
- **Checked at handover**: Validating the collection asks for the PIN. Without it the delivery cannot be validated, whichever way it is validated.
- **Audit log**: Every PIN issued, verified, failed, locked, cleared or expired is logged, with the user and date.

## Behaves well

- The PIN is never stored or shown: only a salted hash is kept, and staff never see it in forms, chatter or logs.
- Wrong attempts are counted and the PIN locks after a limit you set; only a stock manager can issue a new one.
- Expired, used and locked PINs are refused. Changing the delivery method clears the PIN and logs it.
- The check cannot be switched off from the warehouse: only sales users and stock managers can change the delivery method of an order waiting for collection (only a stock manager while the PIN is locked), and an open collection delivery cannot be detached from its order.
- The PIN email goes to the customer only, whatever recipients are added to the email template.
- Works for counter staff without an email address and for users limited to their own sales orders.
- No limits on changing the delivery method of normal orders; no dependency on WhatsApp or other apps.

## Technical

- Fields on `sale.order` and `stock.picking`, wizard `cl.collection.pin.verify`, log `cl.collection.pin.log`.
- Hooks `stock.picking._action_done()` / `button_validate()`; email template `mail_template_collection_pin`.
- Tests: `odoo -i cl_collection_pin --test-tags /cl_collection_pin`.
- Odoo 18.0 · depends on `sale_stock`, `delivery`, `mail` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
