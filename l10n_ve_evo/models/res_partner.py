# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'

    rif_type = fields.Selection([
        ('V', 'Persona Natural (V)'),
        ('J', 'Persona Jurídica (J)'),
        ('G', 'Gubernamental (G)'),
        ('E', 'Extranjero (E)'),
        ('P', 'Pasaporte (P)'),
    ], string='Tipo de RIF', required=True, default='V')

    city_id = fields.Many2one('res.city', string='Ciudad')
    municipality_id = fields.Many2one('res.country.municipality', string='Municipio')
    parish_id = fields.Many2one('res.country.parish', string='Parroquia')

    @api.onchange('state_id')
    def _onchange_state_id_ve(self):
        if self.state_id:
            return {'domain': {'municipality_id': [('state_id', '=', self.state_id.id)]}}
        return {'domain': {'municipality_id': []}}

    @api.onchange('municipality_id')
    def _onchange_municipality_id_ve(self):
        if self.municipality_id:
            self.state_id = self.municipality_id.state_id
            return {'domain': {'parish_id': [('municipality_id', '=', self.municipality_id.id)]}}
        return {'domain': {'parish_id': []}}

    @api.constrains('vat', 'rif_type', 'company_type')
    def _check_vat_ve(self):
        for rec in self:
            if rec.country_id and rec.country_id.code == 'VE' and rec.vat:
                # Limpiar caracteres especiales si los hay
                vat_clean = re.sub(r'[^a-zA-Z0-9]', '', rec.vat).upper()
                if rec.rif_type and not vat_clean.startswith(rec.rif_type):
                    raise ValidationError(_("El RIF/Documento debe comenzar con la letra seleccionada en 'Tipo de RIF'."))