# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountAccount(models.Model):
    _inherit = 'account.account'

    # Campo calculado para simplificar el acceso al grupo interno del tipo de cuenta para los reportes.
    internal_group_report = fields.Char(
        string="Internal Group for Reports",
        compute='_compute_internal_group_report',
        store=False, # No es necesario almacenar, se calcula al vuelo.
        help="Technical field to get the internal group of the account type for reporting."
    )

    @api.depends('user_type_id.internal_group')
    def _compute_internal_group_report(self):
        for account in self:
            account.internal_group_report = account.user_type_id.internal_group