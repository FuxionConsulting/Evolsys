from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Modelo para Retenciones"

    # El campo 'number' ahora será computado y asignará el valor de la secuencia adecuada.
    number = fields.Char(string="Número de Retención", required=True, copy=False, readonly=True, default="New")

    # Campo 'type_retention' es esencial para seleccionar la secuencia correcta
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        string="Tipo de Retención",
        required=True,
    )

    name = fields.Char(string="Descripción", compute='_compute_name', store=True)
    date = fields.Date(string="Fecha", default=fields.Date.today())
    partner_id = fields.Many2one('res.partner', string="Compañía", required=True)
    foreign_currency_id = fields.Many2one('res.currency', string="Moneda Extranjera")

    @api.depends('number', 'type_retention', 'partner_id')
    def _compute_name(self):
        for rec in self:
            name_parts = []
            if rec.type_retention:
                name_parts.append(rec.type_retention.upper())
            if rec.number and rec.number != 'New': # Excluye 'New' si aún no se ha asignado un número
                name_parts.append(rec.number)
            if rec.partner_id:
                name_parts.append(rec.partner_id.name)
            rec.name = ' / '.join(name_parts) if name_parts else 'Nueva Retención'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('number', 'New') == 'New':
                # Mapea el tipo de retención a su código de secuencia correspondiente
                sequence_code_map = {
                    'iva': 'retention.iva.control.number',
                    'islr': 'retention.islr.control.number',
                    'municipal': 'retention.municipal.control.number',
                }
                retention_type = vals.get('type_retention')
                sequence_code = sequence_code_map.get(retention_type)

                if sequence_code:
                    vals['number'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
                else:
                    raise ValidationError(_("No se ha configurado una secuencia para el tipo de retención '%s'.") % retention_type)
        return super().create(vals_list)

