# -*- coding: utf-8 -*-
# Copyright (C) Code Legion (<https://thecodelegion.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # Arguments are passed through untouched: other modules (Enterprise Shop Floor)
    # extend the signatures of these methods.

    def button_start(self, *args, **kwargs):
        self.production_id._cl_check_approved()
        return super().button_start(*args, **kwargs)

    def button_finish(self, *args, **kwargs):
        self.production_id._cl_check_approved()
        return super().button_finish(*args, **kwargs)

    def button_done(self, *args, **kwargs):
        self.production_id._cl_check_approved()
        return super().button_done(*args, **kwargs)
