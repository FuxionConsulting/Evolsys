# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta, date

class MoSearchWizard(models.TransientModel):
    _name = 'mo.search.wizard'
    _description = 'Wizard para Búsqueda de ordenes de Fabricacion'

    # **** AQUÍ ES DONDE SE DEFINE EL CAMPO search_date ****
    # Nota: Si no se pone 'required=True', el campo es opcional por defecto.
    search_date = fields.Date(string="Fecha de Búsqueda") 
    
    production_ids = fields.Many2many(
        'mrp.production',
        string="ordenes de Fabricacion Encontradas",
        relation="mo_search_wizard_mrp_production_rel",
        column1="mo_search_wizard_id",
        column2="mrp_production_id",
        readonly=True,
    )

    has_productions = fields.Boolean(
        string="Se encontraron OFs?",
        compute='_compute_has_productions',
        store=False,
    )

    @api.depends('production_ids')
    def _compute_has_productions(self):
        for record in self:
            record.has_productions = bool(record.production_ids)

    def action_search_mos(self):
        domain = [
            ('state', '=', 'draft')
        ]
        
        print(f"\n--- DEBUG Búsqueda solo por Estado 'draft' ---")
        print(f"DEBUG: Dominio de búsqueda: {domain}")

        found_mos = self.env['mrp.production'].search(domain)

        print(f"DEBUG: IDs de ordenes de Fabricacion encontradas: {found_mos.ids}")
        print(f"DEBUG: Nombres de ordenes de Fabricacion encontradas: {[mo.name for mo in found_mos]}")
        print(f"DEBUG: Cantidad de OFs encontradas: {len(found_mos)}")
        print(f"--- FIN DEBUG Búsqueda solo por Estado 'draft' ---\n")

        self.production_ids = [(6, 0, found_mos.ids)]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mo.search.wizard',
            'name': 'Búsqueda de ordenes de Fabricacion',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_open_availability_check_wizard(self):
        return {
            'name': 'Verificar Disponibilidad de Materiales',
            'type': 'ir.actions.act_window',
            'res_model': 'mo.availability.check.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_ids': [(6, 0, self.production_ids.ids)],
            },
        }

    def action_open_validate_wizard(self):
        return {
            'name': 'Validar ordenes de Fabricacion',
            'type': 'ir.actions.act_window',
            'res_model': 'mo.validate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_ids': [(6, 0, self.production_ids.ids)],
            },
        }