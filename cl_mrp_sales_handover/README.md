# Manufacturing to Sales Handover (`cl_mrp_sales_handover`)

Finished production flows back to the sales order, the salesperson and the customer. By [Code Legion](https://thecodelegion.com).

The sales order shows when its manufacturing will be ready and keeps the delivery date in step. Production marks orders as handed over to the warehouse, the salesperson is told, and collection customers get a "ready for collection" email with reminders.

## What it does

- **Delivery date in step**: The latest manufacturing finish date updates the delivery date. Dates agreed with the customer are protected.
- **Handover to warehouse**: When every manufacturing order of the sales order is handed over, the salesperson gets a "Ready for Delivery" activity.
- **Event dates**: The customer's event date on the order is shown to production (sub-assemblies of any level included), with a warning when production would finish too late.
- **Ready for collection**: Customers collecting their order get an email when it is ready, plus reminders until they collect.

## Behaves well

- A date the customer agreed is never moved silently: the salesperson is told, or it moves later only, with a note.
- A sales order counts as handed over only when every one of its manufacturing orders is.
- Each delivery and backorder gets its own collection email, sent once; reminders stop when it is collected or cancelled.
- Emails are queued and sent in the salesperson's name, the reminder job works in safe batches, and every part can be switched on or off per company.
- A handover can only be set or undone with its buttons: the fields cannot be typed, imported or written through the API.

## Technical

- Fields `cl_sale_order_id`, event date and handover state on `mrp.production`; `cl_event_date` on `sale.order`; `cl_handover_collection` on `delivery.carrier`.
- Daily reminder cron; mail templates for ready-for-collection and reminders.
- Works next to `cl_mrp_mto_approval` (which keeps its own link in `cl_mto_sale_order_id`); neither module needs the other.
- Tests: `odoo -i cl_mrp_sales_handover --test-tags /cl_mrp_sales_handover`.
- Odoo 18.0 · depends on `sale_mrp`, `stock_delivery` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
