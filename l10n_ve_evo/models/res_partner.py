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
    ], string='Tipo de RIF', required=True, default='V')

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

            # Buscar por nombre, no por XMLID
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
        return super().write(vals)

    def create(self, vals):
        vals = self._normalize_vat(vals)
        return super().create(vals)

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

                if rec.property_account_position_id.id != ordinario.id:
                    raise ValidationError(_("Las personas naturales deben tener la posición fiscal 'VE - Domestico (Ordinario)'."))

    @api.constrains('vat', 'company_type')
    def _check_vat_format(self):
        for rec in self:
            if not rec.vat:
                raise ValidationError(_("Debe ingresar la identificación fiscal."))

            vat = rec.vat.upper()

            if rec.company_type == 'person':
                # Persona: V + 8 dígitos
                if not re.match(r'^V\d{8}$', vat):
                    raise ValidationError(_("Para personas naturales el formato debe ser: V######## (V + 8 dígitos)."))
            else:
                # Empresa: LETRA + 9 dígitos
                if not re.match(r'^[VEJG]\d{9}$', vat):
                    raise ValidationError(_("Para empresas el formato debe ser: LETRA + 9 dígitos (ej: J123456789)."))
