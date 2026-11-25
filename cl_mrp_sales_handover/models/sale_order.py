# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import _, api, fields, models
from odoo.tools import format_date

READY_ACTIVITY = 'cl_mrp_sales_handover.mail_act_cl_handover_ready'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cl_event_date = fields.Date(
        string='Event Date', copy=False, tracking=True,
        help='Date of the customer\'s event the goods are needed for. '
             'Shown on the manufacturing orders of this order.')
    cl_event_note = fields.Char(
        string='Event Note', copy=False,
        help='Short note about the event, shown to production.')
    cl_handover_event_enabled = fields.Boolean(related='company_id.cl_handover_event_date')
    cl_production_ids = fields.One2many(
        'mrp.production', 'cl_sale_order_id', string='Linked Manufacturing Orders', readonly=True)
    cl_mfg_finish_date = fields.Datetime(
        string='Manufacturing Ready By', compute='_compute_cl_handover', store=True,
        help='Latest end of the manufacturing orders of this order: planned end while they '
             'run, actual end once done.')
    cl_handover_state = fields.Selection(
        [('waiting', 'In Production'),
         ('partial', 'Partially Handed Over'),
         ('done', 'Handed Over')],
        string='Warehouse Handover', compute='_compute_cl_handover', store=True, index=True)
    cl_commitment_by_mfg = fields.Boolean(
        string='Delivery Date from Manufacturing', copy=False, readonly=True,
        help='Set when the Delivery Date was filled by manufacturing. A date entered by '
             'hand counts as agreed with the customer.')
    cl_late_notified_date = fields.Date(copy=False, readonly=True)
    cl_ready_notified = fields.Boolean(copy=False, readonly=True)
    cl_event_at_risk = fields.Boolean(compute='_compute_cl_event_at_risk')

    @api.depends('cl_production_ids.state', 'cl_production_ids.date_finished',
                 'cl_production_ids.cl_handed_over',
                 'cl_production_ids.move_dest_ids.raw_material_production_id')
    def _compute_cl_handover(self):
        for order in self:
            finals = order.cl_production_ids._cl_final_productions()
            order.cl_mfg_finish_date = max(
                finals.filtered('date_finished').mapped('date_finished'), default=False)
            if not finals:
                order.cl_handover_state = False
            elif all(finals.mapped('cl_handed_over')):
                order.cl_handover_state = 'done'
            elif any(finals.mapped('cl_handed_over')):
                order.cl_handover_state = 'partial'
            else:
                order.cl_handover_state = 'waiting'

    @api.depends('cl_event_date', 'cl_mfg_finish_date', 'state')
    def _compute_cl_event_at_risk(self):
        for order in self:
            order.cl_event_at_risk = bool(
                order.state == 'sale' and order.cl_event_date and order.cl_mfg_finish_date
                and order._cl_local_date(order.cl_mfg_finish_date) > order.cl_event_date)

    # ---- helpers ----

    def _cl_local_date(self, value):
        return fields.Datetime.context_timestamp(self, value).date()

    def _cl_format(self, value):
        return format_date(self.env, self._cl_local_date(value))

    def _cl_notify_salesperson(self, body):
        """A note that really notifies the salesperson (inbox / email)."""
        self.ensure_one()
        # Triggered by production steps: a shop-floor user may have no email address,
        # which message_post refuses. Post as OdooBot in that case.
        extra = {}
        if not self.env.user.partner_id.email:
            extra['author_id'] = self.env.ref('base.partner_root').id
        self.message_post(body=body, subtype_xmlid='mail.mt_note',
                          partner_ids=self.user_id.partner_id.ids, **extra)

    # ---- write ----

    def write(self, vals):
        if 'commitment_date' in vals and not self.env.context.get('cl_handover_sync'):
            # Typed by a person: from now on this is the date agreed with the customer.
            vals = dict(vals, cl_commitment_by_mfg=False, cl_late_notified_date=False)
        event_fields = {'cl_event_date', 'cl_event_note'}.intersection(vals)
        before = {order.id: (order.cl_event_date, order.cl_event_note) for order in self} \
            if event_fields else {}
        res = super().write(vals)
        if event_fields:
            self._cl_log_event_change(before)
        return res

    def _cl_log_event_change(self, before):
        # The MO fields are stored related fields kept up to date by the ORM as superuser,
        # so the salesperson needs no manufacturing rights. Production gets a log line.
        for order in self.sudo():
            if before.get(order.id) == (order.cl_event_date, order.cl_event_note):
                continue
            productions = order.cl_production_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            if not productions:
                continue
            if order.cl_event_date:
                body = _("Event date on %(order)s changed to %(date)s%(note)s.",
                         order=order.name, date=format_date(self.env, order.cl_event_date),
                         note=(' (%s)' % order.cl_event_note) if order.cl_event_note else '')
            else:
                body = _("Event date removed from %s.", order.name)
            for production in productions:
                production._message_log(body=body)

    # ---- delivery date from manufacturing ----

    def _cl_sync_commitment_date(self):
        for order in self.sudo():
            company = order.company_id
            mode = company.cl_handover_date_sync
            if mode == 'none' or order.state != 'sale' or order.delivery_status == 'full':
                continue
            finals = order.cl_production_ids._cl_final_productions()
            if not finals or (mode == 'done' and any(p.state != 'done' for p in finals)):
                continue
            target = order.cl_mfg_finish_date
            if not target:
                continue
            current = order.commitment_date
            if current and current.date() == target.date():
                continue
            names = ', '.join(finals.mapped('name'))
            agreed = bool(current) and not order.cl_commitment_by_mfg
            if agreed:
                if target.date() < current.date():
                    continue  # an agreed date is never moved earlier
                if not company.cl_handover_move_agreed_date:
                    if order.cl_late_notified_date != target.date():
                        order._cl_notify_salesperson(_(
                            "Manufacturing (%(mos)s) now expects to finish on %(new)s, after the "
                            "Delivery Date agreed with the customer (%(old)s). The Delivery Date "
                            "was not changed.",
                            mos=names, new=order._cl_format(target), old=order._cl_format(current)))
                        order.cl_late_notified_date = target.date()
                    continue
            order.with_context(cl_handover_sync=True).write({
                'commitment_date': target,
                'cl_commitment_by_mfg': True,
                'cl_late_notified_date': False,
            })
            if current and target.date() > current.date():
                order._cl_notify_salesperson(_(
                    "Delivery Date moved from %(old)s to %(new)s%(agreed)s: manufacturing "
                    "(%(mos)s) finishes later.",
                    old=order._cl_format(current), new=order._cl_format(target),
                    agreed=_(" (date agreed with the customer)") if agreed else '', mos=names))
            elif current:
                order._message_log(body=_(
                    "Delivery Date moved from %(old)s to %(new)s following manufacturing (%(mos)s).",
                    old=order._cl_format(current), new=order._cl_format(target), mos=names))
            else:
                order._message_log(body=_(
                    "Delivery Date set to %(new)s following manufacturing (%(mos)s).",
                    new=order._cl_format(target), mos=names))

    # ---- handover ----

    def _cl_update_ready_activity(self):
        for order in self.sudo():
            if order.cl_handover_state == 'done':
                if order.cl_ready_notified or not order.company_id.cl_handover_notify:
                    continue
                order.activity_schedule(
                    READY_ACTIVITY,
                    summary=_('Ready for delivery'),
                    note=_("All manufacturing orders of %s have been handed over to the "
                           "warehouse. Plan the delivery or collection.", order.name),
                    user_id=order.user_id.id or self.env.uid,
                )
                order.cl_ready_notified = True
            elif order.cl_ready_notified:
                order.activity_unlink([READY_ACTIVITY])
                order.cl_ready_notified = False
                order._cl_notify_salesperson(_(
                    "%s is no longer fully handed over to the warehouse.", order.name))
