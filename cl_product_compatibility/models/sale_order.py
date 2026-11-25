# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_MANAGER_GROUP = 'sales_team.group_sale_manager'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Not stored: computed on demand, so editing a group never rewrites old orders.
    cl_compatibility_warning = fields.Text(
        string='Compatibility Warning', compute='_compute_cl_compatibility_warning',
        compute_sudo=True)
    cl_compatibility_override = fields.Boolean(
        string='Compatibility Overridden', copy=False, tracking=True)

    def _cl_order_products(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: l.product_id and not l.display_type and l.product_uom_qty > 0
        ).product_id

    def _cl_compatibility_mismatches(self):
        """Pairs (a, b) that share a compatibility group, are not compatible, and
        neither of which has a compatible partner elsewhere on the order."""
        self.ensure_one()
        products = self._cl_order_products().sorted('id')
        if len(products) < 2:
            return []
        company = self.company_id
        group_ids = {
            product.id: set(product.cl_compatibility_group_ids.filtered(
                lambda g: g.active and (not g.company_id or g.company_id == company)).ids)
            for product in products
        }
        grouped = products.filtered(lambda product: group_ids[product.id])
        if len(grouped) < 2:
            return []

        # Compatible partners present on the order, in both directions.
        on_order = set(products.ids)
        partners = {product.id: set() for product in products}
        for product in products:
            for other_id in set(product.cl_compatible_product_ids.ids) & on_order:
                if other_id != product.id:
                    partners[product.id].add(other_id)
                    partners[other_id].add(product.id)

        mismatches = []
        for index, first in enumerate(grouped):
            for second in grouped[index + 1:]:
                if not (group_ids[first.id] & group_ids[second.id]):
                    continue
                if second.id in partners[first.id]:
                    continue
                if partners[first.id] or partners[second.id]:
                    continue
                mismatches.append((first, second))
        return mismatches

    def _cl_compatibility_messages(self, website=False):
        self.ensure_one()
        messages = []
        for first, second in self._cl_compatibility_mismatches():
            message = _("'%(first)s' is not compatible with '%(second)s'.",
                        first=first.display_name, second=second.display_name)
            options = (first.cl_compatible_product_ids | second.cl_compatible_product_ids)
            options = options.filtered(
                lambda p: p.active and p.sale_ok
                and (not p.company_id or p.company_id == self.company_id))
            if website and 'is_published' in options._fields:
                options = options.filtered('is_published')
            if options:
                message += ' ' + _("Compatible options: %s.", ', '.join(options.mapped('display_name')))
            messages.append(message)
        return messages

    @api.depends('order_line.product_id', 'order_line.product_uom_qty', 'state')
    def _compute_cl_compatibility_warning(self):
        for order in self:
            if order.state not in ('draft', 'sent'):
                order.cl_compatibility_warning = False
                continue
            messages = order._cl_compatibility_messages()
            order.cl_compatibility_warning = '\n'.join(messages) if messages else False

    def write(self, vals):
        if 'order_line' in vals and 'cl_compatibility_override' not in vals:
            # Changing the lines invalidates an earlier override.
            vals = dict(vals, cl_compatibility_override=False)
        return super().write(vals)

    def _cl_log_compatibility_note(self, title, messages):
        self.ensure_one()
        # A log note: nobody has to be notified, and it also works for users
        # who have no email address.
        self._message_log(body=Markup("<p><b>%s</b></p><ul>%s</ul>") % (
            title, Markup('').join(Markup("<li>%s</li>") % message for message in messages)))

    def action_confirm(self):
        if not self.env.context.get('cl_skip_compatibility'):
            blocked = []
            for order in self:
                if order.cl_compatibility_override:
                    continue
                messages = order._cl_compatibility_messages()
                if not messages:
                    continue
                if self.env.su:
                    # Confirmed by the system or on behalf of the customer
                    # (online payment, signature, scheduled action). Refusing
                    # here would leave a paid order unconfirmed: let it
                    # through and leave a trace for the sales team.
                    order._cl_log_compatibility_note(
                        _("Confirmed with products that are not compatible"), messages)
                    continue
                blocked.append("%s:\n- %s" % (order.name, '\n- '.join(messages)))
            if blocked:
                raise UserError(_(
                    "These orders contain products that are not compatible:\n\n%s\n\n"
                    "Fix the order lines, or ask a Sales Manager to override.",
                    '\n\n'.join(blocked)))
        return super().action_confirm()

    def action_cl_override_compatibility(self):
        if not self.env.user.has_group(_MANAGER_GROUP):
            raise UserError(_("Only Sales Managers can override a compatibility warning."))
        messages_by_order = {order.id: order._cl_compatibility_messages() for order in self}
        # The check is skipped for this confirmation only. The flag is set
        # afterwards: other apps may rewrite the lines while confirming
        # (reward lines, for instance), which resets it.
        res = self.with_context(cl_skip_compatibility=True).action_confirm()
        for order in self:
            order.cl_compatibility_override = True
            order._cl_log_compatibility_note(
                _("Compatibility warning overridden by %s", self.env.user.name),
                messages_by_order[order.id])
        return res
