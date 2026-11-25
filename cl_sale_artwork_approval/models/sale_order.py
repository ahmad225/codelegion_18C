# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

SALES_GROUP = 'sales_team.group_sale_salesman'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_artwork_ids = fields.One2many(
        'cl.artwork', 'cl_sale_order_id', string='Artwork Requests', groups=SALES_GROUP)
    cl_reused_artwork_ids = fields.Many2many(
        'cl.artwork', string='Reused Artwork', compute='_compute_cl_artwork_info', groups=SALES_GROUP)
    cl_artwork_count = fields.Integer(
        string='Artworks', compute='_compute_cl_artwork_info', groups=SALES_GROUP)
    cl_artwork_status = fields.Selection([
        ('none', 'Not Needed'),
        ('missing', 'Missing'),
        ('approved', 'Approved'),
    ], string='Artwork', compute='_compute_cl_artwork_info', groups=SALES_GROUP,
        help='Whether every line whose product requires artwork has approved artwork.')
    cl_artwork_missing = fields.Char(
        string='Products Waiting for Artwork', compute='_compute_cl_artwork_info', groups=SALES_GROUP)
    # The Artwork tab works line by line: what each line needs and what it has.
    cl_artwork_line_ids = fields.Many2many(
        'sale.order.line', string='Lines with Artwork', compute='_compute_cl_artwork_line_ids',
        groups=SALES_GROUP)

    @api.depends('order_line.product_id', 'order_line.cl_artwork_id')
    def _compute_cl_artwork_line_ids(self):
        for order in self:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id
                and (l.product_id.cl_artwork_required or l.cl_artwork_id))
            # Saved lines only: the buttons of the tab act on stored lines.
            order.cl_artwork_line_ids = lines._origin

    @api.depends('order_line.cl_artwork_id', 'order_line.cl_artwork_id.state',
                 'order_line.product_id', 'cl_artwork_ids')
    def _compute_cl_artwork_info(self):
        for order in self:
            used = order.order_line.cl_artwork_id
            order.cl_reused_artwork_ids = used - order.cl_artwork_ids
            order.cl_artwork_count = len(used | order.cl_artwork_ids)
            required = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id.cl_artwork_required)
            missing = order._cl_lines_missing_artwork()
            order.cl_artwork_missing = ', '.join(missing.product_id.mapped('display_name'))
            if not required:
                order.cl_artwork_status = 'none'
            else:
                order.cl_artwork_status = 'missing' if missing else 'approved'

    def _cl_lines_missing_artwork(self):
        return self.order_line.filtered(
            lambda l: not l.display_type and l.product_id.cl_artwork_required
            and l.sudo().cl_artwork_id.state != 'approved')

    # ------------------------------------------------------------------
    # confirmation
    # ------------------------------------------------------------------

    def action_confirm(self):
        # Staff are blocked; customers accepting or paying online (portal, public, sudo) are not.
        interactive = not self.env.su and self.env.user._is_internal()
        for order in self.filtered(lambda o: o.company_id.cl_artwork_block_sale):
            missing = order._cl_lines_missing_artwork()
            if not missing:
                continue
            products = ', '.join(missing.product_id.mapped('display_name'))
            if interactive:
                raise UserError(_(
                    "%(order)s cannot be confirmed: the artwork of %(products)s is not approved yet.",
                    order=order.name, products=products))
            order.sudo()._message_log(
                body=_("Confirmed by the customer while the artwork of %s is not approved yet.", products))
        return super().action_confirm()

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if 'partner_id' in vals:
            for order in self:
                pending = order.sudo().cl_artwork_ids.filtered(
                    lambda a: a.state not in ('approved', 'cancel'))
                if pending:
                    pending.write({'partner_id': order.partner_id.commercial_partner_id.id})
        return res

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def action_cl_view_artworks(self):
        self.ensure_one()
        artworks = self.order_line.cl_artwork_id | self.cl_artwork_ids
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_sale_artwork_approval.action_cl_artwork')
        action.update({
            'domain': [('id', 'in', artworks.ids)],
            'context': {
                'default_cl_sale_order_id': self.id,
                'default_partner_id': self.partner_id.commercial_partner_id.id,
                'default_company_id': self.company_id.id,
                'default_user_id': (self.user_id or self.env.user).id,
                'cl_sale_order_id': self.id,
            },
        })
        if len(artworks) == 1:
            action.update({'views': [(False, 'form')], 'res_id': artworks.id})
        return action
