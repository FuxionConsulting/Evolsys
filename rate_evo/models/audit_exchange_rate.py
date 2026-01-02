from odoo import models, fields, api

class AuditExchangeRateChange(models.Model):
    _name = "rate_evo.audit.exchange.rate"
    _description = "Auditoría de cambios en tasas de cambio"
    _order = "timestamp desc"

    currency_id = fields.Many2one("res.currency", string="Moneda", required=True)
    old_rate = fields.Float(string="Tasa anterior", digits=(16, 6))
    new_rate = fields.Float(string="Tasa nueva", digits=(16, 6), required=True)
    user_id = fields.Many2one("res.users", string="Usuario", required=True, default=lambda self: self.env.user)
    timestamp = fields.Datetime(string="Fecha de cambio", default=lambda self: fields.Datetime.now(), required=True)
    reason = fields.Text(string="Motivo", required=True)
