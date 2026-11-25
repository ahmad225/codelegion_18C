# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.tools import clean_context, formatLang
from odoo.tools.misc import format_date

RELOAD = {'type': 'ir.actions.client', 'tag': 'soft_reload'}


class CreditApprovalRequest(models.TransientModel):
    _name = 'cl.credit.approval.request'
    _description = "Credit Approval Request"

    order_id = fields.Many2one(
        'sale.order', string="Quotation", required=True, readonly=True, ondelete='cascade')
    partner_id = fields.Many2one(
        related='order_id.partner_id', string="Customer")
    cl_credit_state = fields.Selection(related='order_id.cl_credit_state')
    reason_html = fields.Html(
        string="Why It Is Blocked", compute='_compute_details', sanitize=False)
    overdue_html = fields.Html(
        string="Overdue Items", compute='_compute_details', sanitize=False)
    note = fields.Text(
        string="Note for the Credit Manager",
        help="Anything the approver should know, e.g. a payment promised by the customer.")

    @api.depends('order_id')
    def _compute_details(self):
        today = fields.Date.context_today(self)
        for wizard in self:
            order = wizard.order_id
            issues = order._cl_credit_issues() if order else []
            wizard.reason_html = order._cl_credit_reasons_html(issues) if issues else False
            rows = Markup("")
            currency = order.company_id.currency_id
            for issue in issues:
                # values are escaped by Markup's % formatting
                for line in issue.get('lines', []):
                    rows += Markup(
                        "<tr><td>%s</td><td>%s</td>"
                        "<td class='text-end'>%s</td><td class='text-end'>%s</td></tr>"
                    ) % (
                        line.move_id.name or line.name or "",
                        format_date(self.env, line.date_maturity),
                        (today - line.date_maturity).days,
                        formatLang(self.env, line.amount_residual, currency_obj=currency),
                    )
            if rows:
                wizard.overdue_html = Markup(
                    "<table class='table table-sm mb-0'><thead><tr>"
                    "<th>%s</th><th>%s</th><th class='text-end'>%s</th><th class='text-end'>%s</th>"
                    "</tr></thead><tbody>%s</tbody></table>"
                ) % (_("Document"), _("Due Date"), _("Days Overdue"), _("Amount Due"), rows)
            else:
                wizard.overdue_html = False

    def _cl_credit_order(self):
        """The quotation, without the dialog's ``default_*`` context keys:
        they must not leak into the records made when the order is confirmed."""
        self.ensure_one()
        return self.order_id.with_context(clean_context(self.env.context))

    def action_request(self):
        self._cl_credit_order()._cl_credit_request(self.note)
        return RELOAD

    def action_approve(self):
        """Credit Managers can approve straight from the dialog."""
        self._cl_credit_order().action_cl_credit_approve()
        return RELOAD
