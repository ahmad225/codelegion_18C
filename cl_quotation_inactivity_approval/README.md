# Stale Quotation Approval (`cl_quotation_inactivity_approval`)

Quotations left untouched for too long need a manager's approval before they become orders. By [Code Legion](https://thecodelegion.com).

Prices, stock and terms change. If a quotation had no activity for longer than the days you set, confirming it sends it for approval instead. Approvers get an activity, approve or reject, and the salesperson carries on.

## What it does

- **Inactivity rule**: Set the number of days in Sales settings (default 14, 0 = off).
- **Approve or reject**: Approvers get an activity; approved quotations can then be confirmed. The salesperson is notified of the decision.
- **Not a permanent pass**: An approval counts as activity. If the approved quotation is left alone again for longer than the limit, it needs a new approval.
- **Locked while pending**: Only approvers can change the customer, lines, prices or terms of a quotation waiting for approval.
- **Quotations to Approve**: A menu under Sales > Orders lists the quotations waiting for approval.
- **Real activity only**: Changes to the quotation and messages to or from the customer count. Internal notes and tracking do not.

## Behaves well

- Confirming several quotations at once confirms the fresh ones and sends only the stale ones for approval.
- Online acceptance, signature and payment by the customer are never blocked.
- No new order status and no changes to Odoo's own read-only rules: confirmed orders stay locked as usual.
- Approvers get a real activity, not just a pop-up; no scheduled job.
- A pending quotation that an approver confirms directly, or that the customer accepts online, closes the request and its activities by itself.
- A quotation that could not be confirmed anyway (for example a line without a product) is not sent to the approvers; the usual error is shown.
- If a company has no approver, confirming a stale quotation says so instead of leaving it pending with nobody to approve it.
- The last-activity date and the approval status cannot be set by hand, import or API by anyone who is not an approver.
- Notes are logged in the chatter and work for users without an email address.

## Technical

- Fields `cl_last_activity_date`, `cl_approval_state` on `sale.order`; group `cl_quotation_inactivity_approval.group_cl_quotation_approver`.
- Overrides `action_confirm()`, `create()`/`write()` and `_message_post_after_hook()`; activity type `mail_act_cl_quotation_approval`.
- Tests: `odoo -i cl_quotation_inactivity_approval --test-tags /cl_quotation_inactivity_approval`.
- Odoo 18.0 · depends on `sale` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
