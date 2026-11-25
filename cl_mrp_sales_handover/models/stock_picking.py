# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

READY_TEMPLATE = 'cl_mrp_sales_handover.mail_template_cl_collection_ready'
REMINDER_TEMPLATE = 'cl_mrp_sales_handover.mail_template_cl_collection_reminder'


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    cl_collection_ready_sent = fields.Datetime(
        string='Ready for Collection Sent', copy=False, readonly=True)
    cl_collection_reminder_count = fields.Integer(
        string='Collection Reminders Sent', copy=False, readonly=True)
    cl_collection_next_reminder = fields.Datetime(
        string='Next Collection Reminder', copy=False, readonly=True, index='btree_not_null')

    # ---- helpers ----

    def _cl_is_collection(self):
        self.ensure_one()
        carrier = self.carrier_id or self.sale_id.carrier_id
        return bool(carrier.cl_handover_collection)

    def _cl_is_ready_for_collection(self):
        """The customer's delivery order with every move fully reserved and every
        previous step (pick, pack, manufacturing) finished."""
        self.ensure_one()
        moves = self.move_ids.filtered(lambda m: m.state != 'cancel')
        return bool(
            self.picking_type_code == 'outgoing'
            and self.state == 'assigned'
            and moves
            and all(move.state == 'assigned' for move in moves)
            and all(orig.state in ('done', 'cancel') for orig in moves.move_orig_ids))

    def _cl_collection_partner(self):
        self.ensure_one()
        return self.sale_id.partner_id or self.partner_id

    def _cl_send_collection_email(self, template, reminder=False):
        """Queue the email (never sent inside the current transaction). Returns False
        when nothing could be sent, so no reminders are planned."""
        self.ensure_one()
        partner = self._cl_collection_partner()
        label = _('Collection reminder') if reminder else _('Ready for Collection email')
        if not template:
            self._message_log(body=_("%s not sent: its email template has been deleted.", label))
            return False
        if not partner.email:
            self._message_log(body=_("%(label)s not sent: %(partner)s has no email address.",
                                     label=label, partner=partner.display_name or _("the customer")))
            return False
        template.send_mail(self.id, email_layout_xmlid='mail.mail_notification_light')
        body = _("%(label)s sent to %(partner)s for %(picking)s.",
                 label=label, partner=partner.display_name, picking=self.name)
        self._message_log(body=body)
        if self.sale_id:
            self.sale_id._message_log(body=body)
        return True

    # ---- ready for collection ----

    def _cl_notify_collection_ready(self):
        template = self.env.ref(READY_TEMPLATE, raise_if_not_found=False)
        for picking in self.sudo():
            company = picking.company_id
            if (picking.cl_collection_ready_sent or not company.cl_handover_collection_email
                    or not picking.sale_id or not picking._cl_is_collection()
                    or not picking._cl_is_ready_for_collection()):
                continue
            now = fields.Datetime.now()
            sent = picking._cl_send_collection_email(template.sudo() if template else template)
            plan = sent and company.cl_handover_reminder_max > 0
            picking.write({
                'cl_collection_ready_sent': now,
                'cl_collection_reminder_count': 0,
                'cl_collection_next_reminder':
                    now + timedelta(days=company.cl_handover_reminder_days) if plan else False,
            })

    # ---- reminders ----

    def _cl_send_collection_reminder(self, template):
        self.ensure_one()
        company = self.company_id
        maximum = company.cl_handover_reminder_max
        if (not company.cl_handover_collection_email or maximum <= 0
                or self.cl_collection_reminder_count >= maximum):
            self.cl_collection_next_reminder = False
            return
        interval = timedelta(days=company.cl_handover_reminder_days)
        if not self._cl_is_ready_for_collection():
            # Goods unreserved again: wait, do not tell the customer they are ready.
            self.cl_collection_next_reminder = fields.Datetime.now() + interval
            return
        if not self._cl_send_collection_email(template, reminder=True):
            self.cl_collection_next_reminder = False
            return
        count = self.cl_collection_reminder_count + 1
        self.write({
            'cl_collection_reminder_count': count,
            'cl_collection_next_reminder': fields.Datetime.now() + interval if count < maximum else False,
        })

    @api.model
    def _cl_cron_collection_reminders(self, batch_size=100):
        """Daily job. Each delivery order is handled in its own savepoint: the email is
        queued and the counter moved in the same step, so a failure sends nothing and a
        second run never repeats a reminder. Done or cancelled deliveries drop out."""
        now = fields.Datetime.now()
        domain = [
            ('cl_collection_next_reminder', '!=', False),
            ('cl_collection_next_reminder', '<=', now),
            ('state', 'not in', ('done', 'cancel')),
        ]
        Picking = self.sudo()
        template = self.env.ref(REMINDER_TEMPLATE, raise_if_not_found=False)
        template = template.sudo() if template else template
        pickings = Picking.search(domain, order='cl_collection_next_reminder, id', limit=batch_size)
        for picking in pickings:
            try:
                with self.env.cr.savepoint():
                    picking._cl_send_collection_reminder(template)
            except Exception:
                _logger.exception("Collection reminder failed for delivery order %s", picking.id)
                self.env.invalidate_all(flush=False)
                # Retry tomorrow so one broken record never blocks the queue.
                picking.cl_collection_next_reminder = now + timedelta(days=1)
        self.env['ir.cron']._notify_progress(done=len(pickings), remaining=Picking.search_count(domain))
        return True

    # ---- stop when collected or cancelled ----

    def _action_done(self):
        res = super()._action_done()
        self.filtered(lambda p: p.state == 'done' and p.cl_collection_next_reminder).sudo().write(
            {'cl_collection_next_reminder': False})
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.filtered(lambda p: p.state == 'cancel' and p.cl_collection_next_reminder).sudo().write(
            {'cl_collection_next_reminder': False})
        return res
