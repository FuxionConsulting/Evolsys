# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve_evolsys")
    def _get_ve_evolsys_template_data(self):
        return {
            "code_digits": "7",
            "property_account_receivable_id": "account_activa_account_1122001",
            "property_account_payable_id": "account_activa_account_2122001",
            "property_account_expense_categ_id": "account_activa_account_7151001",
            "property_account_income_categ_id": "account_activa_account_5111001",
            "name": _("Evolsys"),
        }

    @template("ve_evolsys", "res.company")
    def _get_ve_evolsys_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                'account_sale_tax_id': 'l10n_ve_evolsys.l10n_ve_evolsys_iva_sale_16',
                'account_purchase_tax_id': 'l10n_ve_evolsys.l10n_ve_evolsys_iva_purchase_16',
                'income_currency_exchange_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_730000',
                'expense_currency_exchange_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_740000',
                'transfer_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_114000',
                'account_journal_suspense_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_270000',
                'expense_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_611100',
                'expense_depreciation_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_621000',
                'income_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_700000',
                'account_stock_valuation_id': 'l10n_ve_evolsys.l10n_ve_evolsys_140000',
                'account_default_pos_receivable_account_id': 'l10n_ve_evolsys.l10n_ve_evolsys_130000',
            },
        }
