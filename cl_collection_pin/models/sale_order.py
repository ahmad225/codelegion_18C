# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import hashlib
import hmac
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

CL_PIN_LENGTH = 6
CL_PIN_ITERATIONS = 100000
CL_PIN_STATES = [
    ('none', 'No PIN'),
    ('active', 'Active'),
    ('locked', 'Locked'),
    ('used', 'Used'),
    ('expired', 'Expired'),
]
# Context key set only by this module's own code (always together with sudo)
# to allow writing the protected PIN fields.
CL_PIN_WRITE_CTX = 'cl_collection_pin_internal_write'
# Set while an order is being cancelled, so cancelling its deliveries does not
# expire the PIN with the wrong reason first.
CL_PIN_ORDER_CANCEL_CTX = 'cl_collection_pin_order_cancel'
# Protected PIN fields and the only values a user may create an order with.
CL_PIN_ORDER_DEFAULTS = {
    'cl_pin_hash': False,
    'cl_pin_salt': False,
    'cl_pin_state': 'none',
    'cl_pin_issued_at': False,
    'cl_pin_attempts': 0,
}
CL_PIN_ORDER_FIELDS = set(CL_PIN_ORDER_DEFAULTS)
CL_PIN_TEMPLATE_XMLID = 'cl_collection_pin.mail_template_collection_pin'


def cl_pin_internal_write_allowed(env):
    """Protected PIN fields may only be written by this module's code."""
    return env.su and env.context.get(CL_PIN_WRITE_CTX)


def cl_hash_pin(pin, salt):
    """Salted PBKDF2-SHA256 hash (hex) of a clear PIN; ``salt`` is hex."""
    return hashlib.pbkdf2_hmac(
        'sha256', pin.encode(), bytes.fromhex(salt), CL_PIN_ITERATIONS).hex()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_is_collection_order = fields.Boolean(
        string='Customer Collection', compute='_compute_cl_is_collection_order',
        compute_sudo=True,
        help="The delivery method of this order is a customer collection method.")
    # Only a salted hash of the PIN is kept. Restricted to Settings
    # administrators so other users cannot read it (and brute-force it offline).
    cl_pin_hash = fields.Char(
        string='Collection PIN Hash', readonly=True, copy=False, groups='base.group_system')
    cl_pin_salt = fields.Char(
        string='Collection PIN Salt', readonly=True, copy=False, groups='base.group_system')
    cl_pin_state = fields.Selection(
        CL_PIN_STATES, string='Collection PIN', default='none', readonly=True, copy=False)
    cl_pin_issued_at = fields.Datetime(string='PIN Issued On', readonly=True, copy=False)
    cl_pin_attempts = fields.Integer(string='Wrong PIN Attempts', readonly=True, copy=False)
    cl_pin_log_count = fields.Integer(
        string='PIN Log Entries', compute='_compute_cl_pin_log_count')

    @api.depends('carrier_id.cl_is_collection')
    def _compute_cl_is_collection_order(self):
        for order in self:
            order.cl_is_collection_order = bool(order.carrier_id.cl_is_collection)

    def _compute_cl_pin_log_count(self):
        counts = {}
        order_ids = self._origin.ids
        if order_ids:
            counts = {
                order.id: count
                for order, count in self.env['cl.collection.pin.log'].sudo()._read_group(
                    [('cl_order_id', 'in', order_ids)], ['cl_order_id'], ['__count'])
            }
        for order in self:
            order.cl_pin_log_count = counts.get(order._origin.id, 0)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        # An order is always created without a PIN, whoever creates it: there
        # is no exception for superuser code here, because core code creates
        # records as superuser with the caller's context.
        safe_vals_list = []
        for vals in vals_list:
            if any(vals.get(fname) and vals[fname] != safe
                   for fname, safe in CL_PIN_ORDER_DEFAULTS.items()):
                raise AccessError(_("The collection PIN fields are managed by the Click & Collect "
                                    "PIN workflow and cannot be set directly."))
            # Set them explicitly: otherwise ``default_<field>`` keys sent in
            # the context (RPC, import, copy) would fill them in.
            safe_vals_list.append(dict(vals, **CL_PIN_ORDER_DEFAULTS))
        return super().create(safe_vals_list)

    def write(self, vals):
        if CL_PIN_ORDER_FIELDS.intersection(vals) and not cl_pin_internal_write_allowed(self.env):
            raise AccessError(_("The collection PIN fields are managed by the Click & Collect "
                                "PIN workflow and cannot be changed directly."))
        old_carriers = {order.id: order.carrier_id for order in self} if 'carrier_id' in vals else {}
        if old_carriers:
            self._cl_check_carrier_change(vals['carrier_id'])
        res = super().write(vals)
        if old_carriers:
            changed = self.filtered(
                lambda o: o.carrier_id != old_carriers[o.id] and o.cl_pin_state != 'none')
            changed._cl_clear_pin(_("PIN cleared: delivery method changed."))
        if vals.get('state') == 'draft':
            self.filtered(lambda o: o.cl_pin_state != 'none')._cl_clear_pin(
                _("PIN cleared: order reset to quotation."))
        elif vals.get('state') == 'cancel':
            self.filtered(lambda o: o.cl_pin_state in ('active', 'locked'))._cl_expire_pin(
                _("PIN expired: order cancelled."))
        return res

    def _cl_check_carrier_change(self, new_carrier_id):
        """Changing the delivery method of an order waiting for collection
        clears its PIN and switches the PIN check of its deliveries off, so it
        needs the same rights as 'Send New PIN'. Inventory users have write
        access to sales orders: without this check the person who must verify
        the PIN could simply remove the need for it.
        """
        if self.env.su:
            return
        user = self.env.user
        if user.has_group('stock.group_stock_manager'):
            return
        is_salesman = user.has_group('sales_team.group_sale_salesman')
        for order in self.sudo():
            if (order.state != 'sale' or not order.carrier_id.cl_is_collection
                    or order.carrier_id.id == (new_carrier_id or False)
                    or not order._cl_open_collection_deliveries()):
                continue
            if order.cl_pin_state == 'locked':
                raise AccessError(_(
                    "The collection PIN of %s is locked after too many wrong attempts. Only an "
                    "Inventory Administrator can change its delivery method.", order.name))
            if not is_salesman:
                raise AccessError(_(
                    "%s is waiting to be collected by the customer. Only sales users and "
                    "Inventory Administrators can change its delivery method.", order.name))

    def _action_confirm(self):
        res = super()._action_confirm()
        # One-step warehouses have no pick transfer to wait for: the goods are
        # ready to collect as soon as the order is confirmed.
        for order in self.filtered('cl_is_collection_order'):
            transfers = self.env['stock.picking'].sudo().search(
                [('sale_id', '=', order.id), ('state', '!=', 'cancel')])
            if transfers and all(t.picking_type_code == 'outgoing' for t in transfers):
                order._cl_auto_issue_pin()
        return res

    def _action_cancel(self):
        return super(SaleOrder, self.with_context(**{CL_PIN_ORDER_CANCEL_CTX: True}))._action_cancel()

    # ------------------------------------------------------------------
    # PIN life cycle
    # ------------------------------------------------------------------

    def _cl_write_pin_values(self, vals):
        return self.sudo().with_context(**{CL_PIN_WRITE_CTX: True}).write(vals)

    def _cl_open_collection_deliveries(self):
        """Transfers handing the goods of the order to the customer (delivery
        operation type, or any transfer to a customer location) that are not
        done or cancelled yet."""
        self.ensure_one()
        return self.env['stock.picking'].sudo().search([
            ('sale_id', '=', self.id),
            '|', ('picking_type_code', '=', 'outgoing'), ('location_dest_id.usage', '=', 'customer'),
            ('state', 'not in', ('done', 'cancel')),
        ])

    def _cl_auto_issue_pin(self):
        """Issue a PIN for the orders whose goods are ready to collect.

        Never replaces an active PIN, and never unlocks a locked one.
        :return: {order id: clear PIN} for the orders that got one
        """
        pins = {}
        for order in self.sudo():
            if (order.state == 'sale' and order.cl_is_collection_order
                    and order.cl_pin_state not in ('active', 'locked')
                    and order._cl_open_collection_deliveries()):
                pins[order.id] = order._cl_issue_pin('issued')
        return pins

    def _cl_issue_pin(self, event, note=False):
        """Generate a new PIN, keep only its salted hash and email it.

        Any previous PIN of the order stops working. The clear PIN is only
        returned to the caller and put in the email to the customer.
        :return: the clear PIN
        """
        self.ensure_one()
        pin = '%0*d' % (CL_PIN_LENGTH, secrets.randbelow(10 ** CL_PIN_LENGTH))
        salt = secrets.token_hex(16)
        self._cl_write_pin_values({
            'cl_pin_hash': cl_hash_pin(pin, salt),
            'cl_pin_salt': salt,
            'cl_pin_state': 'active',
            'cl_pin_issued_at': fields.Datetime.now(),
            'cl_pin_attempts': 0,
        })
        sent, info = self._cl_send_pin_email(pin)
        details = [note] if note else []
        details.append(_("Emailed to %s.", info) if sent else _("Not emailed: %s.", info))
        self._cl_log(event, note=' '.join(details))
        return pin

    def _cl_send_pin_email(self, pin):
        """Email the clear PIN to the customer.

        The PIN is passed to the template through the context only. The mail
        is deleted once sent (auto_delete), and deleted by us if it could not be
        sent, so the PIN is never left in the database.
        :return: (sent, email address or reason it was not sent)
        """
        self.ensure_one()
        partner = self.sudo().partner_id
        email = partner.email
        template = self.env.ref(CL_PIN_TEMPLATE_XMLID, raise_if_not_found=False)
        if not email:
            reason = _("the customer has no email address")
        elif not template:
            reason = _("the collection PIN email template is missing")
        else:
            # Recipients are forced to the customer: whatever is added to the
            # template (To, Cc), the PIN goes to nobody else.
            mail_id = template.sudo().with_context(cl_collection_pin=pin).send_mail(
                self.id, force_send=True, email_values={
                    'auto_delete': True,
                    'email_to': False,
                    'email_cc': False,
                    'recipient_ids': [(6, 0, partner.ids)],
                })
            mail = self.env['mail.mail'].sudo().browse(mail_id).exists()
            if not mail:
                # auto_delete removed it: it was sent.
                reason = False
            else:
                reason = False if mail.state == 'sent' else (
                    mail.failure_reason or _("the email could not be delivered"))
                mail.unlink()
        if reason:
            self._cl_post_note(_(
                "The collection PIN could not be sent to the customer: %s. "
                "Fix it and use 'Send New PIN'.", reason))
            return False, reason
        self._cl_post_note(_("A new collection PIN was emailed to the customer (%s).", email))
        return True, email

    def _cl_clear_pin(self, note):
        """Forget the PIN (and the verification of the open deliveries)."""
        for order in self:
            order._cl_write_pin_values({
                'cl_pin_hash': False,
                'cl_pin_salt': False,
                'cl_pin_state': 'none',
                'cl_pin_issued_at': False,
                'cl_pin_attempts': 0,
            })
            order._cl_open_collection_deliveries().filtered('cl_pin_verified')._cl_set_verified(False)
            order._cl_log('cleared', note=note)
            order._cl_post_note(note)

    def _cl_expire_pin(self, note):
        for order in self:
            order._cl_write_pin_values({'cl_pin_state': 'expired'})
            order._cl_log('expired', note=note)
            order._cl_post_note(note)

    def _cl_expire_if_collected(self):
        """Expire a still usable PIN once no collection delivery is left open."""
        for order in self:
            if order.cl_pin_state in ('active', 'locked') and not order._cl_open_collection_deliveries():
                order._cl_expire_pin(_("PIN expired: all collection deliveries are done."))

    def _cl_check_pin_usable(self):
        """Raise a clear error when the order has no PIN that can be verified."""
        self.ensure_one()
        order = self.sudo()
        state = order.cl_pin_state
        if state == 'active':
            return
        if state == 'locked':
            raise UserError(_(
                "The collection PIN of %s is locked after too many wrong attempts. "
                "An Inventory Administrator must issue a new PIN with 'Send New PIN'.", order.name))
        if state == 'used':
            message = _("The collection PIN of %s has already been used.", order.name)
        elif state == 'expired':
            message = _("The collection PIN of %s has expired.", order.name)
        else:
            message = _("Order %s has no active collection PIN.", order.name)
        raise UserError(_("%s Issue a new one with the 'Send New PIN' button.", message))

    def _cl_pin_matches(self, pin):
        order = self.sudo()
        if not (order.cl_pin_hash and order.cl_pin_salt and pin):
            return False
        return hmac.compare_digest(cl_hash_pin(pin, order.cl_pin_salt), order.cl_pin_hash)

    def _cl_verify_pin(self, pin, picking, pickings=None):
        """Check a PIN given by the customer for ``picking``.

        A wrong PIN does not raise (so the attempt is kept): it is counted,
        logged, and locks the PIN when the company's limit is reached.
        A right PIN is used up and marks ``pickings`` (default: ``picking``)
        as verified.
        :return: True if the PIN is right
        """
        self.ensure_one()
        self._cl_check_pin_usable()
        if self._cl_pin_matches(pin):
            self._cl_write_pin_values({'cl_pin_state': 'used'})
            (pickings or picking)._cl_set_verified(True)
            self._cl_log('verified', picking=picking)
            self._cl_post_note(
                _("Collection PIN verified by %(user)s for %(picking)s.",
                  user=self.env.user.name, picking=picking.name), picking)
            return True
        # Read as superuser: the user at the counter may not be allowed to
        # read this order (e.g. a salesperson limited to their own orders).
        order = self.sudo()
        attempts = order.cl_pin_attempts + 1
        max_attempts = order.company_id.cl_pin_max_attempts or 5
        locked = attempts >= max_attempts
        vals = {'cl_pin_attempts': attempts}
        if locked:
            vals['cl_pin_state'] = 'locked'
        self._cl_write_pin_values(vals)
        self._cl_log('failed', picking=picking, attempt=attempts)
        self._cl_post_note(
            _("Wrong collection PIN entered by %(user)s for %(picking)s (attempt %(attempt)s of %(max)s).",
              user=self.env.user.name, picking=picking.name, attempt=attempts, max=max_attempts),
            picking)
        if locked:
            note = _("PIN locked after %s wrong attempts.", attempts)
            self._cl_log('locked', picking=picking, attempt=attempts, note=note)
            self._cl_post_note(note, picking)
        return False

    def _cl_log(self, event, picking=False, attempt=0, note=False):
        self.ensure_one()
        return self.env['cl.collection.pin.log'].sudo().create({
            'cl_order_id': self.id,
            'cl_picking_id': picking.id if picking else False,
            'cl_user_id': self.env.user.id,
            'cl_event': event,
            'cl_attempt': attempt,
            'cl_note': note or False,
        })

    def _cl_post_note(self, body, pickings=None):
        """Log a note in the chatter of the order (and ``pickings``).

        ``_message_log`` notifies nobody and works for users without an email
        address, which is common for warehouse staff.
        """
        self.ensure_one()
        self.sudo()._message_log(body=body)
        for picking in (pickings or []):
            picking.sudo()._message_log(body=body)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_cl_send_new_pin(self):
        """Issue a new PIN (the old one stops working) and email it."""
        self.ensure_one()
        user = self.env.user
        is_stock_manager = user.has_group('stock.group_stock_manager')
        if not (is_stock_manager or user.has_group('sales_team.group_sale_salesman')):
            raise AccessError(_(
                "Only sales users and Inventory Administrators can send a new collection PIN."))
        if not is_stock_manager:
            # Sales users: only for the orders they are allowed to see.
            self.check_access('read')
        order = self.sudo()
        if order.cl_pin_state == 'locked' and not is_stock_manager:
            raise AccessError(_(
                "The collection PIN of %s is locked after too many wrong attempts. "
                "Only an Inventory Administrator can unlock it by issuing a new PIN.", order.name))
        if not order.cl_is_collection_order:
            raise UserError(_("Order %s is not collected by the customer.", order.name))
        if order.state != 'sale':
            raise UserError(_("A collection PIN can only be sent for a confirmed order."))
        if not order._cl_open_collection_deliveries():
            raise UserError(_("Order %s has no delivery left to collect.", order.name))
        if order.cl_pin_state == 'none':
            self._cl_issue_pin('issued')
        elif order.cl_pin_state == 'locked':
            self._cl_issue_pin('resent', note=_("Locked PIN replaced."))
        else:
            self._cl_issue_pin('resent', note=_("Previous PIN invalidated."))
        return True

    def action_cl_view_pin_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'cl_collection_pin.cl_collection_pin_log_action')
        action['domain'] = [('cl_order_id', '=', self.id)]
        action['context'] = {}
        return action
