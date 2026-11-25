# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    cl_queued_on_delivery = fields.Boolean(
        string='Queued for Sending on Delivery', readonly=True, copy=False,
        help="Set when this invoice was handed to the automatic sending on "
             "delivery, so it is never sent a second time.")

    # ------------------------------------------------------------------
    # Which invoices
    # ------------------------------------------------------------------

    def _cl_delivery_auto_send_candidates(self):
        """Posted customer invoices of a company that uses the feature, that
        nobody sent yet (by hand, through another automatic flow or through
        this one) and that are not already waiting in the sending queue."""
        return self.filtered(
            lambda move: move.move_type == 'out_invoice'
            and move.state == 'posted'
            and move.company_id.cl_send_invoices_when_delivered
            and not move.cl_queued_on_delivery
            and not move.is_move_sent
            and not move.sending_data
            and move._is_ready_to_be_sent())

    def _cl_validated_delivery(self):
        """A validated outgoing delivery of the sale order(s) this invoice
        bills, if there is one."""
        self.ensure_one()
        pickings = self.line_ids.sale_line_ids.order_id.picking_ids
        return pickings.filtered(
            lambda picking: picking.state == 'done'
            and picking.picking_type_id.code == 'outgoing')[:1]

    def _cl_has_email_recipient(self):
        """Mirror of the test Odoo makes right before emailing an invoice:
        without a customer address and without any recipient coming from the
        email template, it skips the email without saying anything."""
        self.ensure_one()
        if self.partner_id.email:
            return True
        Send = self.env['account.move.send']
        template = Send._get_default_mail_template_id(self)
        if not template:
            return False
        lang = Send._get_default_mail_lang(self, template)
        return bool(Send._get_default_mail_partner_ids(self, template, lang))

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def _cl_queue_delivery_auto_send(self, delivery=None):
        """Hand the invoices that qualify to Odoo's own background sending
        (the queue behind "Send" on several invoices). Nothing is rendered or
        emailed in the current transaction, so validating a delivery is never
        slowed down or blocked by an invoice that cannot be sent.

        This is a company automation: it runs with sudo so that a warehouse
        user without any accounting right can still validate a delivery.

        :param delivery: the ``stock.picking`` to name in the invoice note;
            looked up per invoice when not given.
        :return: the invoices that were queued.
        """
        Send = self.env['account.move.send'].sudo()
        queued = self.env['account.move'].sudo()
        for invoice in self.sudo()._cl_delivery_auto_send_candidates():
            by_email = Send._get_default_sending_method(invoice) == 'email'
            if by_email and not invoice._cl_has_email_recipient():
                invoice._message_log(body=_(
                    "This invoice was not emailed automatically on delivery: "
                    "%(customer)s has no email address. Send it manually once "
                    "the address is known.",
                    customer=invoice.partner_id.display_name))
                continue
            picking = delivery or invoice._cl_validated_delivery()
            invoice._message_log(body=_(
                "Queued to be sent to the customer automatically: delivery "
                "%(delivery)s is validated.", delivery=picking.name or ''))
            queued |= invoice
        if queued:
            queued.write({
                'sending_data': {
                    'author_user_id': self.env.user.id,
                    'author_partner_id': self.env.user.partner_id.id,
                },
                'cl_queued_on_delivery': True,
                # Same convention as the core automatic flows (online payment,
                # subscriptions): they skip invoices already marked as sent,
                # so the customer never gets the same invoice twice.
                'is_move_sent': True,
            })
            cron = self.env.ref(
                'account.ir_cron_account_move_send', raise_if_not_found=False)
            if cron:
                cron.sudo()._trigger()
        return queued

    def _post(self, soft=True):
        # An invoice posted after the goods have left (invoicing policy
        # "delivered quantities") is sent as soon as it is posted.
        posted = super()._post(soft=soft)
        for invoice in posted.sudo()._cl_delivery_auto_send_candidates():
            delivery = invoice._cl_validated_delivery()
            if delivery:
                invoice._cl_queue_delivery_auto_send(delivery=delivery)
        return posted
