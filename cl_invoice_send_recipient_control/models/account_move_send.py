# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        """Every invoice email of the standard sending engine goes through
        here (Send wizard, background batch, automatic flows) and ``kwargs``
        holds the recipients that were really chosen. When the company wants
        followers left out, hand that list to the notification step."""
        if move.company_id.cl_invoice_email_skip_followers:
            chosen = tuple(kwargs.get('partner_ids') or ())
            move = move.with_context(cl_invoice_email_only_partner_ids=chosen)
        return super()._send_mail(move, mail_template, **kwargs)
