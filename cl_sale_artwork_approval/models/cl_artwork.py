# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SALES_GROUP = 'sales_team.group_sale_salesman'
DESIGNER_GROUP = 'cl_sale_artwork_approval.group_cl_artwork_designer'
MANAGER_GROUP = 'cl_sale_artwork_approval.group_cl_artwork_manager'
DESIGN_ACTIVITY = 'cl_sale_artwork_approval.mail_act_cl_artwork_design'
REVIEW_ACTIVITY = 'cl_sale_artwork_approval.mail_act_cl_artwork_review'

# Only the workflow buttons may change these.
WORKFLOW_FIELDS = {
    'state', 'cl_version', 'cl_proof_count', 'cl_rework_note',
    'cl_approved_by_id', 'cl_approved_date',
}
# The design itself: frozen once approved (make a new version instead).
DESIGN_FIELDS = {
    'partner_id', 'product_tmpl_id', 'product_id', 'company_id',
    'cl_source_file', 'cl_source_filename',
    'cl_proof_file', 'cl_proof_filename', 'cl_proof_preview',
}
PROOF_FIELDS = {'cl_proof_file', 'cl_proof_filename', 'cl_proof_preview'}
# What a designer without sales rights may change.
DESIGNER_FIELDS = PROOF_FIELDS | {'cl_designer_note'}


class ClArtwork(models.Model):
    _name = 'cl.artwork'
    _description = 'Customer Artwork'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True
    _rec_names_search = ['name', 'partner_id', 'product_tmpl_id']

    name = fields.Char(string='Title', required=True, tracking=True,
                       default=lambda self: _('Logo'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('design', 'With Designer'),
        ('review', 'Proof Ready'),
        ('rework', 'Rework Requested'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', required=True, copy=False, readonly=True,
        index=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True, tracking=True,
        ondelete='restrict',
        help='Artwork belongs to the customer company; its contacts use it too.')
    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', required=True, index=True, tracking=True,
        ondelete='restrict', check_company=True)
    product_id = fields.Many2one(
        'product.product', string='Variant', index=True, tracking=True, ondelete='restrict',
        check_company=True, domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        help='Leave empty to use this artwork for every variant of the product.')
    user_id = fields.Many2one(
        'res.users', string='Salesperson', tracking=True, domain=[('share', '=', False)],
        default=lambda self: self.env.user,
        help='Reviews the proofs and approves the artwork.')
    cl_designer_id = fields.Many2one(
        'res.users', string='Designer', tracking=True,
        domain=lambda self: self._cl_designer_domain())
    cl_sale_order_id = fields.Many2one(
        'sale.order', string='Requested on', index='btree_not_null', ondelete='set null',
        copy=False, check_company=True)
    cl_version = fields.Integer(string='Version', readonly=True, copy=False)
    cl_brief = fields.Text(string='Design Brief',
                           help='Instructions for the designer: colours, position, size, wording...')
    cl_source_file = fields.Binary(string='Customer Logo', attachment=True)
    cl_source_filename = fields.Char(string='Customer Logo Filename')
    cl_proof_file = fields.Binary(string='Proof', attachment=True, copy=False,
                                  help='The design production uses once it is approved.')
    cl_proof_filename = fields.Char(string='Proof Filename', copy=False)
    cl_proof_preview = fields.Image(string='Proof Preview', max_width=1024, max_height=1024,
                                    copy=False, help='Optional picture of the proof (PNG/JPG).')
    cl_designer_note = fields.Text(string='Designer Notes', copy=False)
    cl_rework_note = fields.Text(string='Last Rework Request', readonly=True, copy=False)
    cl_proof_count = fields.Integer(string='Proofs Submitted', readonly=True, copy=False)
    cl_approved_by_id = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False)
    cl_approved_date = fields.Datetime(string='Approved on', readonly=True, copy=False)
    cl_sale_line_ids = fields.One2many('sale.order.line', 'cl_artwork_id', string='Order Lines')
    cl_sale_order_count = fields.Integer(compute='_compute_cl_sale_order_count', string='Orders')
    cl_production_count = fields.Integer(compute='_compute_cl_production_count',
                                         string='Manufacturing Orders')
    cl_is_sales_user = fields.Boolean(compute='_compute_cl_is_sales_user')

    @api.model
    def _cl_designer_domain(self):
        group = self.env.ref(DESIGNER_GROUP, raise_if_not_found=False)
        domain = [('share', '=', False)]
        if group:
            domain.append(('groups_id', 'in', group.ids))
        return domain

    # ------------------------------------------------------------------
    # computes and constraints
    # ------------------------------------------------------------------

    @api.depends('name', 'cl_version')
    def _compute_display_name(self):
        for artwork in self:
            artwork.display_name = (
                _('%(name)s (v%(version)s)', name=artwork.name, version=artwork.cl_version)
                if artwork.cl_version else artwork.name)

    @api.depends('cl_sale_line_ids.order_id')
    def _compute_cl_sale_order_count(self):
        for artwork in self:
            artwork.cl_sale_order_count = len(artwork.sudo().cl_sale_line_ids.order_id)

    def _compute_cl_production_count(self):
        counts = dict(self.env['mrp.production'].sudo()._read_group(
            [('cl_artwork_id', 'in', self.ids)], ['cl_artwork_id'], ['__count']))
        for artwork in self:
            artwork.cl_production_count = counts.get(artwork, 0)

    @api.depends_context('uid')
    def _compute_cl_is_sales_user(self):
        is_sales_user = self._cl_is_sales_user()
        for artwork in self:
            artwork.cl_is_sales_user = is_sales_user

    @api.constrains('product_id', 'product_tmpl_id')
    def _check_cl_variant(self):
        for artwork in self:
            if artwork.product_id and artwork.product_id.product_tmpl_id != artwork.product_tmpl_id:
                raise ValidationError(_("The variant %s does not belong to the product of the artwork.",
                                        artwork.product_id.display_name))

    @api.onchange('product_tmpl_id')
    def _onchange_cl_product_tmpl_id(self):
        if self.product_id and self.product_id.product_tmpl_id != self.product_tmpl_id:
            self.product_id = False

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        Partner = self.env['res.partner']
        for vals in vals_list:
            if not self.env.su and WORKFLOW_FIELDS.intersection(vals):
                raise UserError(_("The status of an artwork is set by its buttons only."))
            if vals.get('partner_id'):
                vals['partner_id'] = Partner.browse(vals['partner_id']).commercial_partner_id.id
            if vals.get('cl_sale_order_id') and not vals.get('company_id'):
                vals['company_id'] = self.env['sale.order'].browse(vals['cl_sale_order_id']).company_id.id
        artworks = super().create(vals_list)
        for artwork in artworks:
            artwork.sudo().cl_version = artwork._cl_next_version()
        artworks._cl_link_sale_lines()
        return artworks

    def write(self, vals):
        if not self.env.su:
            self._cl_check_write(vals)
        if vals.get('partner_id'):
            vals = dict(vals, partner_id=self.env['res.partner'].browse(
                vals['partner_id']).commercial_partner_id.id)
        reassign = self.browse()
        if 'cl_designer_id' in vals:
            reassign = self.filtered(lambda a: a.state in ('design', 'rework')
                                     and a.cl_designer_id.id != vals['cl_designer_id'])
            reassign.sudo().activity_unlink([DESIGN_ACTIVITY])
        res = super().write(vals)
        for artwork in reassign.filtered('cl_designer_id'):
            artwork._cl_schedule_design_activity(artwork.cl_rework_note or artwork.cl_brief)
        if {'product_tmpl_id', 'product_id', 'cl_sale_order_id', 'partner_id'}.intersection(vals):
            self._cl_link_sale_lines()
        return res

    def _cl_check_write(self, vals):
        fnames = set(vals)
        if WORKFLOW_FIELDS & fnames:
            raise UserError(_("The status of an artwork is set by its buttons only."))
        if not self._cl_is_sales_user():
            if fnames - DESIGNER_FIELDS:
                raise UserError(_("Designers can only upload the proof and write designer notes."))
        if DESIGN_FIELDS & fnames:
            frozen = self.filtered(lambda a: a.state == 'approved')
            if frozen:
                raise UserError(_(
                    "%s is approved and cannot be changed. Create a new version instead.",
                    ', '.join(frozen.mapped('display_name'))))
        if PROOF_FIELDS & fnames:
            waiting = self.filtered(lambda a: a.state == 'review')
            if waiting:
                raise UserError(_(
                    "The proof of %s is waiting for review. Request a rework to upload another one.",
                    ', '.join(waiting.mapped('display_name'))))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_cl_used(self):
        for artwork in self:
            if artwork.state == 'approved':
                raise UserError(_("%s is approved and cannot be deleted. Archive it instead.",
                                  artwork.display_name))
            if artwork.sudo().cl_sale_line_ids.filtered(lambda l: l.state == 'sale'):
                raise UserError(_("%s is used on confirmed orders and cannot be deleted. "
                                  "Cancel or archive it instead.", artwork.display_name))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _cl_is_sales_user(self):
        return self.env.su or self.env.user.has_group(SALES_GROUP)

    def _cl_check_sales_user(self):
        if not self._cl_is_sales_user():
            raise UserError(_("Only sales users can send, review or approve artwork."))

    def _cl_next_version(self):
        self.ensure_one()
        siblings = self.sudo().with_context(active_test=False).search([
            ('partner_id', '=', self.partner_id.id),
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', self.id),
        ])
        return max(siblings.mapped('cl_version') or [0]) + 1

    def _cl_matches(self, product):
        """Whether this artwork can be used for ``product`` (a product.product)."""
        self.ensure_one()
        return (product.product_tmpl_id == self.product_tmpl_id
                and (not self.product_id or self.product_id == product))

    @api.model
    def _cl_find_approved(self, partner, product, company):
        """The approved artwork to reuse for this customer and product: artwork of the variant
        first, then of the whole product; the most recently approved one wins."""
        commercial = partner.commercial_partner_id
        if not commercial or not product:
            return self.browse()
        candidates = self.sudo().search([
            ('partner_id', '=', commercial.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', 'in', [False, product.id]),
            ('company_id', '=', company.id),
            ('state', '=', 'approved'),
        ])
        if not candidates:
            return self.browse()
        best = candidates.sorted(
            lambda a: (bool(a.product_id), a.cl_approved_date or datetime.min, a.id), reverse=True)[:1]
        return self.browse(best.id)

    def _cl_link_sale_lines(self):
        """Artwork requested on an order is used by that order's lines of the same product."""
        for artwork in self.sudo().filtered(lambda a: a.cl_sale_order_id and a.state != 'cancel'):
            lines = artwork.cl_sale_order_id.order_line.filtered(
                lambda l: l.product_id and artwork._cl_matches(l.product_id))
            lines = lines.filtered(lambda l: l.cl_artwork_id != artwork)
            if lines:
                lines.write({'cl_artwork_id': artwork.id})

    def _cl_assign_open_lines(self):
        """Quotations of the customer still waiting for this product's artwork get it now."""
        Line = self.env['sale.order.line'].sudo()
        for artwork in self.sudo():
            domain = [
                ('order_id.state', 'in', ('draft', 'sent')),
                ('order_id.partner_id', 'child_of', artwork.partner_id.id),
                ('product_id.product_tmpl_id', '=', artwork.product_tmpl_id.id),
                ('company_id', '=', artwork.company_id.id),
            ]
            if artwork.product_id:
                domain.append(('product_id', '=', artwork.product_id.id))
            lines = Line.search(domain).filtered(
                lambda l: not l.cl_artwork_id or l.cl_artwork_id.state == 'cancel')
            if lines:
                lines.write({'cl_artwork_id': artwork.id})

    def _cl_release_open_lines(self):
        """Quotations using a cancelled artwork fall back to the customer's approved one."""
        Artwork = self.env['cl.artwork']
        lines = self.sudo().cl_sale_line_ids.filtered(lambda l: l.state in ('draft', 'sent'))
        for line in lines:
            line.cl_artwork_id = Artwork._cl_find_approved(
                line.order_id.partner_id, line.product_id, line.company_id).id

    def _cl_sync_productions(self):
        productions = self.env['mrp.production'].sudo().search([
            ('cl_artwork_id', 'in', self.ids), ('state', 'not in', ('done', 'cancel'))])
        productions._cl_sync_artwork_attachment()

    def _cl_schedule_design_activity(self, note=False):
        for artwork in self.filtered('cl_designer_id'):
            artwork.sudo().activity_schedule(
                DESIGN_ACTIVITY,
                summary=_('Design artwork: %s', artwork.display_name),
                note=note or '',
                user_id=artwork.cl_designer_id.id,
            )

    def _cl_post_note(self, body, partners=None, attachments=None):
        """Chatter note in the name of the current user, optionally notifying ``partners``.

        Posted as superuser because message_post refuses a user who has no email
        address; the caller has already checked what the user may do."""
        self.ensure_one()
        return self.sudo().message_post(
            body=body,
            subtype_xmlid='mail.mt_note',
            author_id=self.env.user.partner_id.id,
            partner_ids=partners.ids if partners else None,
            attachments=attachments,
        )

    def _cl_form_action(self):
        self.ensure_one()
        return {
            'name': _('Artwork'),
            'type': 'ir.actions.act_window',
            'res_model': 'cl.artwork',
            'view_mode': 'form',
            'res_id': self.id,
        }

    # ------------------------------------------------------------------
    # workflow
    # ------------------------------------------------------------------

    def action_cl_send_to_designer(self):
        self._cl_check_sales_user()
        for artwork in self:
            if artwork.state != 'draft':
                raise UserError(_("%s has already been sent to the designer.", artwork.display_name))
            if not artwork.cl_designer_id:
                raise UserError(_("Choose a designer for %s first.", artwork.display_name))
            if not artwork.cl_source_file and not artwork.cl_brief:
                raise UserError(_("Upload the customer's logo or write a design brief for %s first.",
                                  artwork.display_name))
            artwork.sudo().write({'state': 'design'})
            artwork.message_subscribe(partner_ids=artwork.cl_designer_id.partner_id.ids)
            artwork._cl_schedule_design_activity(artwork.cl_brief)
            artwork._cl_post_note(
                _("Sent to %(designer)s for design by %(user)s.",
                  designer=artwork.cl_designer_id.name, user=self.env.user.name))
        return True

    def action_cl_submit_proof(self):
        for artwork in self:
            if not (self.env.user == artwork.cl_designer_id or artwork._cl_is_sales_user()):
                raise UserError(_("Only the designer of %s or a sales user can submit its proof.",
                                  artwork.display_name))
            if artwork.state not in ('draft', 'design', 'rework'):
                raise UserError(_("%s is not waiting for a proof.", artwork.display_name))
            if not artwork.cl_proof_file:
                raise UserError(_("Upload the proof of %s first.", artwork.display_name))
            proof_number = artwork.cl_proof_count + 1
            artwork.sudo().write({'state': 'review', 'cl_proof_count': proof_number})
            filename = artwork.cl_proof_filename or 'proof'
            artwork._cl_post_note(
                _("Proof %(number)s submitted by %(user)s.", number=proof_number,
                  user=self.env.user.name),
                attachments=[(_('Proof %(number)s - %(file)s', number=proof_number, file=filename),
                              base64.b64decode(artwork.with_context(bin_size=False).cl_proof_file))],
            )
            artwork.sudo().activity_feedback([DESIGN_ACTIVITY], feedback=_('Proof submitted'))
            if artwork.user_id:
                artwork.sudo().activity_schedule(
                    REVIEW_ACTIVITY,
                    summary=_('Review artwork proof: %s', artwork.display_name),
                    note=artwork.cl_designer_note or '',
                    user_id=artwork.user_id.id,
                )
        return True

    def action_cl_request_rework(self):
        self.ensure_one()
        self._cl_check_sales_user()
        if self.state != 'review':
            raise UserError(_("Only a proof waiting for review can be sent back for rework."))
        return {
            'name': _('Request Rework'),
            'type': 'ir.actions.act_window',
            'res_model': 'cl.artwork.rework.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cl_artwork_id': self.id},
        }

    def _cl_request_rework(self, comment):
        self._cl_check_sales_user()
        if not comment or not comment.strip():
            raise UserError(_("Tell the designer what to change."))
        for artwork in self:
            if artwork.state != 'review':
                raise UserError(_("Only a proof waiting for review can be sent back for rework."))
            artwork.sudo().write({'state': 'rework', 'cl_rework_note': comment})
            artwork.sudo().activity_feedback([REVIEW_ACTIVITY], feedback=_('Rework requested'))
            artwork._cl_schedule_design_activity(comment)
            artwork._cl_post_note(
                _("Rework requested by %(user)s: %(comment)s", user=self.env.user.name, comment=comment),
                partners=artwork.cl_designer_id.partner_id)
        return True

    def action_cl_approve(self):
        self._cl_check_sales_user()
        for artwork in self:
            if artwork.state != 'review':
                raise UserError(_("%s has no proof waiting for review.", artwork.display_name))
            if not artwork.cl_proof_file:
                raise UserError(_("%s has no proof file to approve.", artwork.display_name))
            artwork.sudo().write({
                'state': 'approved',
                'cl_approved_by_id': self.env.user.id,
                'cl_approved_date': fields.Datetime.now(),
            })
            artwork.sudo().activity_feedback([REVIEW_ACTIVITY], feedback=_('Approved'))
            artwork.sudo().activity_unlink([DESIGN_ACTIVITY])
            artwork._cl_post_note(_("Approved by %s.", self.env.user.name),
                                  partners=artwork.cl_designer_id.partner_id)
        self._cl_assign_open_lines()
        self._cl_sync_productions()
        return True

    def action_cl_cancel(self):
        self._cl_check_sales_user()
        if self.filtered(lambda a: a.state == 'approved'):
            raise UserError(_("Approved artwork cannot be cancelled. Archive it instead."))
        self.sudo().write({'state': 'cancel'})
        self.sudo().activity_unlink([DESIGN_ACTIVITY, REVIEW_ACTIVITY])
        self._cl_release_open_lines()
        return True

    def action_cl_reset_to_draft(self):
        self._cl_check_sales_user()
        self.filtered(lambda a: a.state == 'cancel').sudo().write({'state': 'draft'})
        return True

    def action_cl_new_version(self):
        """Start a new design from this one (same customer, product and logo)."""
        self.ensure_one()
        self._cl_check_sales_user()
        default = {}
        if self.env.context.get('cl_sale_order_id'):
            default['cl_sale_order_id'] = self.env.context['cl_sale_order_id']
        return self.copy(default)._cl_form_action()

    def action_cl_view_sale_orders(self):
        self.ensure_one()
        orders = self.cl_sale_line_ids.order_id
        action = self.env['ir.actions.act_window']._for_xml_id('sale.action_orders')
        action.update({'domain': [('id', 'in', orders.ids)], 'context': {'create': False}})
        return action

    def action_cl_view_productions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action.update({'domain': [('cl_artwork_id', '=', self.id)], 'context': {'create': False}})
        return action
