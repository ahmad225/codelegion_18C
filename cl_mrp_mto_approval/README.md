# Make-to-Order Approval (`cl_mrp_mto_approval`)

Manufacturing orders created from sales orders wait for a coordinator before production starts. By [Code Legion](https://thecodelegion.com).

When a confirmed sales order creates a manufacturing order (make-to-order), production cannot plan, start or produce it until a Manufacturing Coordinator approves it. Coordinators get an activity, approve or reject with a reason, and salespeople can follow the manufacturing of the sales orders they can open.

## What it does

- **Coordinator approval**: Approve with one click, or reject with a reason and optionally cancel the order.
- **Activities, not pop-ups**: Coordinators get an activity; one decision closes it for all of them. Rejections notify the salesperson on the sales order.
- **Approve in bulk**: Manufacturing > Operations > To Approve lists the waiting orders; select several and approve.
- **Salespeople follow along**: An opt-in group adds a Manufacturing button to the sales orders a salesperson can open and shows that order's manufacturing, read-only.
- **Only sales-driven orders**: Manual manufacturing orders and reordering rules are never held.

## Behaves well

- No new manufacturing state: Odoo's own flow is untouched; only planning, starting and producing wait.
- Backorders, splits and sub-assemblies (1, 2 or 3 step manufacturing) keep the approval of their order; no repeated requests.
- Waiting orders cannot be merged into a new order to get around the approval.
- The link to the sales order comes from the procurement, never from matching the Source text.
- Approval cannot be bypassed through imports or the API; administrators can approve too.

## Technical

- Fields `cl_approval_state` and `cl_mto_sale_order_id` on `mrp.production`, set in `stock.rule._prepare_mo_vals()`; guards on plan/start/produce/merge and work orders.
- Groups in their own "Make-to-Order Approval" category; reject wizard `cl.mrp.mto.reject.wizard`.
- Salespeople in the viewer group cannot write, create or delete manufacturing and work orders (record rules). Reading is left as Odoo defines it, so the Forecast report keeps working for them.
- Works next to `cl_mrp_sales_handover`: the two modules share no field.
- Tests: `odoo -i cl_mrp_mto_approval --test-tags /cl_mrp_mto_approval`.
- Odoo 18.0 · depends on `sale_mrp` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
