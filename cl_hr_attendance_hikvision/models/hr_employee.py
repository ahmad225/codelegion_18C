# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    cl_hik_user_id = fields.Char(
        string='Hikvision User ID', groups='hr.group_hr_user', copy=False, index='btree_not_null',
        help='Employee No. of this person on the Hikvision devices of the company (exactly as on the '
             'device, leading zeros included). Punches with this number are booked on this employee; '
             'punches received before the number was entered are processed as soon as it is saved.')

    _sql_constraints = [
        ('cl_hik_user_id_company_uniq', 'unique (cl_hik_user_id, company_id)',
         'This Hikvision User ID is already used by another employee of the same company.'),
    ]

    @api.model
    def _cl_hik_clean_vals(self, vals):
        if 'cl_hik_user_id' in vals:
            vals['cl_hik_user_id'] = (vals['cl_hik_user_id'] or '').strip() or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._cl_hik_clean_vals(dict(vals)) for vals in vals_list]
        employees = super().create(vals_list)
        if any(vals.get('cl_hik_user_id') for vals in vals_list):
            employees.sudo()._cl_hik_map_punches()
        return employees

    def write(self, vals):
        vals = self._cl_hik_clean_vals(dict(vals))
        result = super().write(vals)
        if vals.get('cl_hik_user_id') or ('company_id' in vals and 'cl_hik_user_id' not in vals):
            self.sudo()._cl_hik_map_punches()
        return result

    def _cl_hik_map_punches(self):
        """Book the punches received before this employee had a Hikvision User ID, and pair them."""
        Punch = self.env['cl.hik.punch'].sudo()
        waiting = Punch.browse()
        for employee in self.filtered('cl_hik_user_id'):
            waiting |= Punch.search([
                ('state', '=', 'unmapped'),
                ('hik_user_id', '=', employee.cl_hik_user_id),
                ('company_id', '=', employee.company_id.id),
            ])
        mapped = waiting._cl_map_employees()
        if mapped:
            Punch._cl_process_pending(employees=mapped.employee_id)
