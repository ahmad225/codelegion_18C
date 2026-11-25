# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cl_rating_template_id = fields.Many2one(
        'mail.template', string='Review Email Template',
        domain="[('model', '=', 'rating.rating')]",
        default=lambda self: self.env.ref(
            'cl_product_rating_notification.mail_template_product_rating',
            raise_if_not_found=False))
    cl_rating_partner_ids = fields.Many2many(
        'res.partner', 'cl_company_rating_partner_rel', 'company_id', 'partner_id',
        string='Review Notification Recipients')
