from odoo import models, fields

class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    def write(self, vals):
        for rec in self:
            old_rate = rec.rate
            res = super().write(vals)
            if "rate" in vals and vals["rate"] != old_rate:
                self.env["rate_evo.audit.exchange.rate"].create({
                    "currency_id": rec.currency_id.id,
                    "old_rate": old_rate,
                    "new_rate": vals["rate"],
                    "reason": self.env.context.get("rate_update_reason", "Actualización automática"),
                    "user_id": self.env.user.id,
                })
        return res
