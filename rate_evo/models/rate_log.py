from odoo import models, fields

class RateEvoLog(models.Model):
    _name = "rate_evo.rate.log"
    _description = "Log de importaciones de tasas de cambio"
    _order = "timestamp desc"

    rate_id = fields.Many2one(
        "res.currency.rate",
        string="Tasa registrada",
        required=True,
        ondelete="cascade",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )

    # El proveedor se obtiene del campo currency_provider de la compañía
    currency_provider = fields.Selection(
        related="company_id.currency_provider",
        string="Proveedor",
        readonly=True,
        store=True,
    )

    action = fields.Selection(
        [
            ("import", "Importación automática"),
            ("manual_update", "Actualización manual"),
            ("error", "Error"),
        ],
        string="Acción",
        required=True,
    )

    status = fields.Selection(
        [
            ("success", "Éxito"),
            ("failed", "Fallido"),
        ],
        string="Estado",
        required=True,
    )

    message = fields.Text(string="Mensaje de log")

    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
    )

    timestamp = fields.Datetime(
        string="Fecha",
        default=lambda self: fields.Datetime.now(),
        required=True,
    )
