# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResCountryMunicipality(models.Model):
    _name = 'res.country.municipality'
    _description = 'Municipio de Venezuela'
    _order = 'name'

    name = fields.Char(string='Municipio', required=True, translate=True)
    code = fields.Char(string='Código', help='Código del Municipio (ej. uso fiscal)')
    state_id = fields.Many2one('res.country.state', string='Estado', required=True, index=True)

class ResCountryParish(models.Model):
    _name = 'res.country.parish'
    _description = 'Parroquia de Venezuela'
    _order = 'name'

    name = fields.Char(string='Parroquia', required=True, translate=True)
    code = fields.Char(string='Código', help='Código de la Parroquia')
    municipality_id = fields.Many2one('res.country.municipality', string='Municipio', required=True, index=True)
    # Campo relacionado para facilitar búsquedas y dominios
    state_id = fields.Many2one('res.country.state', related='municipality_id.state_id', string='Estado', store=True, readonly=True)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Añadimos los campos específicos de la localización VE
    municipality_id = fields.Many2one('res.country.municipality', string='Municipio')
    parish_id = fields.Many2one('res.country.parish', string='Parroquia')

    @api.onchange('state_id')
    def _onchange_state_id_ve(self):
        """Limpiar municipio y parroquia si cambia el estado"""
        if self.state_id and self.municipality_id.state_id != self.state_id:
            self.municipality_id = False
            self.parish_id = False

    @api.onchange('municipality_id')
    def _onchange_municipality_id(self):
        """Limpiar parroquia si cambia el municipio"""
        if self.municipality_id and self.parish_id.municipality_id != self.municipality_id:
            self.parish_id = False