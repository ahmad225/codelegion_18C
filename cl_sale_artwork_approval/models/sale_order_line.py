# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    cl_artwork_required = fields.Boolean(related='product_id.cl_artwork_required')
    cl_artwork_partner_id = fields.Many2one(
        'res.partner', related='order_id.partner_id.commercial_partner_id',
        string='Artwork Customer')
    cl_artwork_id = fields.Many2one(
        'cl.artwork', string='Artwork', index='btree_not_null', ondelete='set null', copy=False,
        compute='_compute_cl_artwork_id', store=True, readonly=False, precompute=True,
        domain="[('partner_id', '=', cl_artwork_partner_id), ('product_tmpl_id', '=', product_template_id),"
               " ('state', '!=', 'cancel')]",
        help="The customer's approved artwork for this product is used automatically. "
             "Pick another version if the customer wants it.")
    cl_artwork_state = fields.Selection(related='cl_artwork_id.state', string='Artwork Status')

    @api.depends('product_id', 'order_id.partner_id')
    def _compute_cl_artwork_id(self):
        Artwork = self.env['cl.artwork']
        for line in self:
            current = line.cl_artwork_id
            if line.state not in ('draft', 'sent') and line._origin.id:
                # Confirmed lines keep the artwork production was given.
                line.cl_artwork_id = current
                continue
            if not line.product_id or line.display_type:
                line.cl_artwork_id = False
                continue
            partner = line.order_id.partner_id.commercial_partner_id
            if current and current.sudo().partner_id == partner \
                    and current.sudo()._cl_matches(line.product_id):
                line.cl_artwork_id = current
                continue
            line.cl_artwork_id = Artwork._cl_find_approved(partner, line.product_id, line.company_id)

    # ------------------------------------------------------------------
    # Artwork tab of the order
    # ------------------------------------------------------------------

    def action_cl_open_artwork(self):
        self.ensure_one()
        if not self.cl_artwork_id:
            raise UserError(_("This line has no artwork yet."))
        return self.cl_artwork_id._cl_form_action()

    def action_cl_request_artwork(self):
        """Start the artwork of this line: for its product, its customer and its order."""
        self.ensure_one()
        if not self.product_id or self.display_type:
            raise UserError(_("Artwork can only be requested for a product line."))
        current = self.cl_artwork_id
        if current and current.state != 'cancel':
            # One artwork in progress per line: carry on with it.
            return current._cl_form_action()
        order = self.order_id
        artwork = self.env['cl.artwork'].create({
            'name': _("%s artwork", self.product_id.name),
            'partner_id': order.partner_id.id,
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'cl_sale_order_id': order.id,
            'company_id': order.company_id.id,
            'user_id': (order.user_id or self.env.user).id,
        })
        return artwork._cl_form_action()

    def action_cl_new_artwork_version(self):
        """The customer wants a change: new design started from the approved one, for this order."""
        self.ensure_one()
        if self.cl_artwork_id.state != 'approved':
            raise UserError(_("A new version starts from approved artwork."))
        return self.cl_artwork_id.with_context(
            cl_sale_order_id=self.order_id.id).action_cl_new_version()

    def write(self, vals):
        res = super().write(vals)
        if 'cl_artwork_id' in vals:
            # Manufacturing orders follow their order line: refresh the attached proof.
            productions = self.env['mrp.production'].sudo().search([
                ('state', 'not in', ('done', 'cancel')),
                '|', '|',
                ('sale_line_id', 'in', self.ids),
                ('move_dest_ids.sale_line_id', 'in', self.ids),
                ('procurement_group_id.sale_id', 'in', self.order_id.ids),
            ])
            productions._cl_sync_artwork_attachment()
        return res
