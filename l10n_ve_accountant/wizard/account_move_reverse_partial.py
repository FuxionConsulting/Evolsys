from odoo import fields, models, _
from odoo.exceptions import UserError

class AccountMoveReversePartial(models.TransientModel):
    _name = 'account.move.reverse.partial'
    _description = 'Asistente para Nota de Crédito Parcial/Reversión'

    move_id = fields.Many2one('account.move', required=True, string='Factura')

    reverse_type = fields.Selection(
        [
            ('full', 'Reversión Total (Nota de Crédito por el monto total)'),
            ('partial', 'Nota de Crédito Parcial (Abrir borrador)'),
        ],
        string='Tipo de Nota de Crédito',
        default='full',
        required=True,
    )

    def action_reverse(self):
        self.ensure_one()

        if self.reverse_type == 'full':
            # Usar el flujo estándar si existe
            if hasattr(self.move_id, 'button_draft_and_reverse'):
                return self.move_id.button_draft_and_reverse()
            if hasattr(self.move_id, 'button_reverse'):
                return self.move_id.button_reverse()
            raise UserError(_('No se encontró el método de reversión total en account.move.'))

        if self.reverse_type == 'partial':
            # Intentar construir los valores de reversión de forma segura
            reverse_method = getattr(self.move_id, '_reverse_move_vals', None)
            if not reverse_method:
                raise UserError(_('La funcionalidad de reversión no está disponible en este sistema.'))

            # Intentar con distintos nombres de parámetro por compatibilidad
            refund_vals = None
            try:
                refund_vals = reverse_method(cancel=False, keep_linc=True)
            except TypeError:
                try:
                    refund_vals = reverse_method(cancel=False, keep_lines=True)
                except TypeError:
                    try:
                        refund_vals = reverse_method(cancel=False, keep_invoice_lines=True)
                    except TypeError:
                        # Llamada sin parámetros si ninguna firma coincide
                        refund_vals = reverse_method()

            if not refund_vals:
                raise UserError(_('No se pudieron obtener los valores para la nota de crédito parcial.'))

            new_move = self.env['account.move'].with_context(
                skip_invoice_line_auto_update=True
            ).create(refund_vals)

            return {
                'name': _('Nota de Crédito Borrador Parcial'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': new_move.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'default_move_type': new_move.move_type},
            }

        return {'type': 'ir.actions.act_window_close'}
