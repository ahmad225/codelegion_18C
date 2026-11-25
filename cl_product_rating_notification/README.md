# Product Review Notifications (`cl_product_rating_notification`)

Email your team as soon as a customer rates or reviews a product. By [Code Legion](https://thecodelegion.com).

Every new or edited product review on your shop sends an email to the people you choose, with the rating, the comment and a link to the review.

## What it does

- **New reviews**: A review or rating on a product emails your team straight away.
- **Edited reviews**: When a customer changes the rating or comment, the team hears about it too.
- **Choose who hears**: Pick the contacts to notify in Website settings, per company. A product that belongs to a company notifies that company's team; otherwise the team of the website's company is notified.
- **Your own template**: A ready email template is set on install; edit it or choose another.

## Behaves well

- Only product reviews notify; ratings on other records (tickets, tasks) are ignored.
- One email per review: no duplicates when Odoo saves a review, and saving a review without changing the rating or comment sends nothing.
- Sent from the company's address, never from the reviewing customer, even with a template that has no sender.
- A broken email template never stops a customer from posting a review; the problem is written to the server log.
- Recipients are contacts, not typed-in addresses; emails are queued, so the customer never waits.
- The email links your team straight to the review.

## Technical

- Company fields `cl_rating_template_id` and `cl_rating_partner_ids`, shown in Website settings (saved on the company of the website being configured).
- `rating.rating` create/write call `_cl_notify_product_review()`; template `mail_template_product_rating`.
- Tests: `odoo -i cl_product_rating_notification --test-tags /cl_product_rating_notification`.
- Odoo 18.0 · depends on `website_sale`, `rating` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
