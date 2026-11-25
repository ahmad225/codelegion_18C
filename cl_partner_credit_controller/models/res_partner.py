# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.sql import column_exists, create_column

CONTROLLER_COLUMN = 'cl_credit_controller_id'


def cl_precreate_credit_controller_column(cr, table):
    """Create the stored related column of ``table`` by hand when it is known
    to be empty, so that installing the module does not compute it record by
    record on large order and invoice tables.

    It is empty as long as no partner has a credit controller, which is
    always the case on a first install. In any other situation nothing is
    done here and the ORM computes the column as usual.
    """
    if column_exists(cr, table, CONTROLLER_COLUMN):
        return
    if column_exists(cr, 'res_partner', CONTROLLER_COLUMN):
        cr.execute("SELECT 1 FROM res_partner WHERE cl_credit_controller_id IS NOT NULL LIMIT 1")
        if cr.fetchone():
            return
    create_column(cr, table, CONTROLLER_COLUMN, 'int4')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cl_credit_controller_id = fields.Many2one(
        'res.users', string='Credit Controller', index='btree_not_null', tracking=True,
        domain="[('share', '=', False)]",
        help='Internal user who follows up payments for this customer. Set on the company; '
             'its contact persons follow it.')

    @api.constrains('cl_credit_controller_id')
    def _check_cl_credit_controller_internal(self):
        # Checked where the value is chosen (the company or individual), not on
        # the contacts it is copied to: the copy must never be refused.
        for partner in self.filtered(lambda p: p.commercial_partner_id == p):
            controller = partner.cl_credit_controller_id
            if controller.sudo().share:
                raise ValidationError(_(
                    "%s is a portal user. Only internal users can be credit controllers.",
                    controller.name))

    @api.model
    def _commercial_fields(self):
        # Odoo copies commercial fields from the company to every contact below it
        # (on create, on change of parent and on every change of the company).
        return super()._commercial_fields() + ['cl_credit_controller_id']

    def action_cl_sync_credit_controller(self):
        """Copy the credit controller of the selected customers' companies to all
        their contacts (for data loaded without going through the ORM)."""
        commercial = self.commercial_partner_id
        before = {
            partner.id: partner.cl_credit_controller_id
            for partner in self.search([('commercial_partner_id', 'in', commercial.ids)])
        }
        for partner in commercial:
            partner._commercial_sync_to_children(['cl_credit_controller_id'])
        changed = sum(
            1 for partner in self.browse(list(before))
            if partner.cl_credit_controller_id != before[partner.id]
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Credit Controller'),
                'message': _('%s contact(s) updated.', changed),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
