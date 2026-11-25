# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

APPROVER_GROUP = 'cl_contact_approval.group_cl_contact_approver'
APPROVAL_ACTIVITY = 'cl_contact_approval.mail_act_cl_customer_approval'
ORDER_REVIEW_ACTIVITY = 'cl_contact_approval.mail_act_cl_unapproved_order'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Held by the commercial partner (company, or individual without parent)
    # and copied to its contacts through Odoo's commercial-field sync.
    cl_approval_state = fields.Selection(
        [('draft', 'Draft'), ('pending', 'Pending Approval'), ('approved', 'Approved')],
        string='Approval Status', default='draft', readonly=True,
        copy=False, index=True, tracking=True)
    cl_approval_requested_by_id = fields.Many2one(
        'res.users', string='Approval Requested By', copy=False, readonly=True)
    cl_approval_enabled = fields.Boolean(compute='_compute_cl_approval_enabled')

    @api.depends('company_id')
    @api.depends_context('company')
    def _compute_cl_approval_enabled(self):
        for partner in self:
            partner.cl_approval_enabled = partner._cl_approval_company().cl_contact_approval_enabled

    @api.model
    def _commercial_fields(self):
        return super()._commercial_fields() + ['cl_approval_state']

    # ---- helpers ----

    def _cl_approval_company(self):
        self.ensure_one()
        return (self.company_id or self.env.company).sudo()

    @api.model
    def _cl_is_approver(self):
        return self.env.su or self.env.user.has_group(APPROVER_GROUP)

    def _cl_check_approver(self):
        if not self._cl_is_approver():
            raise AccessError(_("Only members of the 'Approve Customers' group can approve or reject customers."))

    def _cl_missing_mandatory_fields(self):
        """Labels of the company's mandatory fields that are empty on the commercial partner."""
        self.ensure_one()
        partner = self.commercial_partner_id.sudo()
        return [
            field.field_description
            for field in self._cl_approval_company().cl_contact_mandatory_field_ids
            if field.name in partner._fields and not partner[field.name]
        ]

    @api.model
    def _cl_get_approvers(self, company=None):
        group = self.env.ref(APPROVER_GROUP, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        approvers = group.sudo().users.filtered(lambda u: u.active and not u.share)
        if company:
            approvers = approvers.filtered(lambda u: company in u.company_ids)
        return approvers

    @api.model
    def _cl_schedule_approver_activities(self, records, act_type_xmlid, company, summary, note):
        """One activity per approver per record; approvers already holding one are skipped."""
        approvers = self._cl_get_approvers(company)
        for record in records.sudo():
            already = record.activity_search([act_type_xmlid]).user_id
            for user in approvers - already:
                record.activity_schedule(act_type_xmlid, summary=summary, note=note, user_id=user.id)
        return approvers

    @api.model
    def _cl_close_approver_activities(self, records, act_type_xmlid, feedback, log_if_none=False):
        """Close the activities scheduled for the approvers on ``records``.

        Every approver holds a copy. The one of the user who decided is marked
        done (one chatter line); the copies of the others are removed, instead
        of one "done" line per approver.
        """
        for record in records.sudo():
            mine = record.activity_search([act_type_xmlid], user_id=self.env.uid)
            if mine:
                mine.action_feedback(feedback=feedback)
            elif log_if_none:
                record._message_log(body=feedback)
            record.activity_unlink([act_type_xmlid])

    def _cl_notify_requester(self, body):
        self.ensure_one()
        requester = self.cl_approval_requested_by_id
        partner_ids = requester.partner_id.ids if requester and requester != self.env.user else []
        # message_post refuses a user without an email address: only log the note then.
        if partner_ids and (self.env.su or self.env.user.email_formatted):
            self.sudo().message_post(body=body, partner_ids=partner_ids, subtype_xmlid='mail.mt_note')
        else:
            self.sudo()._message_log(body=body)

    # ---- ORM guards ----

    @api.model_create_multi
    def create(self, vals_list):
        is_approver = self._cl_is_approver()
        context_default = self.env.context.get('default_cl_approval_state')
        for vals in vals_list:
            company = self.env['res.company'].browse(vals['company_id']) if vals.get('company_id') else self.env.company
            requested = vals.get('cl_approval_state', context_default)
            if not company.sudo().cl_contact_approval_enabled:
                vals['cl_approval_state'] = 'approved'
            elif is_approver:
                vals['cl_approval_state'] = requested or 'draft'
            elif requested and requested != 'draft':
                if vals.get('parent_id') and not vals.get('is_company'):
                    # A contact person: its status is synced from its company right after creation.
                    vals['cl_approval_state'] = 'draft'
                else:
                    raise AccessError(_("Only members of the 'Approve Customers' group can create an approved customer."))
            else:
                vals['cl_approval_state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        is_approver = self._cl_is_approver()
        if (
            'cl_approval_state' in vals
            and not is_approver
            and any(partner.cl_approval_state != vals['cl_approval_state'] for partner in self)
        ):
            raise AccessError(_(
                "Only members of the 'Approve Customers' group can change the approval status of a customer. "
                "Use 'Send for Approval' to ask for an approval."))
        was_contact = self.browse()
        if not is_approver and ('parent_id' in vals or 'is_company' in vals):
            was_contact = self.filtered(lambda p: p.commercial_partner_id != p)
        res = super().write(vals)
        if was_contact:
            self._cl_reset_detached_contacts(was_contact)
        return res

    @api.model
    def _cl_reset_detached_contacts(self, partners):
        """A contact person that became its own commercial partner must not keep
        the approval it inherited from its former company."""
        detached = partners.filtered(
            lambda p: p.commercial_partner_id == p and p.cl_approval_state != 'draft' and p.cl_approval_enabled)
        if detached:
            detached.sudo().write({'cl_approval_state': 'draft', 'cl_approval_requested_by_id': False})
            for partner in detached:
                partner.sudo()._message_log(
                    body=_("No longer part of an approved company: the customer is back in Draft "
                           "and needs its own approval."))

    # ---- workflow ----

    def action_cl_send_for_approval(self):
        partners = self.commercial_partner_id.filtered(lambda p: p.cl_approval_state == 'draft')
        partners.check_access('write')
        for partner in partners:
            missing = partner._cl_missing_mandatory_fields()
            if missing:
                raise UserError(_(
                    "%(customer)s cannot be sent for approval yet. Please fill in:\n- %(fields)s",
                    customer=partner.display_name, fields='\n- '.join(missing)))
        partners.sudo().write({'cl_approval_state': 'pending', 'cl_approval_requested_by_id': self.env.uid})
        for partner in partners:
            approvers = self._cl_schedule_approver_activities(
                partner, APPROVAL_ACTIVITY, partner.company_id,
                summary=_('Approve customer'),
                note=_('%s was sent for approval.', partner.display_name))
            if approvers:
                body = _("Sent for approval to %s.", ', '.join(approvers.mapped('name')))
            else:
                body = _("Sent for approval. Nobody is in the 'Approve Customers' group yet.")
            partner.sudo()._message_log(body=body)
        return True

    def action_cl_mass_send_for_approval(self):
        """List action: send the selected draft customers and say how many went."""
        partners = self.commercial_partner_id.filtered(lambda p: p.cl_approval_state == 'draft')
        partners.action_cl_send_for_approval()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Send for Approval'),
                'message': _("%s customer(s) sent for approval.", len(partners)) if partners
                else _("None of the selected contacts is a customer in Draft."),
                'type': 'success' if partners else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _cl_approve(self, raise_on_missing=True):
        """Approve the commercial partners of self.

        :return: (approved partners, {partner: [missing field labels]})
        """
        self._cl_check_approver()
        partners = self.commercial_partner_id.filtered(lambda p: p.cl_approval_state != 'approved')
        approved = self.browse()
        skipped = {}
        for partner in partners:
            missing = partner._cl_missing_mandatory_fields()
            if missing:
                if raise_on_missing:
                    raise UserError(_(
                        "%(customer)s cannot be approved yet. Please fill in:\n- %(fields)s",
                        customer=partner.display_name, fields='\n- '.join(missing)))
                skipped[partner] = missing
                continue
            approved |= partner
        if approved:
            approved.sudo().write({'cl_approval_state': 'approved'})
            review_type = self.env.ref(ORDER_REVIEW_ACTIVITY, raise_if_not_found=False)
            for partner in approved:
                feedback = _('Customer approved by %s.', self.env.user.name)
                self._cl_close_approver_activities(partner, APPROVAL_ACTIVITY, feedback)
                if review_type:
                    orders = self.env['sale.order'].sudo().search([
                        ('partner_id', 'child_of', partner.id),
                        ('activity_ids.activity_type_id', '=', review_type.id),
                    ])
                    self._cl_close_approver_activities(
                        orders, ORDER_REVIEW_ACTIVITY, feedback, log_if_none=True)
                partner._cl_notify_requester(_("%s is approved.", partner.display_name))
        return approved, skipped

    def action_cl_approve(self):
        self._cl_approve(raise_on_missing=True)
        return True

    def action_cl_mass_approve(self):
        """List action: approve what can be approved and report the rest."""
        approved, skipped = self._cl_approve(raise_on_missing=False)
        lines = [_("%s customer(s) approved.", len(approved))]
        for partner, missing in skipped.items():
            lines.append(_("%(customer)s skipped, missing: %(fields)s",
                           customer=partner.display_name, fields=', '.join(missing)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approve Customers'),
                'message': '\n'.join(lines),
                'type': 'warning' if skipped else 'success',
                'sticky': bool(skipped),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_cl_reject(self):
        self._cl_check_approver()
        partners = self.commercial_partner_id.filtered(lambda p: p.cl_approval_state == 'pending')
        partners.sudo().write({'cl_approval_state': 'draft'})
        for partner in partners:
            self._cl_close_approver_activities(
                partner, APPROVAL_ACTIVITY, _('Approval rejected by %s.', self.env.user.name))
            partner._cl_notify_requester(_(
                "Approval of %(customer)s was rejected by %(user)s. The customer is back in Draft.",
                customer=partner.display_name, user=self.env.user.name))
        return True

    def action_cl_revoke_approval(self):
        """Take back the approval of an approved customer: it goes back to Draft
        (with its contacts) and has to be sent for approval again."""
        self._cl_check_approver()
        partners = self.commercial_partner_id.filtered(lambda p: p.cl_approval_state == 'approved')
        partners.sudo().write({'cl_approval_state': 'draft'})
        for partner in partners:
            partner._cl_notify_requester(_(
                "Approval of %(customer)s was revoked by %(user)s. The customer is back in Draft: "
                "its quotations cannot be confirmed until it is approved again.",
                customer=partner.display_name, user=self.env.user.name))
        return True
