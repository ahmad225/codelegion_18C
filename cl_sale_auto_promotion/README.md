# Auto-Apply Promotions on Quotations (`cl_sale_auto_promotion`)

Eligible automatic promotions are applied to quotations as you work, and the savings are shown on the PDF. By [Code Legion](https://thecodelegion.com).

Each time quotation lines change, automatic promotions the customer qualifies for are applied. When several discounts compete, the salesperson chooses. The order and invoice show the customer how much they saved.

## What it does

- **Applied automatically**: Free products and a single eligible discount are added as soon as the quotation qualifies.
- **You choose when it matters**: Several competing discounts? A banner asks the salesperson to choose, using the standard rewards window.
- **End notice**: one banner on the quotation tells when a promotion used on it is about to end (amber) or has ended (red).
- **Savings shown**: a line under the totals of the order and the invoice, and on both PDFs, tells how much of the amount is promotion savings.
- **Promotions on the quotation PDF**: the promotions applied are listed under the totals, with their end date while the quotation is still open.

## Behaves well

- Loyalty points, eWallet and gift card balances are never spent automatically; only automatic promotions are claimed.
- Coupons, codes and rewards the salesperson applied by hand are never removed.
- A promotion line the salesperson deletes stays deleted on that quotation for as long as the promotion keeps applying. If the quotation stops earning it (lines removed, quantity lowered) and earns it again later, it is offered again.
- The chatter note is a log note: nobody is notified, and it also works for users without an email address.
- Savings exclude eWallet and gift card payments, and each invoice shows only its own savings.

## Technical

- Settings `cl_promo_auto_apply`, `cl_promo_expiry_notice_days` per company (Sales > Configuration > Settings > Pricing).
- Uses sale_loyalty `_update_programs_and_rewards()`, `_get_claimable_rewards()`, `_apply_program_reward()`; lines it adds are marked `cl_auto_applied`.
- Tests: `odoo -i cl_sale_auto_promotion --test-tags /cl_sale_auto_promotion`.
- Odoo 18.0 · depends on `sale_loyalty` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
