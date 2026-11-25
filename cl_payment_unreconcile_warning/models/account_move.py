# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _cl_unreconcile_label(self):
        """How this journal entry is called in the confirmation message, e.g.
        'Payment PBNK1/2026/00001' or 'Credit Note RINV/2026/00003'."""
        self.ensure_one()
        payment = self.origin_payment_id or self.line_ids.payment_id[:1]
        if payment:
            return _("Payment %(name)s", name=payment.name or self.name or self.ref or '-')
        return "%s %s" % (self.type_name, self.name or self.ref or '-')

    def cl_unreconcile_warning_message(self, partial_id):
        """Return the confirmation message shown before a reconciliation is
        removed from the payment widget.

        ``self`` is the document on screen (invoice, bill, credit note or
        receipt). The entry on the other side of the partial is what gets
        removed from it: a payment, a credit note, a bank transaction...
        """
        self.ensure_one()
        # The names and the amount are the ones the payment widget already
        # shows, and the widget reads them with sudo (the other entry can
        # belong to another branch). Do the same once the user is known to be
        # allowed to read the document itself.
        self.check_access('read')
        partial = self.env['account.partial.reconcile'].sudo().browse(partial_id).exists()
        if not partial:
            return {'message': _(
                "This reconciliation has already been removed. Confirm to "
                "refresh the document.")}
        document = self.sudo()
        lines = partial.debit_move_id | partial.credit_move_id
        document_line = lines.filtered(lambda line: line.move_id == document)[:1]
        if not document_line:
            return {'message': _("Are you sure you want to remove this reconciliation?")}
        counterpart = (lines.move_id - document)[:1] or document
        if document_line == partial.debit_move_id:
            amount, currency = partial.debit_amount_currency, partial.debit_currency_id
        else:
            amount, currency = partial.credit_amount_currency, partial.credit_currency_id
        return {'message': _(
            "Remove %(counterpart)s (%(amount)s) from %(document)s?\n\n"
            "%(document)s will have this amount due again. %(counterpart)s is "
            "not cancelled: it stays posted and can be matched again later.",
            counterpart=counterpart._cl_unreconcile_label(),
            amount=currency.format(amount) if currency else amount,
            document=document._cl_unreconcile_label(),
        )}
