# Back-in-Stock Email Server (`cl_back_in_stock_mail_server`)

Send eCommerce "back in stock" emails through their own outgoing mail server. By [Code Legion](https://thecodelegion.com).

Customers who ask to be told when a product is back in stock get that email through the outgoing server you choose, for example a marketing SMTP account. Every other email keeps using the usual server.

## What it does

- **Dedicated server**: Pick an outgoing mail server for back-in-stock emails in Website settings.
- **Per company**: Each company can use its own server. A product that belongs to a company uses that company's server; a shared product, or a company without its own server, uses the server of the website's company.
- **Nothing else changes**: Invoices, orders and all other emails are untouched.
- **Falls back safely**: No server chosen? Emails go out exactly as they do today.

## Behaves well

- Only back-in-stock emails are routed: the server is applied while Odoo builds those emails, and nowhere else.
- A server already chosen on an email is never overwritten.
- An archived server is ignored, so customers still get their email through the usual server.
- The setting is saved on the company of the website you are configuring, the same company the emails are sent for.
- The sender address stays the one Odoo uses. If your dedicated server only accepts its own address, set **From Filtering** on that server and Odoo adapts the sender as usual.
- Uses Odoo's own back-in-stock feature; nothing is duplicated.

## Technical

- Company field `cl_back_in_stock_mail_server_id`, shown in Website settings.
- Wraps `product.product._send_availability_email()`: Odoo's method runs once per outgoing server (once in total with a single company) and `mail.mail.create()` applies the server only inside it.
- Tests: `odoo -i cl_back_in_stock_mail_server --test-tags /cl_back_in_stock_mail_server`.
- Odoo 18.0 · depends on `website_sale_stock` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
