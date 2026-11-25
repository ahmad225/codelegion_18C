# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.sale_order import CL_PIN_LENGTH

CL_PIN_FORMAT = re.compile(r'[0-9]{%d}' % CL_PIN_LENGTH)


class ClCollectionPinVerify(models.TransientModel):
    _name = 'cl.collection.pin.verify'
    _description = 'Verify Collection PIN'

    cl_picking_id = fields.Many2one(
        'stock.picking', string='Delivery', required=True, readonly=True, ondelete='cascade')
    cl_validate_picking_ids = fields.Many2many(
        'stock.picking', 'cl_collection_pin_verify_picking_rel', 'wizard_id', 'picking_id',
        string='Transfers to Validate', readonly=True)
    cl_order_id = fields.Many2one(related='cl_picking_id.sale_id', string='Sales Order')
    cl_partner_id = fields.Many2one(related='cl_picking_id.partner_id', string='Customer')
    cl_pin_state = fields.Selection(related='cl_picking_id.sale_id.cl_pin_state')
    cl_attempts_left = fields.Integer(
        string='Attempts Left', compute='_compute_cl_attempts_left', compute_sudo=True)
    cl_pin = fields.Char(string='Collection PIN', help="The PIN the customer received by email.")
    cl_error = fields.Char(string='Error', readonly=True)

    @api.depends('cl_picking_id.sale_id.cl_pin_attempts', 'cl_picking_id.company_id.cl_pin_max_attempts')
    def _compute_cl_attempts_left(self):
        for wizard in self:
            order = wizard.cl_picking_id.sale_id
            max_attempts = wizard.cl_picking_id.company_id.cl_pin_max_attempts or 5
            wizard.cl_attempts_left = max(max_attempts - order.cl_pin_attempts, 0)

    def _cl_action_open(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Verify Collection PIN"),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {},
        }

    def action_cl_verify(self):
        self.ensure_one()
        picking = self.cl_picking_id
        pin = (self.cl_pin or '').strip()
        # Never keep what was typed, right or wrong.
        self.write({'cl_pin': False, 'cl_error': False})
        to_validate = (self.cl_validate_picking_ids | picking).filtered(
            lambda p: p.state not in ('done', 'cancel'))
        if not picking.cl_pin_verified and picking.cl_is_collection_delivery:
            if not CL_PIN_FORMAT.fullmatch(pin):
                raise UserError(_("Enter the %s-digit collection PIN (digits only).", CL_PIN_LENGTH))
            order = picking.sale_id
            # Deliveries of the same order validated together are collected
            # at the same time: one PIN check covers them.
            same_collection = to_validate.filtered(
                lambda p: p.sale_id == order and p.cl_is_collection_delivery and not p.cl_pin_verified)
            if not order._cl_verify_pin(pin, picking, same_collection | picking):
                # No exception: the failed attempt must be saved.
                # sudo: the user may not be allowed to read the order itself.
                if order.sudo().cl_pin_state == 'locked':
                    error = _("Wrong PIN. Too many wrong attempts: the PIN is now locked. "
                              "An Inventory Administrator must issue a new PIN.")
                else:
                    error = _("Wrong PIN. %s attempt(s) left.", self.cl_attempts_left)
                self.cl_error = error
                return self._cl_action_open()
        return to_validate.button_validate()
