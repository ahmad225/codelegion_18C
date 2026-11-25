# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class CreditNoteReason(models.Model):
    """Why a customer invoice is credited. Some reasons mean goods are coming
    back: those credit notes wait for the return before they can be posted."""
    _name = 'cl.credit.note.reason'
    _description = 'Credit Note Reason'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    requires_return = fields.Boolean(
        string='Goods Must Come Back',
        help="A credit note with this reason can only be posted once a return "
             "request has been approved and the goods have been received.")
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help="Leave empty to share the reason between all companies.")
    active = fields.Boolean(default=True)
