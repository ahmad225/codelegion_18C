# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tools import float_compare

APPROVER_GROUP = 'cl_credit_note_return_approval.group_cl_return_approver'
APPROVAL_ACTIVITY = 'cl_credit_note_return_approval.activity_type_return_approval'


class ReturnRequest(models.Model):
    """The authorisation to take goods back for a credit note.

    Accounting asks, a Return Approver decides. Only an approved request
    creates the return transfers, so the warehouse never sees a return that
    nobody agreed to, and a rejected request leaves nothing to clean up."""
    _name = 'cl.return.request'
    _description = 'Return Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    credit_note_id = fields.Many2one(
        'account.move', string='Credit Note', required=True, index=True,
        ondelete='cascade', domain=[('move_type', '=', 'out_refund')])
    invoice_id = fields.Many2one(
        related='credit_note_id.reversed_entry_id', string='Invoice', store=True)
    partner_id = fields.Many2one(
        related='credit_note_id.partner_id', string='Customer', store=True)
    company_id = fields.Many2one(
        related='credit_note_id.company_id', store=True, index=True)
    reason_id = fields.Many2one(
        related='credit_note_id.cl_credit_reason_id', string='Reason', store=True)
    user_id = fields.Many2one(
        'res.users', string='Requested By', readonly=True,
        default=lambda self: self.env.user)
    state = fields.Selection(
        selection=[
            ('to_approve', 'To Approve'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancel', 'Cancelled'),
        ],
        string='Status', default='to_approve', required=True, readonly=True,
        copy=False, tracking=True)
    decided_by_id = fields.Many2one(
        'res.users', string='Decided By', readonly=True, copy=False)
    decided_on = fields.Datetime(string='Decided On', readonly=True, copy=False)
    line_ids = fields.One2many(
        'cl.return.request.line', 'request_id', string='Goods To Return')
    picking_ids = fields.One2many(
        'stock.picking', 'cl_return_request_id', string='Return Transfers')
    picking_count = fields.Integer(
        string='Transfers', compute='_compute_reception', compute_sudo=True)
    is_received = fields.Boolean(
        string='Goods Received', compute='_compute_reception', compute_sudo=True,
        help="Approved, at least one return transfer is done and none is "
             "still open.")

    @api.depends('state', 'picking_ids.state')
    def _compute_reception(self):
        for request in self:
            states = request.picking_ids.mapped('state')
            request.picking_count = len(states)
            request.is_received = (
                request.state == 'approved'
                and 'done' in states
                and all(state in ('done', 'cancel') for state in states))

    # ------------------------------------------------------------------
    # The decision cannot be forged through a plain create/write
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['state'] = 'to_approve'
            vals.pop('decided_by_id', None)
            vals.pop('decided_on', None)
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'cl.return.request') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if 'credit_note_id' in vals:
                raise UserError(_(
                    "A return request cannot be moved to another credit note."))
            if vals.get('state') in ('approved', 'rejected') or (
                    {'decided_by_id', 'decided_on'} & vals.keys()):
                self._cl_check_approver()
        return super().write(vals)

    def _cl_check_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise AccessError(_(
                "Only Return Approvers can approve or reject a return request."))

    # ------------------------------------------------------------------
    # Asking
    # ------------------------------------------------------------------
    @api.model
    def _cl_request_for(self, credit_note):
        """Create the request of a draft credit note: the goods it credits,
        as far as they were delivered and are not on their way back yet."""
        credit_note.ensure_one()
        invoice = credit_note.reversed_entry_id
        if credit_note.move_type != 'out_refund' or not invoice:
            raise UserError(_(
                "A return can only be requested for the credit note of a customer invoice."))
        if credit_note.state != 'draft':
            raise UserError(_(
                "A return can only be requested while the credit note is a draft."))
        if credit_note.cl_return_request_ids.filtered(
                lambda r: r.state in ('to_approve', 'approved')):
            raise UserError(_(
                "This credit note already has a return request. Cancel it "
                "before asking for another one."))
        credit_note._cl_check_credit_limits()

        wanted = defaultdict(float)
        for line in credit_note.invoice_line_ids:
            product = line.product_id
            if line.display_type == 'product' and product.type == 'consu':
                uom = line.product_uom_id or product.uom_id
                wanted[product] += uom._compute_quantity(
                    line.quantity, product.uom_id, round=False)
        if not wanted:
            raise UserError(_(
                "There are no goods on this credit note, so there is nothing "
                "to return. Choose a reason that does not require a return."))

        # Deliveries are read as superuser: the person preparing the credit
        # note is not necessarily an inventory user.
        returnable = defaultdict(float)
        for move in invoice.sudo()._cl_delivery_moves():
            returnable[move.product_id.id] += move._cl_returnable_qty()

        lines, short = [], []
        for product, qty in wanted.items():
            rounding = product.uom_id.rounding
            possible = min(qty, returnable[product.id])
            if float_compare(possible, 0.0, precision_rounding=rounding) > 0:
                lines.append(Command.create(
                    {'product_id': product.id, 'quantity': possible}))
            if float_compare(possible, qty, precision_rounding=rounding) < 0:
                short.append(_(
                    "%(product)s: %(possible)s of %(qty)s %(uom)s",
                    product=product.display_name, possible=possible, qty=qty,
                    uom=product.uom_id.name))
        if not lines:
            raise UserError(_(
                "Nothing can be returned: the goods of invoice %s were not "
                "delivered from a sales order, or are already returned. Choose "
                "a reason that does not require a return.", invoice.name))

        request = self.create({'credit_note_id': credit_note.id, 'line_ids': lines})
        if short:
            request._message_log(body=_(
                "Not everything on the credit note can come back (not "
                "delivered, or already returned). Requested: %s",
                '; '.join(short)))
        request._cl_notify_approvers()
        credit_note._message_log(body=_(
            "Return %s requested.", request._get_html_link()))
        return request

    def _cl_notify_approvers(self):
        approvers = self.env.ref(APPROVER_GROUP).sudo().users
        for request in self:
            for user in approvers.filtered(
                    lambda u: u.active and request.company_id in u.company_ids):
                request.activity_schedule(
                    APPROVAL_ACTIVITY, user_id=user.id,
                    summary=_("Return to approve: %s", request.partner_id.display_name))

    # ------------------------------------------------------------------
    # Deciding
    # ------------------------------------------------------------------
    def _cl_decide(self, state, feedback):
        self.write({
            'state': state,
            'decided_by_id': self.env.user.id,
            'decided_on': fields.Datetime.now(),
        })
        self.activity_feedback([APPROVAL_ACTIVITY], feedback=feedback)

    def action_approve(self):
        self._cl_check_approver()
        for request in self:
            if request.state != 'to_approve':
                raise UserError(_(
                    "%s was already decided or cancelled.", request.name))
            pickings = request._cl_create_return_transfers()
            request._cl_decide('approved', _("Approved"))
            # the person who asked has to know: a real notification
            request.message_post(
                body=_("Return approved. Transfers to receive: %s",
                       ', '.join(pickings.mapped('name'))),
                partner_ids=request.user_id.partner_id.ids)
        return True

    def action_reject(self):
        self._cl_check_approver()
        for request in self:
            if request.state != 'to_approve':
                raise UserError(_(
                    "%s was already decided or cancelled.", request.name))
            request._cl_decide('rejected', _("Rejected"))
            request.message_post(
                body=_("Return rejected."),
                partner_ids=request.user_id.partner_id.ids)
        return True

    def action_cancel(self):
        """Withdraw a request, for instance to change the credit note and ask
        again. Transfers that are not received yet are cancelled with it."""
        for request in self:
            if request.state not in ('to_approve', 'approved'):
                continue
            pickings = request.sudo().picking_ids
            if 'done' in pickings.mapped('state'):
                raise UserError(_(
                    "Goods of %s were already received: it cannot be cancelled.",
                    request.name))
            pickings.filtered(lambda p: p.state != 'cancel').action_cancel()
            request.write({'state': 'cancel'})
            request.activity_unlink([APPROVAL_ACTIVITY])
        return True

    def _cl_create_return_transfers(self):
        """Create the return of each delivery concerned, most recent delivery
        first, for the requested quantities and never more than what is still
        at the customer's."""
        self.ensure_one()
        todo = defaultdict(float)
        for line in self.line_ids:
            todo[line.product_id.id] += line.quantity
        # The approver works in Inventory and may have no access to invoices.
        delivery_move_ids = self.sudo().invoice_id._cl_delivery_moves().ids
        deliveries = self.env['stock.move'].browse(delivery_move_ids).sorted(
            lambda move: (move.date, move.id), reverse=True)
        plan = defaultdict(dict)
        for move in deliveries:
            rounding = move.product_id.uom_id.rounding
            qty = min(todo[move.product_id.id], move._cl_returnable_qty())
            if float_compare(qty, 0.0, precision_rounding=rounding) > 0:
                plan[move.picking_id][move.id] = qty
                todo[move.product_id.id] -= qty
        if not plan:
            raise UserError(_(
                "%s: nothing can be returned any more, the goods are already "
                "on their way back. Reject the request.", self.name))

        pickings = self.env['stock.picking']
        for delivery, quantities in plan.items():
            wizard = self.env['stock.return.picking'].create({'picking_id': delivery.id})
            for return_line in wizard.product_return_moves:
                return_line.quantity = quantities.get(return_line.move_id.id, 0.0)
            pickings += wizard._create_return()
        pickings.sudo().write({'cl_return_request_id': self.id})
        return pickings

    def action_view_pickings(self):
        self.ensure_one()
        return self.picking_ids._get_records_action(name=_("Return Transfers"))


class ReturnRequestLine(models.Model):
    _name = 'cl.return.request.line'
    _description = 'Return Request Line'

    request_id = fields.Many2one(
        'cl.return.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('type', '=', 'consu')])
    quantity = fields.Float(
        string='Quantity', digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one(
        related='product_id.uom_id', string='Unit')

    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)',
         "The quantity to return must be positive."),
    ]
