# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Customer Statements',
    'summary': 'Customer account statements and overdue statements: PDF, '
               'email, customer portal and monthly automatic sending.',
    'description': """
Customer Statements
===================
Statements of account for your customers, worked out live from the posted
receivable entries in Accounting.

* **Account statement** for any period: opening balance, every invoice, credit
  note, payment and adjustment with debit, credit and running balance, and the
  closing balance.
* **Overdue statement**: open items past their due date with days overdue.
* **Ageing** (not due / 1-30 / 31-60 / 61-90 / over 90 days) by due date.
* **Print or email** for one or many customers; the email carries the PDF.
* **Statement recipients** per customer (e.g. their accounts payable contact).
* **Customer portal** page with a date filter and PDF download.
* **Monthly automatic sending** of last month's statement, per company, with a
  log of every statement sent.

Behaves well:

* Nothing is stored per customer - every statement is built from the ledger
  when it is asked for, so it is never stale.
* PDFs are attached to the email and never published as public files.
* Portal customers only ever see their own statement.
* Amounts are in company currency; ageing follows the due date.
* Statements and emails are worded in each customer's language.
* Automatic sending is idempotent: each customer gets one statement per
  period. Customers are handled and saved one by one, so a long run that is
  interrupted carries on where it stopped.
* A customer without an email address is logged as "Not Sent", not silently
  skipped, and gets the statement automatically once an address is filled in;
  a statement that failed for a technical reason is tried again the next day.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['account', 'portal'],
    'data': [
        'security/cl_customer_statement_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'report/report_customer_statement.xml',
        'wizard/cl_customer_statement_wizard_views.xml',
        'views/cl_customer_statement_log_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
