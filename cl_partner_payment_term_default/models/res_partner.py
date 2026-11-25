# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from collections import defaultdict

from odoo import _, api, fields, models

TERM_FIELDS = ('property_payment_term_id', 'property_supplier_payment_term_id')
# Context key set on the writes this module makes itself, so that they are
# stored as they are and do not start another round of synchronisation.
SYNC_KEY = 'cl_payment_term_sync'


class ResPartner(models.Model):
    """Payment terms of a company and of its contacts.

    The rule is deliberately simple: a contact has the payment terms of its
    company, in every company of the database, unless *Keep Own Payment Terms*
    is ticked on it. The box is ticked for the user as soon as a contact is
    given terms that differ from its company's, and unticking it brings the
    contact back in line.
    """
    _inherit = 'res.partner'

    cl_keep_own_payment_term = fields.Boolean(
        string='Keep Own Payment Terms',
        help="Ticked: this contact has its own customer and vendor payment "
             "terms, whatever the terms of its company.\n"
             "Not ticked: the contact always has the payment terms of its "
             "company.\n"
             "The box is ticked automatically when you give the contact "
             "payment terms that differ from its company's.")

    # ------------------------------------------------------------------
    # Core hook
    # ------------------------------------------------------------------

    @api.model
    def _commercial_fields(self):
        # Odoo copies "commercial fields" from the company onto each contact
        # without exception. Payment terms are taken out of that list and
        # handled below, where a contact may be left alone.
        return [name for name in super()._commercial_fields() if name not in TERM_FIELDS]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cl_payment_term_source(self):
        """The partner whose payment terms ``self`` follows: its commercial
        entity. Empty for a partner that is its own entity (a company, or a
        person without company). Also works on a record being edited."""
        self.ensure_one()
        if self.is_company or not self.parent_id:
            return self.browse()
        return self.parent_id.commercial_partner_id

    def _cl_differs_from_company_terms(self, values):
        """Whether ``values`` (ids keyed by payment term field) give ``self``
        something else than what its company has."""
        source = self._cl_payment_term_source()
        return bool(source) and any(
            (values[name] or False) != source[name].id for name in values)

    def _cl_contacts_following_terms(self):
        """Contacts, at any depth, that take their payment terms from the
        commercial entities in ``self``. Archived contacts are included so
        they are right when they come back."""
        if not self.ids:
            return self.browse()
        return self.with_context(active_test=False).search([
            ('commercial_partner_id', 'in', self.ids),
            ('id', 'not in', self.ids),
            ('cl_keep_own_payment_term', '=', False),
        ])

    def _cl_align_payment_terms(self):
        """Give the contacts in ``self`` that follow their company its payment
        terms, in every company of the database (the terms are stored per
        company). Only contacts that are really out of line are written.

        :return: the contacts that were changed.
        """
        contacts = self.sudo().filtered(
            lambda partner: partner._cl_payment_term_source()
            and not partner.cl_keep_own_payment_term)
        changed = self.browse()
        if not contacts:
            return changed
        for company in self.env['res.company'].sudo().search([]):
            contacts_in_company = contacts.with_company(company).with_context(**{SYNC_KEY: True})
            # Group the contacts by the terms they must get: one write each.
            ids_by_terms = defaultdict(list)
            for contact in contacts_in_company:
                source = contact._cl_payment_term_source()
                wanted = tuple(source[name].id for name in TERM_FIELDS)
                if wanted != tuple(contact[name].id for name in TERM_FIELDS):
                    ids_by_terms[wanted].append(contact.id)
            for wanted, contact_ids in ids_by_terms.items():
                contacts_in_company.browse(contact_ids).write(dict(zip(TERM_FIELDS, wanted)))
                changed |= self.browse(contact_ids)
        return changed

    # ------------------------------------------------------------------
    # Form feedback
    # ------------------------------------------------------------------

    @api.onchange('parent_id', 'is_company')
    def _onchange_cl_payment_term_source(self):
        source = self._cl_payment_term_source()
        if source and not self.cl_keep_own_payment_term:
            for name in TERM_FIELDS:
                self[name] = source[name]

    @api.onchange(*TERM_FIELDS)
    def _onchange_cl_own_payment_term(self):
        source = self._cl_payment_term_source()
        if source and any(self[name] != source[name] for name in TERM_FIELDS):
            self.cl_keep_own_payment_term = True

    @api.onchange('cl_keep_own_payment_term')
    def _onchange_cl_keep_own_payment_term(self):
        source = self._cl_payment_term_source()
        if source and not self.cl_keep_own_payment_term:
            for name in TERM_FIELDS:
                self[name] = source[name]

    # ------------------------------------------------------------------
    # Create / write
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        if self.env.context.get(SYNC_KEY):
            return partners
        own = self.browse()
        for partner, vals in zip(partners, vals_list):
            if partner.cl_keep_own_payment_term:
                continue
            # The web client sends every field of the form, empty ones too:
            # only terms that were really filled in count as a choice.
            given = {name: vals[name] for name in TERM_FIELDS if vals.get(name)}
            if given and partner._cl_differs_from_company_terms(given):
                own |= partner
        if own:
            own.with_context(**{SYNC_KEY: True}).write({'cl_keep_own_payment_term': True})
        (partners - own)._cl_align_payment_terms()
        return partners

    def write(self, vals):
        if self.env.context.get(SYNC_KEY):
            return super().write(vals)

        # Read what is being changed first: core removes keys from ``vals``.
        given = {name: vals[name] for name in TERM_FIELDS if name in vals}
        flag_given = 'cl_keep_own_payment_term' in vals
        follows_again = vals.get('cl_keep_own_payment_term') is False
        moved = bool(vals.get('parent_id')) or 'is_company' in vals

        res = super().write(vals)

        # 1. A contact that gets other terms than its company keeps them.
        own = self.browse()
        if given and not flag_given:
            own = self.filtered(
                lambda partner: not partner.cl_keep_own_payment_term
                and partner._cl_differs_from_company_terms(given))
            if own:
                own.with_context(**{SYNC_KEY: True}).write({'cl_keep_own_payment_term': True})

        # 2. New terms on a company go down to its contacts. A write changes
        #    the terms of the current company only, and so does this.
        if given:
            entities = self.filtered(lambda partner: not partner._cl_payment_term_source())
            followers = entities.sudo()._cl_contacts_following_terms()
            if followers:
                followers.with_context(**{SYNC_KEY: True}).write(given)

        # 3. A contact that stops keeping its own terms, or that moves to
        #    another company (taking its own contacts along), takes the terms
        #    of its company in every company.
        to_align = self.browse()
        if follows_again:
            to_align = self
        if moved:
            to_align = self.sudo().with_context(active_test=False).search(
                [('id', 'child_of', self.ids)])
        (to_align - own)._cl_align_payment_terms()
        return res

    # ------------------------------------------------------------------
    # Manual action
    # ------------------------------------------------------------------

    def action_cl_sync_payment_terms(self):
        """Actions menu on contacts: bring the selected contacts, and all the
        contacts of the selected companies, back in line with their company
        in every company of the database. Contacts keeping their own terms
        are left alone."""
        self.check_access('write')
        selected = self.sudo()
        entities = selected.filtered(lambda partner: not partner._cl_payment_term_source())
        contacts = (selected - entities) | self.sudo().with_context(active_test=False).search([
            ('commercial_partner_id', 'in', entities.ids),
            ('id', 'not in', entities.ids),
        ])
        kept = contacts.filtered('cl_keep_own_payment_term')
        changed = (contacts - kept)._cl_align_payment_terms()
        message = _(
            "%(changed)s contact(s) updated, %(same)s already had the terms "
            "of their company.",
            changed=len(changed), same=len(contacts) - len(kept) - len(changed))
        if kept:
            message += " " + _(
                "%(kept)s contact(s) keep their own terms and were not touched.",
                kept=len(kept))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Payment terms of contacts"),
                'message': message,
                'type': 'success' if changed else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
