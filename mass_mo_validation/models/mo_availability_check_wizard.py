# -*- coding: utf-8 -*-

from odoo import models, fields, api

class MoAvailabilityCheckWizard(models.TransientModel):
    _name = 'mo.availability.check.wizard'
    _description = 'Wizard para Verificar Disponibilidad de Materiales'

    production_ids = fields.Many2many(
        'mrp.production',
        string="ordenes de Fabricacion",
        readonly=True,
    )
    availability_info_ids = fields.One2many(
        'mo.availability.info',
        'wizard_id', 
        string="Informacion de Disponibilidad",
        readonly=True,
    )

    @api.model
    def default_get(self, fields):
        res = super(MoAvailabilityCheckWizard, self).default_get(fields)
        if 'production_ids' in fields and self.env.context.get('default_production_ids'):
            res['production_ids'] = self.env.context['default_production_ids']
        return res

    def action_check_availability(self):
        self.write({'availability_info_ids': [(5, 0, 0)]}) 

        new_info_records = [] 
        
        for mo in self.production_ids:
            is_available = True
            message = "Todos los componentes están disponibles."
            missing_details = "" 

            if mo.bom_id:
                for line in mo.bom_id.bom_line_ids:
                    product = line.product_id
                    # Asegurarse de que product_qty sea un número válido y no cero para evitar divisiones por cero o cálculos erroneos
                    if line.product_qty > 0 and mo.product_qty > 0:
                        required_qty = line.product_qty * mo.product_qty 
                    else:
                        required_qty = 0 # O maneja este caso según tu logica de negocio

                    available_qty = product.qty_available 
                    
                    if available_qty < required_qty:
                        is_available = False
                        missing_details += f"- {product.name} (faltan {required_qty - available_qty} {product.uom_id.name})\n"
            else:
                is_available = False
                message = "La Orden de Fabricacion no tiene una Lista de Materiales (BoM) definida."

            if not is_available:
                message = "Faltan componentes para esta Orden de Fabricacion."

            info_vals = {
                'production_id': mo.id,
                'has_all_materials': is_available,
                'message': message,
                'missing_materials_details': missing_details,
                'wizard_id': self.id, 
            }
            new_info_records.append(self.env['mo.availability.info'].create(info_vals).id)
        
        self.write({'availability_info_ids': [(6, 0, new_info_records)]}) 

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mo.availability.check.wizard',
            'name': 'Verificar Disponibilidad de Materiales',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_proceed_to_validation(self):
        # **** MODIFICACIoN CLAVE AQUÍ: Filtrar OFs disponibles ****
        available_mo_ids = self.availability_info_ids.filtered(lambda x: x.has_all_materials).mapped('production_id').ids

        if not available_mo_ids:
            raise UserError("No hay ordenes de Fabricacion con disponibilidad completa para validar.")

        return {
            'name': 'Validar ordenes de Fabricacion',
            'type': 'ir.actions.act_window',
            'res_model': 'mo.validate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_ids': [(6, 0, available_mo_ids)], # Solo pasa las OFs disponibles
            },
        }