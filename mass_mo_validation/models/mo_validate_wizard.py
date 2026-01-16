# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError

class MoValidateWizard(models.TransientModel):
    _name = 'mo.validate.wizard'
    _description = 'Wizard para Validar ordenes de Fabricacion'

    # ... (tus campos production_ids, selected_production_ids, company_id) ...
    production_ids = fields.Many2many(
        'mrp.production',
        string="ordenes de Fabricacion Recibidas",
        readonly=True,
    )
    
    selected_production_ids = fields.Many2many(
        'mrp.production',
        string="ordenes de Fabricacion a Validar",
        relation="mo_validate_wizard_production_rel", 
        column1="validate_wizard_id",                  
        column2="mrp_production_id",                   
        help="Selecciona las ordenes de Fabricacion que deseas validar."
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Companía', 
        required=True, 
        default=lambda self: self.env.company
    )

    @api.model
    def default_get(self, fields):
        res = super(MoValidateWizard, self).default_get(fields)
        if 'production_ids' in fields and self.env.context.get('default_production_ids'):
            received_mos = self.env.context['default_production_ids']
            res['production_ids'] = received_mos
            res['selected_production_ids'] = received_mos 
        return res

    def action_validate_mos(self):
        print("DEBUG: action_validate_mos ha sido llamado.") # AnADE ESTO
        if not self.selected_production_ids:
            print("DEBUG: No hay ordenes de Fabricacion seleccionadas. Lanzando UserError.") # AnADE ESTO
            raise UserError("No has seleccionado ninguna Orden de Fabricacion para validar.")

        for mo in self.selected_production_ids:
            print(f"DEBUG: Procesando OF: {mo.name}, Estado actual: {mo.state}") # AnADE ESTO
            try:
                if mo.state == 'done':
                    print(f"DEBUG: La OF {mo.name} ya está validada. Saltando.")
                    continue

                if mo.state in ['draft', 'confirmed', 'ready']: 
                    if mo.state == 'draft':
                        mo.action_confirm() 
                        print(f"DEBUG: OF {mo.name} confirmada.")
                    
                    mo.action_assign() 
                    print(f"DEBUG: OF {mo.name} - Intento de asignacion de componentes. Estado de reserva: {mo.reservation_state}")
                    
                    if mo.reservation_state != 'assigned':
                         print(f"DEBUG: OF {mo.name} - Componentes NO completamente disponibles. Lanzando UserError.")
                         raise UserError(f"Los componentes para la OF {mo.name} no están completamente disponibles después de intentar reservarlos. Asegúrate de tener stock antes de validar.")
                    
                    # Estos métodos pueden variar según la version y modulos adicionales
                    # Si tu Odoo 17 no los tiene, el flujo action_confirm() -> action_assign() -> button_mark_done() suele ser suficiente.
                    # Por ahora, vamos a mantenerlos y ver si dan error.
                    # mo.button_mark_as_todo() 
                    # mo.button_start_production() 

                    mo.button_mark_done() 
                    print(f"DEBUG: OF {mo.name} marcada como Hecha (Validada).")
                    self.env.cr.commit() 
                else:
                    print(f"DEBUG: La OF {mo.name} no está en un estado válido para ser validada (estado actual: {mo.state}).")
            except Exception as e:
                print(f"DEBUG: EXCEPCIoN al validar la OF {mo.name}: {e}")
                # Capturamos la excepcion y la relanzamos como UserError para que se muestre en la interfaz.
                raise UserError(f"Error al validar la OF {mo.name}: {e}\nContacta a tu administrador.")

        print("DEBUG: Todas las OFs seleccionadas procesadas. Recargando wizard.") # AnADE ESTO
        # Este return debería recargar el wizard. Si el wizard queda en blanco o se cierra,
        # significa que la operacion fue exitosa desde el punto de vista del wizard,
        # pero las OFs validadas deberían desaparecer de la lista.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mo.validate.wizard',
            'name': 'Validar ordenes de Fabricacion',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }