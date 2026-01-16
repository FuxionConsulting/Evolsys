# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class MailTrackingValue(models.Model):
    _inherit = 'mail.tracking.value'

    # --- TUS CAMPOS COMPUTADOS EXISTENTES (CORREGIDOS) ---
    # Nota: Usar 'model' y 'author_id' como nombres de campo aquí
    # puede ser confuso si el modelo base de Odoo tiene campos con el mismo nombre.
    # Los renombramos internamente o nos aseguramos de que no haya conflicto.
    # Pero si tu intencion es sobreescribirlos o extenderlos, así se haría.
    # Basado en la depuracion, es más probable que estos sean campos nuevos para la vista.

    # Tu campo 'model' corregido (es un campo computado)
    computed_model_name = fields.Char(
        string="Modelo",
        compute="_compute_model_name",
        store=True,
        readonly=True,
    )

    # Tu campo 'author_id' corregido (es un campo computado)
    computed_author_id = fields.Many2one(
        "res.partner",
        string="Autor",
        compute="_compute_author_id",
        store=True,
        readonly=True,
    )

    @api.depends("mail_message_id.model") # DEPENDENCIA CORREGIDA
    def _compute_model_name(self):
        for record in self:
            record.computed_model_name = record.mail_message_id.model

    @api.depends("mail_message_id.author_id") # DEPENDENCIA CORREGIDA
    def _compute_author_id(self):
        for record in self:
            record.computed_author_id = record.mail_message_id.author_id

    # --- CAMPOS RELATED PARA MAYOR ROBUSTEZ Y CLARIDAD EN LA VISTA ---
    # Estos campos related son una forma más directa y a menudo preferida
    # cuando solo necesitas acceder a un campo de un Many2one directamente.
    # Son más eficientes que los @api.depends si no hay logica compleja.

    audit_date = fields.Datetime(
        string="Fecha de Cambio",
        related='mail_message_id.date',
        store=True,
        readonly=True,
    )
    
    # field_id es el Many2one a ir.model.fields
    audit_field_description = fields.Char(
        string="Campo Modificado",
        related='field_id.field_description', # Usamos field_id.field_description
        readonly=True,
    )
    audit_field_name = fields.Char( # Por si prefieres el nombre técnico del campo
        string="Nombre Técnico del Campo",
        related='field_id.name',
        store=True,
        readonly=True,
    )

    # Nota: Los campos new_value_char, old_value_char, etc. (los que confirmaste que existen)
    # no necesitan ser definidos aquí si ya están en el modelo base mail.tracking.value.
    # Solo los incluyo en el XML para la vista.