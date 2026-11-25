# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from . import models


def _cl_set_default_rating_template(env):
    """Select the shipped template on every company that has none yet."""
    template = env.ref('cl_product_rating_notification.mail_template_product_rating',
                       raise_if_not_found=False)
    if template:
        env['res.company'].search([('cl_rating_template_id', '=', False)]).write(
            {'cl_rating_template_id': template.id})
