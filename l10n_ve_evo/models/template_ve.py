# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.addons.account.models.chart_template import template

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ve')
    def _get_ve_template_data(self):
        return {
            'name': _('Evolsys'),
            'visible': True,
            'code_digits': 6,  # entero, no string
            # Estos deben existir en ir.model.data al momento de usar el template
            #'property_account_receivable_id': 'l10n_ve_evo.l10n_ve_evo_130000',
            #'property_account_payable_id': 'l10n_ve_evo.l10n_ve_evo_210000',
            #'downpayment_account_id': 'l10n_ve_evo.l10n_ve_evo_115000',
        }

    @template('ve', 'res.company')
    def _get_ve_res_company(self):
        return {
            'base.main_company': {
                'account_fiscal_country_id': 'base.ve',
                'account_sale_tax_id': 'l10n_ve_evo.l10n_ve_evo_iva_sale_16',
                'account_purchase_tax_id': 'l10n_ve_evo.l10n_ve_evo_iva_purchase_16',
                'income_currency_exchange_account_id': 'l10n_ve_evo.l10n_ve_evo_730000',
                'expense_currency_exchange_account_id': 'l10n_ve_evo.l10n_ve_evo_740000',
                'transfer_account_id': 'l10n_ve_evo.l10n_ve_evo_114000',
                'account_journal_suspense_account_id': 'l10n_ve_evo.l10n_ve_evo_270000',
                'expense_account_id': 'l10n_ve_evo.l10n_ve_evo_611100',
                'expense_depreciation_account_id': 'l10n_ve_evo.l10n_ve_evo_621000',
                'income_account_id': 'l10n_ve_evo.l10n_ve_evo_700000',
                'account_stock_valuation_id': 'l10n_ve_evo.l10n_ve_evo_140000',
                'account_default_pos_receivable_account_id': 'l10n_ve_evo.l10n_ve_evo_130000',
            }
        }

    @template('ve', 'account.journal')
    def _get_ve_account_journal(self):
        return {
            'bank': {
                'name': _('Banco Principal USD'),
                'type': 'bank',
                'code': 'USS',
                'default_account_id': 'l10n_ve_evo.l10n_ve_evo_111000',
            },
            'cash': {
                'name': _('Efectivo VEB'),
                'type': 'cash',
                'code': 'EFF',
                'default_account_id': 'l10n_ve_evo.l10n_ve_evo_110000',
            },
            'sale': {'name': _('Ventas'), 'type': 'sale', 'code': 'VTA', 'refund_sequence': True},
            'purchase': {'name': _('Compras'), 'type': 'purchase', 'code': 'COM', 'refund_sequence': True},
            'misc': {'name': _('Asientos Varios'), 'type': 'general', 'code': 'MISL'},
        }
