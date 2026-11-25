# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

COORDINATOR_GROUP = 'cl_mrp_mto_approval.group_cl_mto_coordinator'
APPROVAL_ACTIVITY = 'cl_mrp_mto_approval.mail_act_cl_mto_approval'
BLOCKED_STATES = ('pending', 'rejected')
# Only coordinators (or the system) may change these.
PROTECTED_FIELDS = {
    'cl_mto_sale_order_id', 'cl_approval_state', 'cl_approval_parent_id',
    'cl_approval_user_id', 'cl_approval_date', 'cl_rejection_reason',
}


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    cl_mto_sale_order_id = fields.Many2one(
        'sale.order', string='Make-to-Order Sales Order', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null',
        help='Sales order whose procurement created this manufacturing order '
             '(also set on its sub-assembly orders and backorders).')
    cl_approval_state = fields.Selection(
        [('none', 'Not Required'), ('pending', 'Waiting Approval'),
         ('approved', 'Approved'), ('rejected', 'Rejected')],
        string='MTO Approval', default='none', required=True, readonly=True, copy=False,
        index=True, tracking=True)
    cl_approval_parent_id = fields.Many2one(
        'mrp.production', string='Approved With', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null',
        help='Sub-assembly order: it is approved or rejected together with this order.')
    cl_approval_user_id = fields.Many2one('res.users', string='Approval Decided By', readonly=True, copy=False)
    cl_approval_date = fields.Datetime(string='Approval Decision Date', readonly=True, copy=False)
    cl_rejection_reason = fields.Text(string='Rejection Reason', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _cl_is_coordinator(self):
        user = self.env.user
        return self.env.su or user.has_group(COORDINATOR_GROUP) or user.has_group('base.group_system')

    def _cl_check_coordinator(self):
        if not self._cl_is_coordinator():
            raise AccessError(_("Only a Manufacturing Coordinator or an administrator can approve or "
                                "reject make-to-order manufacturing orders."))

    def _cl_check_approved(self):
        blocked = self.filtered(lambda p: p.cl_approval_state in BLOCKED_STATES)
        if blocked:
            raise UserError(_(
                "%s is waiting for a Manufacturing Coordinator's approval. It cannot be planned, "
                "started, produced or merged until it is approved.",
                ', '.join(blocked.mapped('name'))))

    def _cl_close_approval_activities(self, feedback):
        """The deciding user's own activity is marked done with the decision; the
        activities of the other coordinators are simply removed (one line in the
        chatter instead of one per coordinator)."""
        # As the system: activities of other users, and no "configure your email
        # address" error for a coordinator without one.
        productions = self.sudo()
        productions.activity_feedback([APPROVAL_ACTIVITY], user_id=self.env.uid, feedback=feedback)
        productions.activity_unlink([APPROVAL_ACTIVITY])

    def _cl_coordinators(self):
        self.ensure_one()
        group = self.env.ref(COORDINATOR_GROUP)
        return group.sudo().users.filtered(
            lambda u: u.active and not u.share and self.company_id in u.company_ids)

    def _cl_approval_family(self):
        """These orders, their backorders/splits and their sub-assembly orders."""
        family = self
        todo = self
        while todo:
            siblings = todo.procurement_group_id.mrp_production_ids
            children = self.search([('cl_approval_parent_id', 'in', (todo | siblings).ids)])
            new = (siblings | children) - family
            family |= new
            todo = new
        return family

    def _cl_request_approval(self):
        for production in self:
            coordinators = production._cl_coordinators()
            # The user may not be allowed to read the sales order (own documents only).
            order_name = production.sudo().cl_mto_sale_order_id.name
            for user in coordinators:
                production.sudo().activity_schedule(
                    APPROVAL_ACTIVITY,
                    summary=_('Approve make-to-order manufacturing'),
                    note=_("Manufacturing order %(mo)s was created for sales order %(so)s. "
                           "Check it, then approve or reject it.",
                           mo=production.name, so=order_name),
                    user_id=user.id,
                )
            body = _("Created for sales order %s: waiting for a Manufacturing Coordinator's "
                     "approval before production can start.", order_name)
            if not coordinators:
                body = '%s %s' % (body, _(
                    "Nobody in %s has the Manufacturing Coordinator group: assign it to someone.",
                    production.company_id.name))
            production._message_log(body=body)

    # ------------------------------------------------------------------
    # creation from procurement / backorders
    # ------------------------------------------------------------------

    def _post_run_manufacture(self, post_production_values):
        res = super()._post_run_manufacture(post_production_values)
        # Sub-assemblies are approved with their parent: only the top orders get activities.
        self.filtered(
            lambda p: p.cl_approval_state == 'pending' and not p.cl_approval_parent_id
        )._cl_request_approval()
        return res

    def _get_backorder_mo_vals(self):
        # Backorders and splits keep the approval of their original order:
        # an approved order is not sent back to approval, a waiting one stays waiting.
        res = super()._get_backorder_mo_vals()
        res.update({
            'cl_mto_sale_order_id': self.cl_mto_sale_order_id.id,
            'cl_approval_state': self.cl_approval_state,
            'cl_approval_parent_id': self.cl_approval_parent_id.id,
            'cl_approval_user_id': self.cl_approval_user_id.id,
            'cl_approval_date': self.cl_approval_date,
            'cl_rejection_reason': self.cl_rejection_reason,
        })
        return res

    def write(self, vals):
        if PROTECTED_FIELDS.intersection(vals) and not self._cl_is_coordinator():
            raise AccessError(_("Only a Manufacturing Coordinator or an administrator can change "
                                "the make-to-order approval of a manufacturing order."))
        if vals.get('qty_producing'):
            self._cl_check_approved()
        return super().write(vals)

    # ------------------------------------------------------------------
    # production guards
    # ------------------------------------------------------------------

    def button_plan(self):
        self._cl_check_approved()
        return super().button_plan()

    def action_start(self):
        self._cl_check_approved()
        return super().action_start()

    def button_mark_done(self):
        self._cl_check_approved()
        return super().button_mark_done()

    def _post_inventory(self, cancel_backorder=False):
        # Last line of defence: nothing is consumed or produced before approval.
        self._cl_check_approved()
        return super()._post_inventory(cancel_backorder=cancel_backorder)

    def _action_cancel(self):
        self.sudo().activity_unlink([APPROVAL_ACTIVITY])
        return super()._action_cancel()

    def _pre_action_split_merge_hook(self, merge=False, split=False):
        # Merging creates a brand new order: it must not be a way around the approval.
        # Splitting is fine, the parts keep the approval of the original order.
        if merge:
            self._cl_check_approved()
        return super()._pre_action_split_merge_hook(merge=merge, split=split)

    def action_merge(self):
        orders = self.sudo().cl_mto_sale_order_id
        approved = any(production.cl_approval_state == 'approved' for production in self)
        action = super().action_merge()
        merged = self.browse(action.get('res_id')) if isinstance(action, dict) else self.browse()
        if merged and len(orders) == 1:
            # Orders of one sales order merged (none of them waiting, see the hook above):
            # the new order stays linked to that sales order.
            merged.sudo().write({
                'cl_mto_sale_order_id': orders.id,
                'cl_approval_state': 'approved' if approved else 'none',
            })
        return action

    # ------------------------------------------------------------------
    # approval actions
    # ------------------------------------------------------------------

    def action_cl_approve(self):
        self._cl_check_coordinator()
        family = self._cl_approval_family().filtered(
            lambda p: p.cl_approval_state in BLOCKED_STATES and p.state not in ('done', 'cancel'))
        if not family:
            return True
        family.write({
            'cl_approval_state': 'approved',
            'cl_approval_user_id': self.env.uid,
            'cl_approval_date': fields.Datetime.now(),
            'cl_rejection_reason': False,
        })
        family._cl_close_approval_activities(_('Approved'))
        for production in family:
            production._message_log(body=_("Approved for production by %s.", self.env.user.name))
        # Written as the system: the coordinator may not be allowed to open the sales order.
        for order in family.sudo().cl_mto_sale_order_id:
            names = ', '.join(family.filtered(
                lambda p: p.sudo().cl_mto_sale_order_id.id == order.id).mapped('name'))
            order._message_log(body=_("Manufacturing order(s) %(names)s approved for production by %(user)s.",
                                      names=names, user=self.env.user.name))
        return True

    def action_cl_reject(self):
        self._cl_check_coordinator()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Manufacturing Order'),
            'res_model': 'cl.mrp.mto.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_ids': self.ids},
        }

    def _cl_reject(self, reason, cancel=False):
        self._cl_check_coordinator()
        family = self._cl_approval_family().filtered(
            lambda p: p.cl_approval_state in BLOCKED_STATES and p.state not in ('done', 'cancel'))
        if not family:
            return True
        family.write({
            'cl_approval_state': 'rejected',
            'cl_approval_user_id': self.env.uid,
            'cl_approval_date': fields.Datetime.now(),
            'cl_rejection_reason': reason,
        })
        family._cl_close_approval_activities(_('Rejected: %s', reason))
        if cancel:
            family.action_cancel()
            outcome = _("The manufacturing order was cancelled.")
        else:
            outcome = _("The manufacturing order is kept on hold.")
        for production in family:
            production._message_log(body=_("Rejected by %(user)s: %(reason)s %(outcome)s",
                                           user=self.env.user.name, reason=reason, outcome=outcome))
        for order in family.sudo().cl_mto_sale_order_id:
            names = ', '.join(family.filtered(
                lambda p: p.sudo().cl_mto_sale_order_id.id == order.id).mapped('name'))
            # A real notification to the salesperson; written as the system once the
            # coordinator's right to reject has been checked (they may not edit this order).
            order.message_post(
                body=_("Manufacturing order(s) %(names)s rejected by %(user)s. Reason: %(reason)s %(outcome)s",
                       names=names, user=self.env.user.name, reason=reason, outcome=outcome),
                partner_ids=order.user_id.partner_id.ids,
                subtype_xmlid='mail.mt_note',
            )
        return True

    def action_cl_request_approval(self):
        """Production sends a rejected order (after fixing it) for approval again."""
        rejected = self.filtered(lambda p: p.cl_approval_state == 'rejected' and p.state not in ('done', 'cancel'))
        if not rejected:
            return True
        rejected.check_access('write')
        family = rejected._cl_approval_family().filtered(
            lambda p: p.cl_approval_state == 'rejected' and p.state not in ('done', 'cancel'))
        family.sudo().write({'cl_approval_state': 'pending'})
        family.filtered(lambda p: p.cl_approval_parent_id not in family)._cl_request_approval()
        return True
