# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cl_handover_date_sync = fields.Selection(
        related='company_id.cl_handover_date_sync', readonly=False)
    cl_handover_move_agreed_date = fields.Boolean(
        related='company_id.cl_handover_move_agreed_date', readonly=False)
    cl_handover_notify = fields.Boolean(
        related='company_id.cl_handover_notify', readonly=False)
    cl_handover_event_date = fields.Boolean(
        related='company_id.cl_handover_event_date', readonly=False)
    cl_handover_collection_email = fields.Boolean(
        related='company_id.cl_handover_collection_email', readonly=False)
    cl_handover_reminder_days = fields.Integer(
        related='company_id.cl_handover_reminder_days', readonly=False)
    cl_handover_reminder_max = fields.Integer(
        related='company_id.cl_handover_reminder_max', readonly=False)
