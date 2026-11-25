# Photo Proof on Transfers (`cl_transfer_photo_proof`)

Require a photo or PDF for every product line before a transfer can be validated. By [Code Legion](https://thecodelegion.com).

Tick "Require Photo Proof per Product" on an operation type (receipts, deliveries, manufacturing pickings...). Each product line then needs at least one photo or PDF before the transfer is validated, however it is validated.

## What it does

- **Per product line**: A camera button on each line opens its proof files; the Proofs column counts them and turns red while a line with a quantity has none.
- **Per operation type**: Switch the rule on only where you need it.
- **Enforced on the server**: The rule applies to the form, the barcode app and the API alike.
- **Chatter summary**: One note per transfer lists the products, quantities and number of files, with links to them.

## Behaves well

- Only lines actually being processed need proof: partial transfers and backorders work normally.
- Only images and PDFs uploaded on the line itself are accepted: a link, an empty file or a file that belongs to another document is refused.
- Proof of a done line cannot be changed: neither the list of files nor the files themselves (no deleting from the chatter note, no replacing).
- Proof files follow the access rights of the transfer line: only users who can read the line (inventory users) can open them, never public users.
- Validating users do not need an email address; files are linked, not copied.

## Technical

- Option `cl_require_photo_proof` on `stock.picking.type`; files in `cl_proof_attachment_ids` on `stock.move`.
- Check in `stock.picking._action_done()`, before any stock moves; `ir.attachment` write/unlink guard for the proof files of done lines.
- Tests: `odoo -i cl_transfer_photo_proof --test-tags /cl_transfer_photo_proof`.
- Odoo 18.0 · depends on `stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
