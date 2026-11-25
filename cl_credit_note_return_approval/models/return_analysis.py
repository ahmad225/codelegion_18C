# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields, models, tools


class ReturnAnalysis(models.Model):
    """Goods actually received back through approved return requests.

    One row per done stock move of a return transfer. The quantity is what
    was received, in the product's unit of measure; the amount values it at
    the unit price the credit note gives for that product, in company
    currency."""
    _name = 'cl.return.analysis'
    _description = 'Returned Goods Analysis'
    _auto = False
    _rec_name = 'request_id'
    _order = 'date desc, id desc'

    date = fields.Date(string='Received On', readonly=True)
    request_id = fields.Many2one('cl.return.request', string='Return Request', readonly=True)
    credit_note_id = fields.Many2one('account.move', string='Credit Note', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    reason_id = fields.Many2one('cl.credit.note.reason', string='Reason', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    quantity = fields.Float(
        string='Quantity Received', digits='Product Unit of Measure', readonly=True)
    amount = fields.Monetary(
        string='Value Credited', currency_field='currency_id', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # uom_uom.factor: quantity in the reference unit = quantity / factor,
        # so "x / from.factor * to.factor" converts x between two units.
        self.env.cr.execute("""
            CREATE VIEW cl_return_analysis AS (
                WITH credited AS (
                    -- per credit note and product: value of one product unit
                    SELECT aml.move_id,
                           aml.product_id,
                           ABS(SUM(aml.balance)) / NULLIF(SUM(
                               aml.quantity / NULLIF(lu.factor, 0) * pu.factor
                           ), 0) AS unit_value
                      FROM account_move_line aml
                      JOIN product_product pp ON pp.id = aml.product_id
                      JOIN product_template pt ON pt.id = pp.product_tmpl_id
                      JOIN uom_uom pu ON pu.id = pt.uom_id
                      JOIN uom_uom lu ON lu.id = COALESCE(aml.product_uom_id, pt.uom_id)
                     WHERE aml.display_type = 'product'
                  GROUP BY aml.move_id, aml.product_id
                )
                SELECT sm.id                    AS id,
                       sp.date_done::date       AS date,
                       rr.id                    AS request_id,
                       rr.credit_note_id        AS credit_note_id,
                       rr.partner_id            AS partner_id,
                       rr.reason_id             AS reason_id,
                       cn.invoice_user_id       AS user_id,
                       sm.product_id            AS product_id,
                       pt.categ_id              AS product_categ_id,
                       rr.company_id            AS company_id,
                       rc.currency_id           AS currency_id,
                       sm.quantity / NULLIF(mu.factor, 0) * pu.factor
                                                AS quantity,
                       sm.quantity / NULLIF(mu.factor, 0) * pu.factor
                           * COALESCE(credited.unit_value, 0)
                                                AS amount
                  FROM stock_move sm
                  JOIN stock_picking sp ON sp.id = sm.picking_id
                  JOIN cl_return_request rr ON rr.id = sp.cl_return_request_id
                  JOIN account_move cn ON cn.id = rr.credit_note_id
                  JOIN res_company rc ON rc.id = rr.company_id
                  JOIN product_product pp ON pp.id = sm.product_id
                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                  JOIN uom_uom pu ON pu.id = pt.uom_id
                  JOIN uom_uom mu ON mu.id = sm.product_uom
             LEFT JOIN credited
                    ON credited.move_id = rr.credit_note_id
                   AND credited.product_id = sm.product_id
                 WHERE sm.state = 'done'
            )
        """)
