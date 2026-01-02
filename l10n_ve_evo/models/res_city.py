# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCity(models.Model):
    _name = 'res.city'
    _description = 'City'
    _order = 'name'

    name = fields.Char(string='City', required=True, index=True)
    state_id = fields.Many2one('res.country.state', string='State', required=True, ondelete='cascade')
    municipality_id = fields.Many2one('res.country.municipality', string='Municipio', required=True, index=True)
    zip = fields.Char(string='Postal Code', help='Primary postal code for the city')
    code = fields.Char(string='Code', help='Optional city code')
