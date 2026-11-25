# Sales Margin Control (`cl_margin_control`)

Warn on low-margin sales and require approval below a margin floor — by [Code Legion](https://thecodelegion.com).

## What it does

- **Line margin warnings** — a **Margin %** column on the order lines, highlighted when the line margin is below a threshold.
- **Order margin warnings** — a banner when the whole order's margin is below a threshold.
- **Margin floor** — below a set margin, the order can't be confirmed until a margin approver approves it. Approvers get a **Margin Approval activity** and a work list under *Sales ▸ Orders ▸ Margin Approvals*; the salesperson is notified of the approval or rejection.

Uses Odoo's standard Sales Margin figures — no custom cost model.

## How the approval works

1. Someone clicks **Confirm** on a quotation below the floor. The quotation is not confirmed: a banner says it is waiting for margin approval, a note is logged and every approver gets an activity.
2. An approver opens it and clicks **Approve Margin** (the quotation is confirmed) or **Reject Margin** (it stays a quotation; confirming again asks again).
3. If the margin is fixed in the meantime the quotation simply confirms, and the request and its activities are withdrawn. Cancelling the quotation withdraws them too.

Who approves: the members of the group chosen under **Approved by** in the settings. If no group is chosen, the **Sales Administrators** approve. Users with the *Access Rights* administration right can always approve. Approvers need access to the orders they approve (e.g. Sales *User: All Documents*).

An approval covers the margin that was approved: if the margin drops below it afterwards, or the order is cancelled and set back to quotation, it needs a new approval. The approve and reject actions are checked on the server, not just hidden.

## Behaves well

- **Warnings fire on *low* margin** (below the threshold) — the case you actually want to catch, not "inside a range". An order exactly at the threshold is not flagged.
- **Batch confirm handles each order**: those below the floor go for approval, the rest confirm — it doesn't stop at the first one.
- **No new order state and no edit-locks**, so posting a note, sending a message or completing an activity on a pending order keeps working.
- Approval is evaluated **live from company settings**, so quotations that existed before install are covered too.
- **Its own activity type**: closing a margin request never touches the other to-dos planned on the order.
- **Automatic confirmations** (online payment, customer signature, eCommerce, other automations) are never left hanging without anyone knowing: by default they are confirmed and a note is logged on the order; untick the setting to hold them for approval instead.
- The line margin fields are for internal users only, like Odoo's own margin fields.

## Configuration

**Sales ▸ Configuration ▸ Settings ▸ Margin Control** (per company):

- **Low-Margin Alerts**: highlight lines under a percentage, warn on orders under a percentage. Information only.
- **Approval Under a Margin Floor**: the floor percentage, who approves (**Approved by**, empty = Sales Administrators) and **Let Automatic Confirmations Through** (on by default).

## Technical

- Settings on `res.company` (`cl_margin_*`); `cl_margin_approval_state`, `cl_margin_approved_percent` and the approve/reject actions on `sale.order`; `cl_margin_pct` / `cl_margin_low` on `sale.order.line`; activity type `cl_margin_control.mail_activity_type_margin_approval`.
- Tests: `odoo -i cl_margin_control --test-tags /cl_margin_control`.
- Odoo 18.0 · depends on `sale_management`, `sale_margin` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
