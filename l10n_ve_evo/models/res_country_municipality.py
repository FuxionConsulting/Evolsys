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
