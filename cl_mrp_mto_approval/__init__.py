# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from . import models
from . import wizard


def cl_post_init_link_sale_orders(env):
    """Link manufacturing orders that already exist to their sales order, so that
    salespeople can see them. Existing orders are never put on approval."""
    Production = env['mrp.production'].sudo()
    by_order = defaultdict(lambda: Production)
    for production in Production.search([('cl_mto_sale_order_id', '=', False)]):
        order = (
            production.sale_line_id.order_id
            or production.procurement_group_id.sale_id
            or production.move_dest_ids.sale_line_id.order_id
            or production.move_dest_ids.group_id.sale_id
        )[:1]
        if order:
            by_order[order.id] |= production
    for order_id, productions in by_order.items():
        productions.write({'cl_mto_sale_order_id': order_id})
