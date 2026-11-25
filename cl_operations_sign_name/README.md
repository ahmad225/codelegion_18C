# Operations Sign Block (`cl_operations_sign_name`)

Name, date and signature boxes at the end of the Picking Operations and Batch Transfer printouts — by [Code Legion](https://thecodelegion.com).

## What it does

- Prints three boxes to fill in by hand — **Name**, **Date and time**, **Signature** — at the end of the **Picking Operations** document and of the **Batch Transfer** document.
- Turned on **per operation type**, so only the transfers you choose carry it. A batch follows the operation type of the batch.

## Behaves well

- The block belongs to **those two documents only**. The company document layout (header / footer) is not modified, so invoices, quotations and every other PDF are unaffected, whichever layout the company uses — including the newer Odoo 18 layouts.
- The **Delivery Slip**, the return slip and the labels do not get the block.
- The three boxes are kept together: they are never split over two pages.

## Configuration

**Inventory ▸ Configuration ▸ Operations Types** ▸ open a type ▸ tick **Sign-off Block on Printout** (General tab). The option is also available as an optional column in the list of operation types.

## Technical

- `cl_sign_block` on `stock.picking.type`; QWeb template `cl_operations_sign_name.sign_block` called at the end of the page of `stock.report_picking` and `stock_picking_batch.report_picking_batch`.
- Tests: `odoo -i cl_operations_sign_name --test-tags /cl_operations_sign_name` (they render both documents and the delivery slip).
- Odoo 18.0 · depends on `stock`, `stock_picking_batch` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
