from odoo import models, fields, api
import requests
from lxml import html
import datetime as dt
from datetime import datetime
from dateutil.relativedelta import relativedelta


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_interval_period = fields.Selection(
        [
            ("manually", "Manually"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        default="manually",
        string="Interval Period",
    )
    curr_next_execution_date = fields.Date(string="Next Execution Date")

    def update_currency_rates(self):
        currencies_name = {
            'USD': 'dolar',
            'EUR': 'euro',
            'CNY': 'yuan',
            'RUB': 'rublo',
            'TRY': 'lira',
        }
        currency_code=''
        inverse = False
        user = self.env.ref('base.user_admin')
        if user.company_id.currency_id.name not in ('VEF', 'VED', 'VES', 'VEB'):
            inverse = True
            currency_code=user.company_id.currency_id.name

        domain = [('name', 'in', list(currencies_name.keys()))]
        if inverse:
            domain = [('name', '=', 'VED')]
        currencies = self.env['res.currency'].search(domain)
        if not currencies:
            return True
        for currency in currencies:
            if not inverse:
                currency_code = currency.name
            url = 'http://www.bcv.org.ve/estadisticas/consumidor'
            response = requests.get(url, verify=False)
            tree = html.fromstring(response.content)
            path = "//div[@id='{}']//strong".format(currencies_name[currency_code])
            amount_rate = round(float(tree.xpath(path)[0].text.strip().replace(',','.')), 4)
            date_rate = datetime.strptime(tree.xpath("//span[contains(@class, 'date-display-single')]/@content")[0], '%Y-%m-%dT%H:%M:%S%z').date()
            currency_rate = self.env['res.currency.rate'].search([('name', '=', date_rate), ('currency_id', '=', currency.id)])
            if not inverse:
                amount_rate = round(1/amount_rate, 8)
            if not currency_rate:
                currency_rate = self.env['res.currency.rate'].create({
                    'name': date_rate,
                    'currency_id': currency.id,
                    'rate': amount_rate,
                })
                currency._compute_current_rate()
        return True

    @api.model
    def run_update_currency(self):
        records = self.search([("curr_next_execution_date", "<=", fields.Date.today())])
        to_update = self.env["res.company"]
        interval_mapping = {
            "daily": relativedelta(days=+1),
            "weekly": relativedelta(weeks=+1),
            "monthly": relativedelta(months=+1),
        }

        for record in records:
            next_update = interval_mapping.get(record.currency_interval_period)
            if next_update:
                record.curr_next_execution_date = dt.date.today() + next_update
                to_update |= record
            else:
                record.curr_next_execution_date = False

        if to_update:
            to_update.update_currency_rates()
