# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ARTWORK_READERS = ('sales_team.group_sale_salesman,mrp.group_mrp_user,'
                   'cl_sale_artwork_approval.group_cl_artwork_designer')


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    cl_artwork_id = fields.Many2one(
        'cl.artwork', string='Artwork', index='btree_not_null', ondelete='set null', copy=False,
        compute='_compute_cl_artwork_id', store=True, readonly=False,
        domain="[('product_tmpl_id', '=', product_tmpl_id), ('state', '=', 'approved')]",
        help='The artwork of the sales order line this order is made for.')
    # Not computed as superuser: the files stay readable only by users who can read the artwork.
    cl_artwork_state = fields.Selection(
        related='cl_artwork_id.state', string='Artwork Status', compute_sudo=False,
        groups=ARTWORK_READERS)
    cl_artwork_proof_file = fields.Binary(
        related='cl_artwork_id.cl_proof_file', string='Approved Proof', compute_sudo=False,
        groups=ARTWORK_READERS)
    cl_artwork_proof_filename = fields.Char(
        related='cl_artwork_id.cl_proof_filename', compute_sudo=False, groups=ARTWORK_READERS)
    cl_artwork_proof_preview = fields.Image(
        related='cl_artwork_id.cl_proof_preview', string='Proof Preview', compute_sudo=False,
        groups=ARTWORK_READERS)
    cl_artwork_attachment_id = fields.Many2one(
        'ir.attachment', string='Attached Proof', readonly=True, copy=False, ondelete='set null')
    cl_artwork_attached_id = fields.Many2one(
        'cl.artwork', string='Attached Artwork', readonly=True, copy=False, ondelete='set null')

    def _cl_get_sale_line(self):
        """The sales order line this order is made for, if any."""
        self.ensure_one()
        line = self.sale_line_id or self.move_dest_ids.sale_line_id[:1]
        if not line and self.procurement_group_id.sale_id:
            line = self.procurement_group_id.sale_id.order_line.filtered(
                lambda l: l.product_id == self.product_id)[:1]
        return line

    @api.depends('sale_line_id.cl_artwork_id', 'move_dest_ids.sale_line_id.cl_artwork_id',
                 'procurement_group_id.sale_id.order_line.cl_artwork_id', 'product_id')
    def _compute_cl_artwork_id(self):
        for production in self:
            line = production.sudo()._cl_get_sale_line()
            if line:
                production.cl_artwork_id = line.cl_artwork_id
            elif production.cl_artwork_id and production.cl_artwork_id.product_tmpl_id != production.product_tmpl_id:
                production.cl_artwork_id = False
            else:
                production.cl_artwork_id = production.cl_artwork_id

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        productions._cl_sync_artwork_attachment()
        return productions

    def write(self, vals):
        res = super().write(vals)
        if 'cl_artwork_id' in vals or 'move_dest_ids' in vals or 'sale_line_id' in vals:
            self._cl_sync_artwork_attachment()
        return res

    def action_confirm(self):
        res = super().action_confirm()
        self._cl_sync_artwork_attachment()
        return res

    def _cl_sync_artwork_attachment(self):
        """Keep one copy of the approved proof attached to open orders. System bookkeeping:
        done as superuser once the artwork itself has been approved by a sales user."""
        Attachment = self.env['ir.attachment'].sudo()
        for production in self.sudo():
            if production.state in ('done', 'cancel'):
                continue
            artwork = production.cl_artwork_id
            wanted = artwork if (
                artwork and artwork.state == 'approved' and artwork.cl_proof_file
                and production.company_id.cl_artwork_attach_production) else artwork.browse()
            if production.cl_artwork_attached_id == wanted and (
                    production.cl_artwork_attachment_id or not wanted):
                continue
            production.cl_artwork_attachment_id.unlink()
            attachment = Attachment
            if wanted:
                attachment = Attachment.create({
                    'name': _('Artwork %(artwork)s - %(file)s', artwork=wanted.display_name,
                              file=wanted.cl_proof_filename or 'proof'),
                    'datas': wanted.with_context(bin_size=False).cl_proof_file,
                    'res_model': 'mrp.production',
                    'res_id': production.id,
                })
            production.write({
                'cl_artwork_attachment_id': attachment.id,
                'cl_artwork_attached_id': wanted.id,
            })

    def _cl_check_artwork_ready(self):
        if self.env.su:
            return
        for production in self:
            if not production.company_id.cl_artwork_block_production \
                    or not production.product_id.cl_artwork_required \
                    or not production.sudo()._cl_get_sale_line():
                continue
            if production.sudo().cl_artwork_id.state != 'approved':
                raise UserError(_(
                    "%(production)s cannot start: the artwork of %(product)s is not approved yet.",
                    production=production.name, product=production.product_id.display_name))

    def action_start(self):
        self._cl_check_artwork_ready()
        return super().action_start()

    def button_mark_done(self):
        self._cl_check_artwork_ready()
        return super().button_mark_done()
