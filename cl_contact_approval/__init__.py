# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from . import models


def _cl_post_init_hook(env):
    """Approve every contact that exists at install time.

    The new column is filled with its default ('draft') when it is created;
    one UPDATE turns all existing contacts into approved customers so that
    switching the feature on never blocks a current customer. Plain SQL on
    purpose: no tracking message or activity per contact.
    """
    env.cr.execute("""
        UPDATE res_partner
           SET cl_approval_state = 'approved'
         WHERE cl_approval_state IS DISTINCT FROM 'approved'
    """)
    env['res.partner'].invalidate_model(['cl_approval_state'])
