# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, format_amount


class AccountMove(models.Model):
    _inherit = 'account.move'

    cl_credit_reason_id = fields.Many2one(
        'cl.credit.note.reason', string='Credit Note Reason',
        copy=False, tracking=True, index='btree_not_null')
    cl_return_request_ids = fields.One2many(
        'cl.return.request', 'credit_note_id', string='Return Requests',
        # same audience as the requests: reading an invoice must not fail for
        # a user (a salesperson, say) who has no access to them
        groups='account.group_account_invoice,account.group_account_readonly,'
               'stock.group_stock_user')
    cl_return_request_count = fields.Integer(
        compute='_compute_cl_return_status', compute_sudo=True)
    cl_return_status = fields.Selection(
        selection=[
            ('to_request', 'Return To Request'),
            ('to_approve', 'Return Waiting For Approval'),
            ('to_receive', 'Goods To Receive'),
            ('received', 'Goods Received'),
            ('rejected', 'Return Rejected'),
        ],
        string='Goods Return',
        compute='_compute_cl_return_status', compute_sudo=True,
        help="Where the return of the goods stands, for a credit note whose "
             "reason requires them to come back.")

    @api.depends('move_type', 'cl_credit_reason_id.requires_return',
                 'cl_return_request_ids.state', 'cl_return_request_ids.is_received')
    def _compute_cl_return_status(self):
        for move in self:
            requests = move.cl_return_request_ids.sorted('id', reverse=True)
            move.cl_return_request_count = len(requests)
            live = requests.filtered(lambda r: r.state in ('to_approve', 'approved'))[:1]
            if live.state == 'to_approve':
                status = 'to_approve'
            elif live:
                status = 'received' if live.is_received else 'to_receive'
            elif move.move_type == 'out_refund' and move.cl_credit_reason_id.requires_return:
                status = 'rejected' if requests[:1].state == 'rejected' else 'to_request'
            else:
                status = False
            move.cl_return_status = status

    # ------------------------------------------------------------------
    # What a credit note may credit
    # ------------------------------------------------------------------
    def _cl_product_totals(self):
        """Per product, over the product lines of ``self``:
        [quantity, highest unit price], both in the product's own unit of
        measure. Lines without a product are not concerned."""
        totals = defaultdict(lambda: [0.0, 0.0])
        for line in self.invoice_line_ids:
            product = line.product_id
            if line.display_type != 'product' or not product:
                continue
            uom = line.product_uom_id or product.uom_id
            entry = totals[product]
            entry[0] += uom._compute_quantity(line.quantity, product.uom_id, round=False)
            entry[1] = max(entry[1], uom._compute_price(line.price_unit, product.uom_id))
        return totals

    def _cl_check_credit_limits(self):
        """A credit note made from an invoice cannot give back more than the
        invoice charged: no other product, no more quantity than is left after
        the other credit notes, no higher unit price, no higher total.
        Everything that is wrong is reported in one message."""
        price_digits = self.env['decimal.precision'].precision_get('Product Price')
        for credit in self:
            invoice = credit.reversed_entry_id
            if credit.move_type != 'out_refund' or not invoice:
                continue
            others = self.env['account.move'].search([
                ('reversed_entry_id', '=', invoice.id),
                ('move_type', '=', 'out_refund'),
                ('state', '!=', 'cancel'),
                ('id', '!=', credit.id),
            ])
            invoiced = invoice._cl_product_totals()
            credited_before = others._cl_product_totals()
            same_currency = credit.currency_id == invoice.currency_id
            problems = []
            for product, (qty, price) in credit._cl_product_totals().items():
                if product not in invoiced:
                    problems.append(_(
                        "%s is not on the invoice.", product.display_name))
                    continue
                invoiced_qty, invoiced_price = invoiced[product]
                left = max(invoiced_qty - credited_before.get(product, (0.0, 0.0))[0], 0.0)
                rounding = product.uom_id.rounding
                if float_compare(qty, left, precision_rounding=rounding) > 0:
                    problems.append(_(
                        "%(product)s: %(qty)s %(uom)s credited, only %(left)s left to credit.",
                        product=product.display_name, qty=qty, left=left,
                        uom=product.uom_id.name))
                if same_currency and float_compare(
                        price, invoiced_price, precision_digits=price_digits) > 0:
                    problems.append(_(
                        "%(product)s: unit price %(price)s is higher than the invoiced %(invoiced)s.",
                        product=product.display_name, price=price, invoiced=invoiced_price))
            if same_currency:
                total = credit.amount_untaxed + sum(others.mapped('amount_untaxed'))
                if credit.currency_id.compare_amounts(total, invoice.amount_untaxed) > 0:
                    problems.append(_(
                        "Credit notes would total %(total)s for an invoice of %(invoice)s (untaxed).",
                        total=format_amount(self.env, total, credit.currency_id),
                        invoice=format_amount(self.env, invoice.amount_untaxed, invoice.currency_id)))
            if problems:
                raise ValidationError(_(
                    "This credit note gives back more than invoice %(invoice)s charged:\n%(problems)s",
                    invoice=invoice.name,
                    problems='\n'.join('- %s' % problem for problem in problems)))

    def _cl_check_goods_returned(self):
        """A credit note whose reason requires a return is posted only once the
        return was approved and the goods are back."""
        for credit in self:
            if credit.move_type != 'out_refund' \
                    or not credit.cl_credit_reason_id.requires_return:
                continue
            status = credit.cl_return_status
            if status == 'received':
                continue
            if status == 'to_request':
                why = _(
                    "The reason '%s' requires the goods to come back: use "
                    "'Request Return' first, or choose another reason.",
                    credit.cl_credit_reason_id.name)
            elif status == 'rejected':
                why = _(
                    "The return of the goods was rejected. Request it again or "
                    "choose a reason that does not require a return.")
            elif status == 'to_approve':
                why = _("The return request is still waiting for approval.")
            else:
                why = _("The return was approved but the goods have not been "
                        "received yet.")
            raise ValidationError(_(
                "%(credit_note)s cannot be posted. %(why)s",
                credit_note=credit.display_name, why=why))

    def _post(self, soft=True):
        # _post is the one door every posting goes through: the Confirm
        # button, 'Reverse and Create Invoice', automatic posting, imports.
        self._cl_check_credit_limits()
        self._cl_check_goods_returned()
        return super()._post(soft=soft)

    # ------------------------------------------------------------------
    # Goods return
    # ------------------------------------------------------------------
    def _cl_delivery_moves(self):
        """Done stock moves that delivered what ``self`` (invoices) charged."""
        return self.invoice_line_ids.sale_line_ids.move_ids.filtered(
            lambda move: move.state == 'done'
            and move.location_dest_id.usage == 'customer'
            and not move.origin_returned_move_id)

    def action_cl_request_return(self):
        self.ensure_one()
        request = self.env['cl.return.request']._cl_request_for(self)
        return request._get_records_action(name=_("Return Request"))

    def action_cl_view_return_requests(self):
        self.ensure_one()
        return self.cl_return_request_ids._get_records_action(name=_("Return Requests"))
