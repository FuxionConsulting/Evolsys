from odoo import models, fields, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    exchange_rate = fields.Float(
        string="Tasa de cambio",
        digits=(16, 6),
        compute="_compute_exchange_rate",
        readonly=True,  # Solo visualización
    )

    @api.depends("currency_id", "payment_date")
    def _compute_exchange_rate(self):
        for wizard in self:
            if wizard.currency_id and wizard.currency_id != wizard.company_id.currency_id:
                wizard.exchange_rate = wizard.currency_id._get_conversion_rate(
                    wizard.currency_id,
                    wizard.company_id.currency_id,
                    wizard.company_id,
                    wizard.payment_date or fields.Date.today(),
                )
            else:
                wizard.exchange_rate = 1.0
