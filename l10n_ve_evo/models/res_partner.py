# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    rif_type = fields.Selection([
        ('V', 'Persona Natural (V)'),
        ('J', 'Persona Jurídica (J)'),
        ('G', 'Gubernamental (G)'),
        ('E', 'Extranjero (E)'),
    ], string='Tipo de RIF', required=True, default='V')

    # Campos geográficos
    city_id = fields.Many2one('res.city', string='Ciudad')
    municipality_id = fields.Many2one('res.country.municipality', string='Municipio')
    parish_id = fields.Many2one('res.country.parish', string='Parroquia')

    # ---------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------
    @api.onchange('company_type')
    def _onchange_company_type(self):
        if self.company_type == 'person':
            self.rif_type = 'V'
            # Buscar por nombre la posición fiscal
            ordinario = self.env['account.fiscal.position'].search([
                ('name', '=', 'VE - Domestico (Ordinario)')
            ], limit=1)
            if ordinario:
                self.property_account_position_id = ordinario
        else:
            if not self.rif_type:
                self.rif_type = 'J'

    @api.onchange('vat')
    def _onchange_vat_upper(self):
        if self.vat:
            self.vat = re.sub(r'[^a-zA-Z0-9]', '', self.vat).upper()

    @api.onchange('state_id')
    def _onchange_state_id_ve(self):
        """Si cambia el estado, limpiar municipio/ciudad/parroquia incompatibles."""
        if self.state_id:
            if self.municipality_id and self.municipality_id.state_id != self.state_id:
                self.municipality_id = False
                self.parish_id = False
            if self.city_id and self.city_id.state_id != self.state_id:
                self.city_id = False

    @api.onchange('municipality_id')
    def _onchange_municipality_id(self):
        """Si cambia el municipio, limpiar parroquia incompatible."""
        if self.municipality_id:
            if self.parish_id and self.parish_id.municipality_id != self.municipality_id:
                self.parish_id = False

    # ---------------------------------------------------------
    # NORMALIZACIÓN BACKEND
    # ---------------------------------------------------------
    def _normalize_vat(self, vals):
        vat = vals.get('vat')
        if vat:
            vals['vat'] = re.sub(r'[^a-zA-Z0-9]', '', vat).upper()
        return vals

    def write(self, vals):
        vals = self._normalize_vat(vals)
        return super(ResPartner, self).write(vals)

    def create(self, vals):
        vals = self._normalize_vat(vals)
        return super(ResPartner, self).create(vals)

    # ---------------------------------------------------------
    # VALIDACIONES
    # ---------------------------------------------------------
    @api.constrains('company_type', 'rif_type')
    def _check_rif_type_for_person(self):
        for rec in self:
            if rec.company_type == 'person' and rec.rif_type != 'V':
                raise ValidationError(_("Las personas naturales deben tener rif_type = 'V'."))

    @api.constrains('company_type', 'property_account_position_id')
    def _check_fiscal_position_for_person(self):
        for rec in self:
            if rec.company_type == 'person':
                ordinario = rec.env['account.fiscal.position'].search([
                    ('name', '=', 'VE - Domestico (Ordinario)')
                ], limit=1)
                if not ordinario:
                    raise ValidationError(_("No se encontró la posición fiscal 'VE - Domestico (Ordinario)'."))

                if rec.property_account_position_id and rec.property_account_position_id.id != ordinario.id:
                    raise ValidationError(_("Las personas naturales deben tener la posición fiscal 'VE - Domestico (Ordinario)'."))

    @api.constrains('vat', 'company_type')
    def _check_vat_format(self):
        for rec in self:
            if not rec.vat:
                raise ValidationError(_("Debe ingresar la identificación fiscal."))

            vat = rec.vat.upper()

            if rec.company_type == 'person':
                # Persona: V + 7 a 8 dígitos
                if not re.match(r'^V\d{7,8}$', vat):
                    raise ValidationError(_("Para personas naturales el formato debe ser: V seguido de 7 u 8 dígitos (ej: V1234567 o V12345678)."))
            else:
                # Empresa: LETRA + 9 dígitos (V, E, J, G)
                if not re.match(r'^[VEJG]\d{9}$', vat):
                    raise ValidationError(_("Para empresas el formato debe ser: LETRA + 9 dígitos (ej: J123456789)."))
