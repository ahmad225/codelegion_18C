# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_handover_date_sync = fields.Selection(
        [('none', 'Do not change it'),
         ('done', 'When manufacturing is done'),
         ('planned', 'Follow the planned end of manufacturing')],
        string='Delivery Date from Manufacturing', default='planned', required=True,
        help='How the Delivery Date of a sales order follows its manufacturing orders. '
             'The latest manufacturing order counts.')
    cl_handover_move_agreed_date = fields.Boolean(
        string='Move Agreed Delivery Dates',
        help='A Delivery Date entered by hand is the date agreed with the customer. '
             'Off: it is never changed, the salesperson gets a note when production will '
             'finish later. On: it is moved to the later date, with a note to the salesperson. '
             'Agreed dates are never moved earlier.')
    cl_handover_notify = fields.Boolean(
        string='Hand Over to Warehouse', default=True,
        help='Finished manufacturing orders can be handed over to the warehouse. '
             'When all of them are, the salesperson gets a "Ready for Delivery" activity.')
    cl_handover_event_date = fields.Boolean(
        string='Customer Event Date', default=True,
        help='Sales orders can carry the date of the customer\'s event; it is shown on '
             'their manufacturing orders.')
    cl_handover_collection_email = fields.Boolean(
        string='Ready for Collection Email', default=True,
        help='Email the customer when the delivery order of an order with a '
             '"Customer Collection" delivery method is ready.')
    cl_handover_reminder_days = fields.Integer(
        string='Reminder Interval (days)', default=3,
        help='Days between the Ready for Collection email and each reminder.')
    cl_handover_reminder_max = fields.Integer(
        string='Maximum Reminders', default=3,
        help='Reminders sent per delivery order at most. 0 = no reminders.')

    @api.constrains('cl_handover_reminder_days', 'cl_handover_reminder_max')
    def _check_cl_handover_reminders(self):
        for company in self:
            if company.cl_handover_reminder_max < 0:
                raise ValidationError(_("The maximum number of collection reminders cannot be negative."))
            if company.cl_handover_reminder_days < 1:
                raise ValidationError(_("The collection reminder interval must be at least one day."))
