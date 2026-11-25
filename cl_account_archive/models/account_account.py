# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, models
from odoo.exceptions import UserError


class AccountAccount(models.Model):
    """Archive / Unarchive for the Chart of Accounts.

    Odoo 18 has no ``active`` field on accounts: an account is taken out of
    use with its ``deprecated`` flag, which already keeps it out of account
    pickers and refuses new journal items. This module does not add a second
    flag next to it. "Archived" *is* ``deprecated``: the views present the
    core field under that name and the two actions below set and clear it.
    """
    _inherit = 'account.account'

    def _cl_check_not_used_by_taxes(self):
        """Refuse to archive accounts that a tax still posts to, and say which
        accounts and which taxes (useful when archiving in bulk)."""
        if not self.ids:
            return
        # sudo: an account can be shared with companies the user is not
        # working in at the moment, and their taxes count too.
        lines = self.env['account.tax.repartition.line'].sudo().search(
            [('account_id', 'in', self.ids)])
        if not lines:
            return
        details = []
        for account in lines.account_id:
            taxes = lines.filtered(lambda line: line.account_id == account).tax_id
            details.append("- %s: %s" % (
                account.display_name, ', '.join(taxes.mapped('name'))))
        raise UserError(_(
            "Taxes still post to the accounts below, so they cannot be "
            "archived. Change the distribution of these taxes first.\n\n"
            "%(details)s", details='\n'.join(details)))

    def write(self, vals):
        # Checked here so that every way of archiving gets the same answer:
        # the Archive action, the toggle on the form, an import.
        if vals.get('deprecated'):
            self.filtered(lambda account: not account.deprecated)._cl_check_not_used_by_taxes()
        return super().write(vals)

    def action_archive(self):
        # The generic implementation needs an ``active`` field.
        in_use = self.filtered(lambda account: not account.deprecated)
        if in_use:
            in_use.write({'deprecated': True})
        return True

    def action_unarchive(self):
        archived = self.filtered('deprecated')
        if archived:
            archived.write({'deprecated': False})
        return True
