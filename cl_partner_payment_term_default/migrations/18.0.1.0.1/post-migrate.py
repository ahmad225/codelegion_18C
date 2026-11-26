# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Upgrade from a version installed before 18.0.1.0.1.

Odoo removes the records a module no longer ships, except those protected
from updates (noupdate). Old record rules, scheduled actions, server actions
and email templates of this module can name fields or methods that are gone,
so the ones no longer shipped are removed here.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODULE = 'cl_partner_payment_term_default'
MODELS = ('ir.rule', 'ir.cron', 'ir.actions.server', 'mail.template')


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    loaded = getattr(env.registry, 'loaded_xmlids', None)
    prefix = MODULE + '.'
    if not loaded or not any(xmlid.startswith(prefix) for xmlid in loaded):
        return  # cannot tell what is still shipped: remove nothing
    stale = env['ir.model.data'].search([
        ('module', '=', MODULE), ('noupdate', '=', True), ('model', 'in', MODELS),
    ]).filtered(lambda data: prefix + data.name not in loaded)
    for data in stale:
        name = prefix + data.name
        try:
            with cr.savepoint():
                if data.model in env:
                    env[data.model].browse(data.res_id).exists().unlink()
                data.exists().unlink()
                _logger.info("%s: removed %s, no longer shipped", MODULE, name)
        except Exception as error:
            _logger.warning("%s: %s kept: %s", MODULE, name, error)
