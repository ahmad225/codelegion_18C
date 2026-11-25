# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _cl_back_in_stock_mail_server(self):
        """Outgoing server for this product's back-in-stock emails.

        The product's own company comes first, then the company of the website
        the job runs for (the same website Odoo reads the stock from), then the
        current company: the first one with a usable server wins, so a company
        without its own server follows the shop's.
        An archived server is skipped: Odoo refuses to send through it, and
        the customer would be dropped from the waiting list without an email.
        """
        self.ensure_one()
        companies = (
            self.company_id
            | self.env['website'].get_current_website().company_id
            | self.env.company
        ).sudo()
        servers = companies.mapped('cl_back_in_stock_mail_server_id')
        return servers.filtered('active')[:1]

    def _is_sold_out(self):
        # Only inside _send_availability_email (see below): the job runs once
        # per outgoing server, and each run leaves the products of the other
        # servers to their own run.
        context = self.env.context
        if ('cl_back_in_stock_server_id' in context
                and self._cl_back_in_stock_mail_server().id != context['cl_back_in_stock_server_id']):
            return True
        return super()._is_sold_out()

    def _send_availability_email(self):
        # Keep Odoo's implementation untouched. It handles every waiting
        # product in one loop, so run it once per outgoing server (a single
        # run when only one company is set up) with that server in the
        # context: mail.mail.create() applies it to the emails of that run.
        waiting = self.search([('stock_notification_partner_ids', '!=', False)])
        server_ids = {product._cl_back_in_stock_mail_server().id for product in waiting}
        for server_id in server_ids or {False}:
            super(ProductProduct, self.with_context(
                cl_back_in_stock_server_id=server_id))._send_availability_email()
