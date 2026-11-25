# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests import TransactionCase


class ClCourierCostCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.customer = cls.env['res.partner'].create({'name': 'Courier Test Customer'})
        product_model = cls.env['product.product']
        cls.product = product_model.create({
            'name': 'Cup Carton', 'type': 'consu', 'weight': 2.0, 'volume': 0.01, 'list_price': 10.0})
        cls.weightless = product_model.create({'name': 'Gift Voucher', 'type': 'consu', 'weight': 0.0})
        cls.ship_product = product_model.create({'name': 'Courier Delivery', 'type': 'service'})

        variable_model = cls.env['cl.courier.variable']
        cls.var_kg = variable_model.create({
            'name': 'Shipping weight', 'cl_code': 'kg', 'cl_type': 'field', 'cl_source': 'shipping_weight'})
        cls.var_rate = variable_model.create({
            'name': 'Rate per kg', 'cl_code': 'rate', 'cl_type': 'fixed', 'cl_fixed_value': 5.0})
        cls.var_fee = variable_model.create({
            'name': 'Fixed fee', 'cl_code': 'fee', 'cl_type': 'fixed', 'cl_fixed_value': 10.0})

        cls.formula = cls._create_formula('Per kg', 'kg * rate + fee')
        cls.carrier = cls._create_carrier('Test Courier', cls.formula)
        cls.plain_carrier = cls._create_carrier('Own Driver')

        cls.courier_user = cls.env['res.users'].create({
            'name': 'Courier Clerk', 'login': 'cl_courier_clerk',
            'groups_id': [(6, 0, [cls.env.ref('cl_courier_cost.group_cl_courier_user').id])]})

    @classmethod
    def _create_formula(cls, name, expression, validate=True):
        formula = cls.env['cl.courier.formula'].create({'name': name, 'cl_expression': expression})
        if validate:
            formula.action_cl_validate()
        return formula

    @classmethod
    def _create_carrier(cls, name, formula=None):
        return cls.env['delivery.carrier'].create({
            'name': name,
            'delivery_type': 'fixed',
            'fixed_price': 20.0,
            'product_id': cls.ship_product.id,
            'cl_courier_formula_id': formula.id if formula else False,
        })

    def _deliver(self, product=None, qty=3.0, carrier=None):
        """Create and validate an outgoing delivery."""
        product = product or self.product
        stock = self.warehouse.lot_stock_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': stock.id,
            'location_dest_id': self.customer_location.id,
            'partner_id': self.customer.id,
            'carrier_id': (carrier or self.carrier).id,
            'move_ids': [(0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': stock.id,
                'location_dest_id': self.customer_location.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        return picking

    def _log(self, picking):
        return self.env['cl.courier.cost'].search([('cl_picking_id', '=', picking.id)])
