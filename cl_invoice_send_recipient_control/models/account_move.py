# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        """Odoo works out who is notified (chosen recipients + followers of the
        subtype, minus the author...). When an invoice email is being sent
        with "skip followers" on, keep from that result only the partners in
        the list set by ``account.move.send._send_mail``. An empty list means
        nobody; no list at all (chatter, other emails) changes nothing."""
        recipients = super()._notify_get_recipients(message, msg_vals, **kwargs)
        only_partner_ids = self.env.context.get('cl_invoice_email_only_partner_ids')
        if only_partner_ids is None:
            return recipients
        keep = set(only_partner_ids)
        return [recipient for recipient in recipients if recipient['id'] in keep]
