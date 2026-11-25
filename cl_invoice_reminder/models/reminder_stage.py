# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import Counter

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class InvoiceReminderStage(models.Model):
    """A step of the reminder schedule of a company: how long after the due
    date it applies and which email it sends."""
    _name = 'cl.invoice.reminder.stage'
    _description = 'Invoice Reminder Stage'
    _order = 'company_id, delay_days, id'

    name = fields.Char(
        string='Stage',
        required=True,
        help="How this stage is called on invoices and in the list of "
             "reminders sent, e.g. 'First reminder' or 'Final notice'.",
    )
    delay_days = fields.Integer(
        string='Days After Due Date',
        required=True,
        default=7,
        help="The reminder is sent once the invoice has been unpaid for this "
             "many days after its due date.",
    )
    template_id = fields.Many2one(
        'mail.template',
        string='Email',
        required=True,
        ondelete='restrict',
        domain=[('model', '=', 'res.partner')],
        default=lambda self: self.env.ref(
            'cl_invoice_reminder.email_template_overdue_invoices',
            raise_if_not_found=False),
        help="Email sent to the customer. It is written for a contact; the "
             "overdue invoices are available as ctx.get('cl_invoices').",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(
        default=True,
        help="An archived stage sends nothing any more, but invoices that "
             "already received it keep it in their history.",
    )

    @api.onchange('delay_days')
    def _onchange_delay_days(self):
        if not self.name and self.delay_days > 0:
            self.name = _("Reminder after %s days", self.delay_days)

    @api.constrains('delay_days', 'company_id', 'active')
    def _check_schedule(self):
        if any(stage.delay_days < 1 for stage in self):
            raise ValidationError(_(
                "A reminder stage must be at least one day after the due date."))
        companies = self.filtered('active').company_id
        if not companies:
            return
        schedule = Counter(
            (stage.company_id, stage.delay_days)
            for stage in self.sudo().search([('company_id', 'in', companies.ids)]))
        for (company, delay), count in schedule.items():
            if count > 1:
                raise ValidationError(_(
                    "%(company)s already has an active reminder stage %(days)s "
                    "days after the due date.",
                    company=company.display_name, days=delay))
