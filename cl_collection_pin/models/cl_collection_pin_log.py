# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models

CL_PIN_EVENTS = [
    ('issued', 'PIN Issued'),
    ('resent', 'New PIN Sent'),
    ('verified', 'Verified'),
    ('failed', 'Wrong PIN'),
    ('locked', 'Locked'),
    ('cleared', 'Cleared'),
    ('expired', 'Expired'),
]


class ClCollectionPinLog(models.Model):
    """Audit trail of collection PIN events. Never holds the PIN itself.

    Users can only read it: lines are written by the module (as superuser).
    """
    _name = 'cl.collection.pin.log'
    _description = 'Collection PIN Log'
    _order = 'cl_date desc, id desc'
    _rec_name = 'cl_order_id'

    cl_order_id = fields.Many2one(
        'sale.order', string='Sales Order', required=True, index=True,
        ondelete='cascade', readonly=True)
    cl_picking_id = fields.Many2one(
        'stock.picking', string='Transfer', index='btree_not_null',
        ondelete='set null', readonly=True)
    cl_partner_id = fields.Many2one(
        related='cl_order_id.partner_id', string='Customer')
    cl_company_id = fields.Many2one(
        'res.company', string='Company', related='cl_order_id.company_id',
        store=True, index=True)
    cl_user_id = fields.Many2one(
        'res.users', string='User', readonly=True,
        default=lambda self: self.env.user)
    cl_event = fields.Selection(CL_PIN_EVENTS, string='Event', required=True, readonly=True)
    cl_attempt = fields.Integer(string='Attempt', readonly=True)
    cl_date = fields.Datetime(
        string='Date', required=True, readonly=True, default=fields.Datetime.now)
    cl_note = fields.Char(string='Details', readonly=True)
