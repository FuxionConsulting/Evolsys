# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class CustomInvoiceReport(models.TransientModel):
    """
    Modelo transitorio para generar el reporte de facturas.
    """
    _name = 'custom.invoice.report'
    _description = 'Reporte de Facturas Personalizado'

    # Campos de Factura
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)
    invoice_date = fields.Date(string='Fecha de Factura', readonly=True)
    invoice_date_due = fields.Date(string='Fecha de Vencimiento', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    amount_total = fields.Monetary(string='Total Factura', currency_field='company_currency_id', readonly=True)
    
    # Campo para la divisa
    company_currency_id = fields.Many2one('res.currency', string='Divisa', readonly=True)

    # 1. CAMBIO: El campo ya NO es calculado. Es un campo simple almacenado.
    amount_credit_notes = fields.Monetary(
        string='Monto Notas de Crédito Conciliadas',
        currency_field='company_currency_id',
        readonly=True,
        # CAMBIO CLAVE: Quitamos 'compute' y ponemos 'store=True' para que sea filtrable.
    )

    # 2. CAMBIO: El campo ya NO es calculado. Es un campo simple almacenado.
    amount_total_after_credit_notes = fields.Monetary(
        string='Monto Neto',
        currency_field='company_currency_id',
        readonly=True,
        # CAMBIO CLAVE: Quitamos 'compute' y ponemos 'store=True' para que sea filtrable.
    )
    
    # FUNCIONES DE CÁLCULO Y GENERACIÓN DE REPORTE

    # Mantenemos la lógica de cálculo, pero la movemos a una función auxiliar.
    def _calculate_cn_amount(self, invoice):
        """
        Calcula el monto total de notas de crédito aplicadas a una factura.
        """
        if not invoice:
            return 0.0

        total_cn_amount = 0.0
        
        # Obtener las líneas de la factura que están pendientes de pago y han sido conciliadas
        reconciled_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.reconcile and line.debit > 0 and line.matched_credit_ids
        )
        
        for line in reconciled_lines:
            for partial in line.matched_credit_ids:
                cn_move = partial.credit_move_id.move_id
                
                # Verificamos que sea una Nota de Crédito ('out_refund') publicada
                if cn_move.move_type == 'out_refund' and cn_move.state == 'posted':
                    # Usamos el campo 'amount' de la conciliación parcial (account.partial.reconcile)
                    # que es el monto exacto de la conciliación.
                    total_cn_amount += partial.amount 
                    
        return total_cn_amount

    # La función @api.depends anterior ya no es necesaria y la eliminamos.
    # Eliminamos _compute_credit_notes_amounts.


    def action_generate_report(self):
        """
        Función que genera los registros transitorios del reporte,
        calculando y almacenando los valores de monto en el proceso.
        """
        # CRÍTICO: Eliminar registros transitorios previos del usuario actual
        self.search([('create_uid', '=', self.env.uid)]).sudo().unlink()

        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted')
        ], order='invoice_date desc')

        report_records = []
        for invoice in invoices:
            
            # PASO CLAVE: Calculamos los montos ANTES de crear el registro
            cn_amount = self._calculate_cn_amount(invoice)
            amount_net = invoice.amount_total - cn_amount
            
            report_records.append({
                'invoice_id': invoice.id,
                'invoice_date': invoice.invoice_date,
                'invoice_date_due': invoice.invoice_date_due,
                'partner_id': invoice.partner_id.id,
                'amount_total': invoice.amount_total,
                'company_currency_id': invoice.currency_id.id,
                
                # NUEVOS VALORES: Insertamos los resultados calculados
                'amount_credit_notes': cn_amount,
                'amount_total_after_credit_notes': amount_net,
            })
            
        # Crear los registros transitorios.
        new_records = self.create(report_records)

        # Retornar una acción de ventana para mostrar la vista de lista con los nuevos registros
        return {
            'name': 'Reporte Personalizado de Facturas',
            'type': 'ir.actions.act_window',
            'res_model': 'custom.invoice.report',
            'view_mode': 'tree',
            'views': [(self.env.ref('l10n_ve_custom_reports.view_custom_report_tree').id, 'tree')], 
            'domain': [('id', 'in', new_records.ids)],
            'target': 'current',
            'flags': {'views_operations': {'form': 'no_open'}},
        }
        
    def action_view_invoice(self):
        # Esta función se mantiene CORRECTA para la navegación.
        self.ensure_one()
        invoice_id = self.invoice_id.id 
        return {
            'name': ('Factura Relacionada'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice_id,
            'view_mode': 'form',
            'target': 'current',
        }