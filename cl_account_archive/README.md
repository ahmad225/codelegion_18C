# Chart of Accounts Archive (`cl_account_archive`)

Archive and unarchive accounts in the Chart of Accounts — by [Code Legion](https://thecodelegion.com).

## What it does

- **Archive / Unarchive** in the Actions menu of the Chart of Accounts, on one account or on a selection (Account Managers only).
- "Archived" is Odoo's core **Deprecated** flag, shown under a clearer name: the account stays out of account pickers and Odoo refuses new journal items on it.
- On the account form: an **Archived** ribbon and an **Archived** toggle.
- In the list: archived accounts are **greyed out**, with an **Archived** column.
- An **Archived** search filter to review or restore.
- Archiving is **blocked** while a tax still posts to the account; the message lists each account and the taxes that use it, so a bulk archive tells you what to fix.

## Behaves well

- **No second flag.** The app adds no field of its own next to *Deprecated*, so there is nothing that can get out of step with it: imports, duplicated accounts and other apps that deprecate an account are all "archived" in exactly the same sense.
- The list's Archived column is **read-only** (no accidental one-click archive in the editable list); archive from the Actions menu or the form.
- The tax check applies to every way of archiving: the action, the form toggle, an import.
- The **Archived** filter sits next to the core **Active Account** filter, which is on by default. Filters of one group add up: with both ticked you see every account, untick *Active Account* to see archived accounts only.

## Technical

- No new field or model. `account.account.action_archive()` / `action_unarchive()` set and clear `deprecated`; `write()` runs the tax check; two server actions bound to the list and form, restricted to `account.group_account_manager` (changing accounts needs that group's access rights in any case).
- Tests: `odoo -i cl_account_archive --test-tags /cl_account_archive`.
- Odoo 18.0 · depends on `account` · LGPL-3.

---
© Code Legion — https://thecodelegion.com
