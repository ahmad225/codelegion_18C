# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class RatingRating(models.Model):
    _inherit = 'rating.rating'

    def _cl_is_product_review(self):
        self.ensure_one()
        return self.res_model == 'product.template' and self.res_id and self.consumed

    def _cl_review_notification_company(self):
        """Company whose team hears about this review.

        The product's own company comes first, then the company of the website
        the review was posted on, then the current company. The first one that
        has both a template and recipients is used, so a company without its
        own setup falls back to the shop's.
        """
        self.ensure_one()
        product = self.env['product.template'].sudo().browse(self.res_id).exists()
        companies = (
            product.company_id
            | self.env['website'].get_current_website().company_id
            | self.env.company
        ).sudo()
        return companies.filtered(
            lambda c: c.cl_rating_template_id and c.cl_rating_partner_ids)[:1]

    def _cl_notify_product_review(self, updated=False):
        # sudo: the review is saved in the customer's own session, and the
        # customer may read neither the template nor the recipients.
        for rating in self.sudo().filtered(lambda r: r._cl_is_product_review()):
            company = rating._cl_review_notification_company()
            if not company:
                continue
            template = company.cl_rating_template_id
            email_values = {'recipient_ids': [(6, 0, company.cl_rating_partner_ids.ids)]}
            if not template.email_from and company.email_formatted:
                # A template without a sender must not fall back to the
                # address of whoever is logged in.
                email_values['email_from'] = company.email_formatted
            try:
                # Savepoint: a broken template must never stop the customer
                # from posting the review.
                with self.env.cr.savepoint():
                    # Queued (force_send=False): the reviewer never waits for SMTP.
                    template.with_context(
                        cl_review_updated=updated,
                        cl_company_email=company.email_formatted,
                        cl_company_name=company.name,
                    ).send_mail(rating.id, force_send=False, raise_exception=False,
                                email_values=email_values)
            except Exception:  # pylint: disable=broad-except
                _logger.exception(
                    "Review notification for rating %s could not be prepared with template %s",
                    rating.id, template.id)

    @api.model_create_multi
    def create(self, vals_list):
        ratings = super().create(vals_list)
        ratings._cl_notify_product_review()
        return ratings

    def write(self, vals):
        if not {'rating', 'feedback', 'consumed'} & set(vals):
            return super().write(vals)
        before = {
            rating.id: (rating.consumed, rating.rating, rating.feedback or '')
            for rating in self.sudo() if rating.res_model == 'product.template'
        }
        res = super().write(vals)
        new_ids, updated_ids = [], []
        for rating in self.sudo():
            old = before.get(rating.id)
            if not old or not rating.consumed:
                continue
            if not old[0]:
                # Filled in for the first time (rating request by email).
                new_ids.append(rating.id)
            elif old[1:] != (rating.rating, rating.feedback or ''):
                # Only a real change is worth an email, not every save.
                updated_ids.append(rating.id)
        self.browse(new_ids)._cl_notify_product_review()
        self.browse(updated_ids)._cl_notify_product_review(updated=True)
        return res
