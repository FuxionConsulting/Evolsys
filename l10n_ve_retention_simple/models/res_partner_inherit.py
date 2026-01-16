# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResPartnerInherit(models.Model):
    _inherit = "res.partner"

    retention_iva_rate = fields.Selection(
        selection=[('75', '75%'), ('100', '100%')],
        string="Retención IVA",
        help="Porcentaje de retención IVA aplicable cuando la posición fiscal es Especial",
        copy=True,
    )

    @api.onchange('property_account_position_id')
    def _onchange_property_account_position_id_retention(self):
        for rec in self:
            pos = rec.property_account_position_id
            if not pos or (pos.name or '').strip().lower() != 'especial':
                rec.retention_iva_rate = False
            else:
                # Si quieres sugerir un valor por defecto al activar 'Especial', descomenta:
                # if not rec.retention_iva_rate:
                #     rec.retention_iva_rate = '75'
                pass

    @api.constrains('retention_iva_rate', 'property_account_position_id')
    def _check_retention_rate_position_consistency(self):
        for rec in self:
            if rec.retention_iva_rate:
                pos = rec.property_account_position_id
                if not pos or (pos.name or '').strip().lower() != 'especial':
                    raise ValidationError(
                        _("El campo Retención IVA solo puede establecerse si la posición fiscal del partner es 'Especial'.")
                    )
