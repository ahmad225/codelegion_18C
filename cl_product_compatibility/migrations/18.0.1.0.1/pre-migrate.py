# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Upgrade from a version installed before 18.0.1.0.1.

Fields, models, views and XML ids of this module were renamed in that version.

* Views: Odoo keeps applying the old views of a module until the very end of
  an upgrade, so an old view that names a removed field would stop it. Every
  view of the module is removed first; the data files create them again.
* Protected records (noupdate): scheduled actions, record rules and email
  templates are never rewritten by an upgrade, so the old ones would keep
  calling code that is gone. They are removed too and created again from the
  data files when still shipped. Changes made to them by hand are lost once.

Nothing is deleted that another record still points to: a refused DELETE is
logged as an error even when it is caught.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'cl_product_compatibility'
PROTECTED = {'ir.cron': 'ir_cron', 'ir.rule': 'ir_rule', 'mail.template': 'mail_template'}


def _in_use(cr, table, record_id):
    """Whether a row of another table would block the deletion."""
    cr.execute("""
        SELECT cl.relname, att.attname
          FROM pg_constraint con
          JOIN pg_class cl ON cl.oid = con.conrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
         WHERE con.contype = 'f'
           AND con.confrelid = %s::regclass
           AND con.confdeltype IN ('r', 'a')
           AND array_length(con.conkey, 1) = 1
    """, [table])
    for ref_table, column in cr.fetchall():
        cr.execute('SELECT 1 FROM "%s" WHERE "%s" = %%s LIMIT 1' % (ref_table, column), [record_id])
        if cr.fetchone():
            return True
    return False


def _delete(cr, model, table, record_id):
    if _in_use(cr, table, record_id):
        _logger.info("%s: %s %s is still in use and was kept", MODULE, model, record_id)
        return False
    cr.execute("DELETE FROM ir_model_data WHERE model = %s AND res_id = %s", [model, record_id])
    cr.execute('DELETE FROM "%s" WHERE id = %%s' % table, [record_id])
    return True


def migrate(cr, version):
    if not version:
        return
    # --- views, children before parents ---
    cr.execute("""
        WITH RECURSIVE tree AS (
            SELECT v.id, 0 AS depth
              FROM ir_ui_view v
             WHERE v.id IN (SELECT res_id FROM ir_model_data
                             WHERE module = %s AND model = 'ir.ui.view')
                OR left(v.key, %s) = %s
            UNION ALL
            SELECT c.id, t.depth + 1
              FROM ir_ui_view c
              JOIN tree t ON c.inherit_id = t.id
        )
        SELECT id FROM tree GROUP BY id ORDER BY max(depth) DESC, id DESC
    """, [MODULE, len(MODULE) + 1, MODULE + '.'])
    views = sum(_delete(cr, 'ir.ui.view', 'ir_ui_view', row[0]) for row in cr.fetchall())

    # --- protected records ---
    cr.execute("""
        SELECT model, res_id FROM ir_model_data
         WHERE module = %s AND noupdate AND model IN %s
         ORDER BY id
    """, [MODULE, tuple(PROTECTED)])
    records = 0
    for model, record_id in cr.fetchall():
        table = PROTECTED[model]
        cr.execute('SELECT 1 FROM "%s" WHERE id = %%s' % table, [record_id])
        if not cr.fetchone():
            cr.execute("DELETE FROM ir_model_data WHERE model = %s AND res_id = %s", [model, record_id])
            continue
        action_id = None
        if model == 'ir.cron':
            cr.execute("SELECT ir_actions_server_id FROM ir_cron WHERE id = %s", [record_id])
            action_id = cr.fetchone()[0]
        if _delete(cr, model, table, record_id):
            records += 1
            if action_id:  # the server action a scheduled job runs
                _delete(cr, 'ir.actions.server', 'ir_act_server', action_id)
    _logger.info("%s: %s view(s) and %s protected record(s) removed before the upgrade",
                 MODULE, views, records)
