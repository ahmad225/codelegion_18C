# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .sale_order import CL_PIN_ORDER_CANCEL_CTX, CL_PIN_WRITE_CTX, cl_pin_internal_write_allowed


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cl_is_collection_delivery = fields.Boolean(
        string='Customer Collection', compute='_compute_cl_is_collection_delivery',
        compute_sudo=True,
        help="Delivery of an order collected by the customer: it can only be "
             "validated once the customer's collection PIN is verified.")
    cl_pin_verified = fields.Boolean(
        string='Collection PIN Verified', readonly=True, copy=False,
        help="The customer's collection PIN was verified for this delivery.")
    cl_pin_state = fields.Selection(related='sale_id.cl_pin_state', string='Collection PIN')
    cl_pin_issued_at = fields.Datetime(related='sale_id.cl_pin_issued_at')
    cl_pin_attempts = fields.Integer(related='sale_id.cl_pin_attempts')
    cl_pin_log_count = fields.Integer(
        string='PIN Log Entries', compute='_compute_cl_pin_log_count')

    @api.depends('picking_type_code', 'location_dest_id.usage',
                 'sale_id.carrier_id.cl_is_collection')
    def _compute_cl_is_collection_delivery(self):
        for picking in self:
            # A transfer to a customer location counts whatever its operation
            # type: switching the type of a delivery must not skip the PIN.
            picking.cl_is_collection_delivery = bool(
                picking.sale_id.carrier_id.cl_is_collection
                and (picking.picking_type_code == 'outgoing'
                     or picking.location_dest_id.usage == 'customer'))

    def _compute_cl_pin_log_count(self):
        Log = self.env['cl.collection.pin.log'].sudo()
        for picking in self:
            origin = picking._origin
            picking.cl_pin_log_count = Log.search_count(origin._cl_pin_log_domain()) if origin else 0

    def _cl_pin_log_domain(self):
        self.ensure_one()
        if self.sale_id:
            return [('cl_order_id', '=', self.sale_id.id)]
        return [('cl_picking_id', '=', self.id)]

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # A transfer is always created unverified, whoever creates it: there is
        # no exception for superuser code here, because core code creates
        # transfers (next step of a route) as superuser with the caller's context.
        if any(vals.get('cl_pin_verified') for vals in vals_list):
            raise AccessError(_("A collection PIN can only be verified with the PIN verification."))
        # Set it explicitly: otherwise a ``default_cl_pin_verified`` key sent in
        # the context would mark new transfers and backorders (created by copy)
        # as verified.
        return super().create([dict(vals, cl_pin_verified=False) for vals in vals_list])

    def write(self, vals):
        if 'cl_pin_verified' in vals and not cl_pin_internal_write_allowed(self.env):
            raise AccessError(_("A collection PIN can only be verified with the PIN verification."))
        if not self.env.su and ('sale_id' in vals or 'group_id' in vals) and any(
                picking.cl_is_collection_delivery and picking.state not in ('done', 'cancel')
                for picking in self):
            # Unlinking the delivery from its order would switch the PIN check off.
            raise AccessError(_(
                "The sales order of a customer collection delivery cannot be changed "
                "while the delivery is open."))
        return super().write(vals)

    def _cl_set_verified(self, verified):
        return self.sudo().with_context(**{CL_PIN_WRITE_CTX: True}).write(
            {'cl_pin_verified': verified})

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _cl_pending_pin_verification(self):
        return self.filtered(
            lambda p: p.state not in ('done', 'cancel')
            and p.cl_is_collection_delivery and not p.cl_pin_verified)

    def button_validate(self):
        pending = self._cl_pending_pin_verification()
        if pending:
            return pending[0]._cl_action_verify_pin(self.filtered(lambda p: p.state not in ('done', 'cancel')))
        return super().button_validate()

    def _cl_action_verify_pin(self, pickings_to_validate):
        """Open the PIN verification for this delivery; ``pickings_to_validate``
        are validated once the PIN is right."""
        self.ensure_one()
        wizard = self.env['cl.collection.pin.verify'].create({
            'cl_picking_id': self.id,
            'cl_validate_picking_ids': [(6, 0, pickings_to_validate.ids)],
        })
        return wizard._cl_action_open()

    def _action_done(self):
        # Hard guard for every caller (form, list, API, other modules).
        pending = self._cl_pending_pin_verification()
        if pending:
            picking = pending[0]
            # sudo: the user may not be allowed to read the order itself.
            order = picking.sudo().sale_id
            if order.cl_pin_state == 'active':
                hint = _("Validate it with the Validate button and enter the customer's PIN.")
            elif order.cl_pin_state == 'locked':
                hint = _("The PIN is locked after too many wrong attempts: an Inventory "
                         "Administrator must issue a new one with 'Send New PIN'.")
            else:
                hint = _("There is no active PIN for order %s: issue one with the "
                         "'Send New PIN' button first.", order.name)
            raise UserError(_(
                "%(picking)s is a customer collection: the customer's collection PIN must be "
                "verified before it can be validated. %(hint)s",
                picking=picking.name, hint=hint))
        res = super()._action_done()
        done = self.filtered(lambda p: p.state == 'done' and p.sale_id)
        # Goods are ready to collect once a pick / pack step of the order is done.
        done.filtered(lambda p: p.picking_type_code == 'internal').sale_id._cl_auto_issue_pin()
        done.filtered('cl_is_collection_delivery').sale_id._cl_expire_if_collected()
        return res

    def action_cancel(self):
        orders = self.sale_id
        res = super().action_cancel()
        if not self.env.context.get(CL_PIN_ORDER_CANCEL_CTX):
            orders.filtered('cl_is_collection_order')._cl_expire_if_collected()
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_cl_send_new_pin(self):
        self.ensure_one()
        if not self.cl_is_collection_delivery:
            raise UserError(_("%s is not a customer collection delivery.", self.name))
        return self.sale_id.action_cl_send_new_pin()

    def action_cl_view_pin_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_collection_pin.cl_collection_pin_log_action')
        action['domain'] = self._cl_pin_log_domain()
        action['context'] = {}
        return action
