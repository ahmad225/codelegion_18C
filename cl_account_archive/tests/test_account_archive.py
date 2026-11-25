# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestAccountArchive(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env['account.account'].create({
            'name': 'Archivable', 'code': 'CLARCH1', 'account_type': 'asset_current'})
        cls.account_2 = cls.env['account.account'].create({
            'name': 'Archivable 2', 'code': 'CLARCH2', 'account_type': 'asset_current'})
        # An account the default sale tax posts to.
        cls.tax_account = cls.company_data['default_account_tax_sale'][:1]

    # ------------------------------------------------------------------
    # Archive / unarchive
    # ------------------------------------------------------------------

    def test_archive_sets_the_core_flag(self):
        self.account.action_archive()
        self.assertTrue(self.account.deprecated)

    def test_unarchive_clears_the_core_flag(self):
        self.account.action_archive()
        self.account.action_unarchive()
        self.assertFalse(self.account.deprecated)

    def test_archive_in_bulk_with_mixed_states(self):
        self.account.action_archive()
        accounts = self.account | self.account_2
        accounts.action_archive()
        self.assertEqual(accounts.mapped('deprecated'), [True, True])
        accounts.action_unarchive()
        self.assertEqual(accounts.mapped('deprecated'), [False, False])

    def test_archived_filter_finds_the_account(self):
        self.account.action_archive()
        archived = self.env['account.account'].search([('deprecated', '=', True)])
        self.assertIn(self.account, archived)
        self.assertNotIn(self.account_2, archived)

    def test_archive_needs_account_manager_rights(self):
        bookkeeper = new_test_user(
            self.env, login='cl_bookkeeper',
            groups='base.group_user,account.group_account_invoice')
        with self.assertRaises(AccessError):
            self.account.with_user(bookkeeper).action_archive()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def test_form_toggle_archives(self):
        with Form(self.account) as form:
            form.deprecated = True
        self.assertTrue(self.account.deprecated)

    def test_views_show_the_archived_state(self):
        Account = self.env['account.account']
        form_arch = Account.get_view(
            self.env.ref('account.view_account_form').id, 'form')['arch']
        self.assertIn('web_ribbon', form_arch)
        list_arch = Account.get_view(
            self.env.ref('account.view_account_list').id, 'list')['arch']
        self.assertIn('decoration-muted="deprecated"', list_arch)
        search_arch = Account.get_view(
            self.env.ref('account.view_account_search').id, 'search')['arch']
        self.assertIn('cl_archived_accounts', search_arch)

    # ------------------------------------------------------------------
    # Accounts used by taxes
    # ------------------------------------------------------------------

    def test_archive_blocked_when_used_in_tax(self):
        self.assertTrue(self.tax_account, "The test chart needs a sale tax account")
        tax = self.company_data['default_tax_sale']
        with self.assertRaises(UserError) as error:
            self.tax_account.action_archive()
        # The message names the account and the tax, so that someone
        # archiving in bulk knows what to fix.
        self.assertIn(self.tax_account.display_name, str(error.exception))
        self.assertIn(tax.name, str(error.exception))
        self.assertFalse(self.tax_account.deprecated)

    def test_bulk_archive_blocked_archives_nothing(self):
        accounts = self.account | self.tax_account
        with self.assertRaises(UserError):
            accounts.action_archive()
        self.assertFalse(self.account.deprecated)
        self.assertFalse(self.tax_account.deprecated)

    def test_core_field_blocked_the_same_way(self):
        with self.assertRaises(UserError) as error:
            self.tax_account.write({'deprecated': True})
        self.assertIn(self.tax_account.display_name, str(error.exception))
