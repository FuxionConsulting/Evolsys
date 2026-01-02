# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.addons.account.models.chart_template import template
from odoo.tools.misc import file_open

class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('ve')
    def _get_ve_template_data(self):
        """
        Define la configuración básica para el Plan de Cuentas de Venezuela.
        """
        return {
            # Se usa 've_chart_template' como ID externo para que el hook pueda referenciarlo.
            'name': _('VE Standard (EVO)'),
            'visible': True, # Visible para que el usuario pueda seleccionarlo
            'code_digits': '6',
            # Cuentas Contables Clave (IDs deben coincidir con account.account-ve.csv)
            # 130000: Cuentas por Cobrar - Clientes
            'property_account_receivable_id': 'l10n_ve_evo_130000', 
            # 210000: Cuentas por Pagar - Proveedores
            'property_account_payable_id': 'l10n_ve_evo_210000',     
            'downpayment_account_id': 'l10n_ve_evo_115000',          # Anticipos (Activo)
        }

    @template('ve', 'res.company')
    def _get_ve_res_company(self):
        """
        Configura la compañía con cuentas predeterminadas.
        Se utiliza la estructura de diccionario anidado que Odoo espera para el modelo res.company.
        """
        return {
            'base.main_company': { # Clave: ID de la compañía principal
                'account_fiscal_country_id': 'base.ve', # Referencia al país VE
                'account_sale_tax_id': 'iva_sale_16',        # IVA Venta 16% 
                'account_purchase_tax_id': 'iva_purchase_16',  # IVA Compra 16% 
                
                # Cuentas de Moneda y Descuentos
                'income_currency_exchange_account_id': 'l10n_ve_evo_750000',
                'expense_currency_exchange_account_id': 'l10n_ve_evo_650000',
                'account_journal_early_pay_discount_gain_account_id': 'l10n_ve_evo_780000', 
                'account_journal_early_pay_discount_loss_account_id': 'l10n_ve_evo_680000', 

                # Otras Cuentas
                'transfer_account_id': 'l10n_ve_evo_114000', # Cuenta Puente
                'account_journal_suspense_account_id': 'l10n_ve_evo_270000', # Cuenta de Suspenso
                'expense_account_id': 'l10n_ve_evo_600000', 
                'expense_depreciation_account_id': 'l10n_ve_evo_690000', 
                'income_account_id': 'l10n_ve_evo_700000', 
                
                # Cuentas relacionadas con Inventario
                'account_stock_journal_id': 'inventory_valuation', # Diario predefinido por Odoo
                'account_stock_valuation_id': 'l10n_ve_evo_140000', # Inventario (Activo)
                
                # Cuenta POS (Punto de Venta)
                'account_default_pos_receivable_account_id': 'l10n_ve_evo_130000', 
            }
        }

    @template('ve', 'account.journal')
    def _get_ve_account_journal(self):
        """
        Configura los diarios predeterminados (Venta, Compra, Efectivo, Banco)
        e incluye el campo 'code' (Prefijo de secuencia) obligatorio.
        """
        return {
            'bank': {
                'name': _('Banco Principal USD'), # Nombre ajustado para reflejar USD
                'type': 'bank',
                'code': 'USS', # Campo 'code' obligatorio
                'default_account_id': 'l10n_ve_evo_111000', # Cuenta de Caja/Banco USD
            },
            'cash': {
                'name': _('Efectivo VEB'),
                'type': 'cash',
                'code': 'EFF', # Campo 'code' obligatorio
                'default_account_id': 'l10n_ve_evo_110000', # Cuenta de Caja/Banco VEB
            },
            'sale': {
                'name': _('Ventas'),
                'type': 'sale',
                'code': 'VTA', # Campo 'code' obligatorio
                'refund_sequence': True,
            },
            'purchase': {
                'name': _('Compras'),
                'type': 'purchase',
                'code': 'COM', # Campo 'code' obligatorio
                'refund_sequence': True,
            },
            'misc': {
                'name': _('Asientos Varios'),
                'type': 'general',
                'code': 'MISL', # Diario general (importante)
            },
        }

#    @template('ve', 'account.chart.template')
#    def _set_template_ref(self):
#        """
#        Define el ID externo del gráfico para que pueda ser referenciado por el hook.
#        """
#        return {
#            'l10n_ve_evo.ve_chart_template': self,
#        }