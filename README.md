# Code Legion — Odoo 18 Modules

Odoo 18 modules developed by [Code Legion](https://thecodelegion.com).

| Module | Technical name | Summary |
|--------|----------------|---------|
| Customer Credit Control | `cl_credit_control` | Block sales orders for customers with overdue invoices, over their credit limit or on credit hold, with an approve / reject workflow. |
| Invoice Payment Reminders | `cl_invoice_reminder` | Email customers automatically about overdue invoices, stage by stage, with one email per customer and a record of every reminder sent. |
| Low Stock Notifications | `cl_low_stock_notification` | Daily e-mail of the products below their minimum stock, with an Excel list, plus a PDF / Excel report on demand. |
| Product Keyword Search | `cl_product_keyword_search` | Find products by your own keywords - nicknames, old references, competitor names - in the backend, the web shop and the POS. |
| Last Purchase Price | `cl_last_po_price` | Fill a purchase order line's price from the product's last confirmed purchase order. |
| Sales Margin Control | `cl_margin_control` | Warn on low-margin sales order lines and orders, and require approval below a margin floor before confirmation. |
| Order Checklist | `cl_order_checklist` | Require a checklist to be completed before confirming a Sales Order or completing a Manufacturing Order. |
| Previously Ordered Products | `cl_previously_ordered_products` | A customer portal page listing previously ordered products with one-click reorder. |
| Payment Unreconcile Warning | `cl_payment_unreconcile_warning` | Ask for confirmation before removing a reconciled payment from an invoice or bill. |
| Auto-send Invoice on Delivery | `cl_delivery_invoice_auto_send` | Automatically send the customer invoice (with its PDF) once the delivery is validated. |
| Allowed Pricelists per Customer | `cl_allowed_pricelist` | Restrict which pricelists can be chosen on a sales order to the ones allowed for the customer. |
| Product Packaging Measurements | `cl_product_packaging_measurements` | Record the length, width, height and gross weight of product packagings and show them on sales order lines. |
| Chart of Accounts Archive | `cl_account_archive` | Archive and unarchive accounts in the Chart of Accounts. |
| Partner Payment Term Default | `cl_partner_payment_term_default` | Default and sync a company's payment terms down to its child contacts, while letting a contact keep its own. |
| Operations Sign Block | `cl_operations_sign_name` | Name, date and signature boxes at the end of the Picking Operations and Batch Transfer printouts, per operation type. |
| Invoice Send Recipient Control | `cl_invoice_send_recipient_control` | When emailing an invoice, notify only the chosen recipients, not the document's followers. |
| Customer Statements | `cl_customer_statement` | Customer account statements and overdue statements: PDF, email, customer portal and monthly automatic sending. |
| Credit Note & Return Approval | `cl_credit_note_return_approval` | Customer credit notes under control: a reason on every credit note, limits against the invoice, and goods returns that must be approved and received before the credit note is posted. |
| Product Compatibility | `cl_product_compatibility` | Stop products that do not fit together - such as a cup and the wrong-size lid - from being sold on the same order. |
| Product Compatibility - eCommerce | `cl_product_compatibility_website` | Block website checkout while the cart holds incompatible products, and tell the customer why. |
| Incoming Purchases on Product | `cl_product_purchase_lines` | See the open purchase order lines still to be received, directly on the product form. |
| Manufacturing Order Description | `cl_mrp_order_description` | Add a description to manufacturing orders and print it - and the shop floor note - on the Production Order PDF. |
| Back-in-Stock Email Server | `cl_back_in_stock_mail_server` | Send the eCommerce "back in stock" emails through a dedicated outgoing mail server. |
| Product Review Notifications | `cl_product_rating_notification` | Email your team as soon as a customer rates or reviews a product on the website. |
| Delete Confirmed Purchase Lines | `cl_purchase_line_control` | Let authorised buyers remove a line from a confirmed purchase order - safely, with its receipt updated and a full log. |
| Suspend Quotations | `cl_sale_order_suspension` | Park a quotation with a reason and a follow-up date; it cannot be confirmed or sent until it is resumed. |
| Stale Quotation Approval | `cl_quotation_inactivity_approval` | Quotations left untouched for too long need a manager's approval before they can be confirmed. |
| Click & Collect PIN | `cl_collection_pin` | Secure collection PIN for click & collect orders: emailed to the customer, verified at the counter before the delivery can be validated. |
| Auto-Apply Promotions on Quotations | `cl_sale_auto_promotion` | Apply eligible automatic promotions on quotations as the lines change, warn about expiring promotions and show the customer their total promotion savings. |
| Website App Install (PWA) | `cl_website_pwa_install` | Let visitors install your website as an app: web manifest, service worker and an install invitation on the homepage. |
| Customer Approval | `cl_contact_approval` | New customers must be checked and approved before their sales orders can be confirmed. |
| Courier Cost Control | `cl_courier_cost` | Estimate what each delivery should cost you from a formula per delivery method, then reconcile it with what the courier billed. |
| Photo Proof on Transfers | `cl_transfer_photo_proof` | Require a photo or PDF for every product processed before a transfer of the chosen operation types can be validated. |
| Make-to-Order Approval | `cl_mrp_mto_approval` | Manufacturing orders created from sales orders wait for a Manufacturing Coordinator's approval before production starts. Salespeople follow the production of their sales orders read-only. |
| Manufacturing to Sales Handover | `cl_mrp_sales_handover` | Keep sales in step with production: delivery dates follow the manufacturing orders, the salesperson is told when goods are handed over, event dates reach production and customers hear when their order is ready for collection. |
| Customer Artwork Approval | `cl_sale_artwork_approval` | Customer logos and print artwork per customer and product: designer proofs, rework and approval, reused on the next order and sent to manufacturing. |
| Customer Credit Controller | `cl_partner_credit_controller` | Give every customer a credit controller, kept the same on all its contacts, orders and invoices. |
| Hikvision Attendance Sync | `cl_hr_attendance_hikvision` | Download punches from Hikvision access-control and time-attendance terminals and turn them into Odoo attendances. |
| Product Allowed Units Filter | `cl_uom_filter` | Select the allowed units on each product; only those are offered in Sales, Purchase, Inventory, Manufacturing and Accounting. |

## Installation

Copy the module folder into your Odoo addons path, update the apps list, and install from **Apps**.

All modules target **Odoo 18.0** and are licensed **LGPL-3**.

---
© Code Legion — https://thecodelegion.com
