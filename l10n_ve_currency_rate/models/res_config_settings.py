from odoo import models, fields, api
import datetime
from dateutil.relativedelta import relativedelta


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_l10n_ve_currency_rate = fields.Boolean(string="Automatic Currency Rates for VE")
    currency_interval_period = fields.Selection(
        related="company_id.currency_interval_period", readonly=False
    )
    curr_next_execution_date = fields.Date(
        related="company_id.curr_next_execution_date", readonly=False
    )

    @api.onchange("currency_interval_period")
    def onchange_currency_interval_period(self):
        if self.company_id.curr_next_execution_date:
            return

        interval_mapping = {
            "daily": relativedelta(days=+1),
            "weekly": relativedelta(weeks=+1),
            "monthly": relativedelta(months=+1),
        }

        next_update = interval_mapping.get(self.currency_interval_period)
        if next_update:
            self.curr_next_execution_date = datetime.date.today() + next_update
        else:
            self.curr_next_execution_date = False

    def update_currency_rate(self):
        self.ensure_one()
        self.company_id.update_currency_rates()
