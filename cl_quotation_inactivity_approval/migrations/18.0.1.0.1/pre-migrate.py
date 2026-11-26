# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Upgrade from a version installed before 18.0.1.0.1.

Fields, views and XML ids of this module were renamed. Odoo keeps applying the
old views of a module until the very end of an upgrade, so an old view that
names a removed field would stop the upgrade. Every view of this module is
therefore removed first; the data files create them again right after.
"""
import logging

_logger = logging.getLogger(__name__)

MODULE = 'cl_quotation_inactivity_approval'


def migrate(cr, version):
    if not version:
        return
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
    view_ids = [row[0] for row in cr.fetchall()]
    removed = 0
    for view_id in view_ids:
        try:
            with cr.savepoint():
                cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s", [view_id])
                cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [view_id])
                removed += 1
        except Exception as error:  # still referenced: left for the standard cleanup
            _logger.warning("%s: view %s kept during the upgrade: %s", MODULE, view_id, error)
    _logger.info("%s: %s old view(s) removed before the upgrade", MODULE, removed)
