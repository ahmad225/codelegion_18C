# Customer Artwork Approval (`cl_sale_artwork_approval`)

Customer logos designed, approved and reused on every order, and sent to production with the manufacturing order. By [Code Legion](https://thecodelegion.com).

On the order's Artwork tab, salespeople click *Request Artwork* on a line, attach the customer's logo and send it to a designer. The designer uploads a proof, the salesperson approves it or asks for rework, and the approved artwork is kept per customer and product. It is reused on the next order and travels with the manufacturing order.

## What it does

- **Designer flow**: Send to a designer, who gets an activity, uploads the proof and sends it back for review.
- **Rework or approve**: Ask for changes with a comment, or approve. Every proof stays in the history.
- **Per customer and product**: Versioned artwork per customer and product (or variant), reused automatically on the next order. *New Version* on an order line starts a changed design from the approved one.
- **Line by line on the order**: the Artwork tab lists each line that needs artwork, the artwork it has and its status.
- **On the manufacturing order**: Production sees the approved proof and gets a copy on the manufacturing order.

## Behaves well

- Only products flagged "Requires Artwork" can block confirmation, and online customer acceptance is never blocked.
- Workflow states change only through the buttons, approved artwork is frozen, and only managers can delete.
- Files on the artwork are private: only users who can open the artwork see them, never portal users. The copy attached to a manufacturing order (a setting, on by default) is visible to whoever can open that order.
- Workflow notes work for users without an email address.
- Lean: depends only on Sales and Manufacturing. No projects, timesheets or HR needed.

## Technical

- Model `cl.artwork` (customer, product, version, proof, state) with rework wizard; product flag and company settings.
- Groups Designer and Manager in their own "Customer Artwork" category; optional block on MO start until approved.
- Tests: `odoo -i cl_sale_artwork_approval --test-tags /cl_sale_artwork_approval`.
- Odoo 18.0 · depends on `sale_mrp` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
