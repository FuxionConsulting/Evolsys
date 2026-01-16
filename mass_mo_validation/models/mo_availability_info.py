# -*- coding: utf-8 -*-

from odoo import models, fields

class MoAvailabilityInfo(models.TransientModel): # O models.Model, dependiendo de si quieres que los registros persistan
    _name = 'mo.availability.info'
    _description = 'Informacion de Disponibilidad de Materiales por OF'

    wizard_id = fields.Many2one(
        'mo.availability.check.wizard', 
        string="Wizard de Verificacion", 
        ondelete='cascade', # Esto eliminará la informacion cuando el wizard se cierre
    )
    production_id = fields.Many2one(
        'mrp.production',
        string="Orden de Fabricacion",
        readonly=True,
    )
    has_all_materials = fields.Boolean(
        string="Materiales Disponibles",
        readonly=True,
    )
    message = fields.Char(
        string="Estado General",
        readonly=True,
    )
    missing_materials_details = fields.Text(
        string="Detalles de Materiales Faltantes",
        readonly=True,
    )
    # Puedes anadir un campo para "missing_components_ids" si quieres una lista de los componentes faltantes
    # missing_components_ids = fields.Many2many('product.product', string="Componentes Faltantes", readonly=True)