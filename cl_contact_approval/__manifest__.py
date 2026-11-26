# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
{
    'name': 'Customer Approval',
    'summary': 'New customers must be checked and approved before their sales '
               'orders can be confirmed.',
    'description': """
Customer Approval
=================
Make sure nobody sells to a customer whose details have not been checked.

* Turn it on per company in Sales settings and choose the contact fields that
  must be filled in before a customer can be approved (email, VAT, payment
  terms, ...).
* A new customer starts as Draft. "Send for Approval" checks the mandatory
  fields, lists the missing ones and, when complete, schedules an approval
  activity for every member of the "Approve Customers" group.
* "Approve" and "Reject" are reserved to approvers. The colleague who asked
  for the approval is notified either way, and the approval activities are
  closed.
* "Revoke Approval" lets an approver put an approved customer (and its
  contacts) back in Draft.
* A sales order cannot be confirmed in the back office while its customer is
  not approved; the order and the customer show a banner explaining why.
* Orders the customer confirms online (signature or payment on the portal or
  web shop) are never blocked: the order gets a note and the approvers get an
  activity to review the customer.
* Sales > Orders > Customers to Approve, search filters (Pending Approval,
  Not Approved), a "Send for Approval" list action and an "Approve Customers"
  list action for mass approval, which skips customers with missing fields
  and tells you which ones.

Behaves well:

* Approval belongs to the company (the commercial partner). Its contact
  persons and addresses follow it automatically: approving a company approves
  all its contacts, and an order addressed to a contact of an approved company
  confirms normally.
* Existing contacts are all approved when the module is installed, so no
  current customer is ever blocked. Contacts created while the feature is off
  are approved too.
* Only approvers can approve, and this is checked on the server for every
  create and write (import, RPC, mass edit), not only by hiding buttons.
* A contact person taken out of its company by a non-approver goes back to
  Draft, so a company's approval cannot be borrowed by a new customer.
* Editing an approved customer does not reset its approval; use "Revoke
  Approval" or the chatter history (the status is tracked) if a review is
  needed.
* No new order state and no scheduled job: Odoo's own statuses, buttons and
  rules are untouched.
""",
    'author': 'Code Legion',
    'website': 'https://thecodelegion.com',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['sale', 'mail'],
    'data': [
        'security/cl_contact_approval_security.xml',
        'data/mail_activity_type_data.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'post_init_hook': '_cl_post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
