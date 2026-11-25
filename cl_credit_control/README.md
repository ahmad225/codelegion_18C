# Customer Credit Control

Odoo 18 module by Code Legion. Technical name: `cl_credit_control`. Licence: LGPL-3.

Stops a quotation from being confirmed when the customer is a credit risk, and lets a
Credit Manager approve or reject the exception.

## When a quotation is blocked

| Reason | Where it is set |
|---|---|
| Invoices overdue by more than the allowed days | Sales settings (company), or per customer |
| The order would take the customer over the credit limit | Odoo's own credit limit on the customer |
| The customer is on credit hold | Customer form |

A customer marked **Exempt from Credit Control** is never blocked.

## How it works

1. The salesperson opens a quotation. If the customer is blocked, a red banner on the
   quotation lists the reasons.
2. **Request Credit Approval** on the quotation (or **Confirm**, then **Review Credit Block**)
   opens a dialog with the overdue items; the salesperson adds a note and clicks
   **Request Approval**.
3. Every Credit Manager of that company gets a **Credit Approval** activity. The quotation
   appears under *Sales > Orders > Credit Approvals*.
4. A Credit Manager clicks **Approve Credit** (the quotation is confirmed) or **Reject Credit**
   (a reason is required and the quotation stays a quotation).
5. Requests, approvals and rejections are logged in the chatter, and the salesperson is notified.

An approval covers the approved order total. If the total is raised afterwards, the quotation
needs a new approval. Changing the customer clears the request.

A request that is no longer needed is withdrawn by itself and the Credit Managers' activities
are closed: when the customer is cleared and the quotation is confirmed normally, when an
automatic confirmation is let through, or when the quotation is cancelled. A cancelled order
that is set back to quotation needs a fresh approval.

## Setup

1. *Sales > Configuration > Settings > Credit Control*:
   - **Block Orders for Overdue Invoices**, with **Allowed Overdue Days** and
     **Ignore Overdue Up To**.
   - **Block Orders Over the Credit Limit** (switches on Odoo's *Sales Credit Limit*).
   - **Let Automatic Confirmations Through**: orders confirmed by online payment, customer
     signature or another automation are confirmed anyway and a note is logged. Untick to
     block those as well.
2. *Settings > Users*: give **Credit Control: Credit Manager** to the approvers. The right
   includes Sales *User: All Documents*, because a Credit Manager has to open other
   salespeople's quotations.
3. On a customer (*Sales & Purchase* tab, *Credit Control*): credit hold, exemption and an
   own overdue allowance. Only Credit Managers can change these (checked on the server, not
   just hidden on the form), and they are not copied when a customer is duplicated.

## Design notes

- The quotation keeps its normal status while it waits. The approval has its own field
  (`cl_credit_state`), so no standard status, button or status bar is replaced.
- A blocked confirmation always raises an error. It never returns silently, so an automated
  caller cannot believe an order was confirmed when it was not.
- An approved quotation is confirmed through the standard `action_confirm`, so every other
  module's checks still run.
- Overdue amounts come from open receivable journal items by due date, so instalments are
  handled. They are worked out live, per company, with no scheduled job.
- The customer filter *Overdue Beyond Allowance* uses the company allowance for everyone;
  a customer's own allowance applies on the customer form and when an order is checked.

## Tests

```
odoo-bin -d <database> -i cl_credit_control --test-tags /cl_credit_control --stop-after-init
```
