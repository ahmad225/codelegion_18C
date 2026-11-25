# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    # --- low margin alerts (information only) -------------------------
    cl_margin_line_alert = fields.Boolean(
        string='Highlight Low-Margin Lines',
        help="Highlight the order lines whose margin is under the percentage below.")
    cl_margin_line_alert_below = fields.Float(
        string='Line Margin Under (%)', default=15.0)
    cl_margin_order_alert = fields.Boolean(
        string='Warn on Low-Margin Orders',
        help="Show a banner on a quotation whose overall margin is under the "
             "percentage below.")
    cl_margin_order_alert_below = fields.Float(
        string='Order Margin Under (%)', default=15.0)

    # --- margin floor (needs approval) --------------------------------
    cl_margin_floor_enabled = fields.Boolean(
        string='Approval Under a Margin Floor',
        help="A quotation whose margin is under the floor cannot be confirmed "
             "until a margin approver approves it.")
    cl_margin_floor = fields.Float(
        string='Margin Floor (%)', default=10.0)
    cl_margin_approver_group_id = fields.Many2one(
        'res.groups', string='Margin Approvers',
        domain="[('share', '=', False)]",
        help="The members of this group approve quotations under the margin "
             "floor and get the approval activity. They need access to the "
             "quotations they approve. Leave empty to let the Sales "
             "Administrators approve.")
    cl_margin_skip_automatic = fields.Boolean(
        string='Let Automatic Confirmations Through',
        default=True,
        help="Orders confirmed by the system (online payment, customer signature, "
             "eCommerce, other automations) are confirmed even under the margin "
             "floor, and a note is logged on the order. Untick to hold those "
             "for approval as well.")

    @api.constrains('cl_margin_line_alert_below', 'cl_margin_order_alert_below', 'cl_margin_floor')
    def _check_cl_margin_percentages(self):
        for company in self:
            for value in (company.cl_margin_line_alert_below,
                          company.cl_margin_order_alert_below,
                          company.cl_margin_floor):
                if value < 0 or value > 100:
                    raise ValidationError(_(
                        "Margin percentages must be between 0 and 100."))
