# -*- coding: utf-8 -*-
import logging
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# POST INIT HOOK (Odoo 19)
# ---------------------------------------------------------
def _post_init_hook(env):
    """
    Post-init hook para l10n_ve_evo:
    - Activa el chart template 've' en Venezuela.
    - Instala el plan de cuentas en la compañía principal.
    - Ajusta cuentas por defecto exigidas por Odoo 19.
    - Configura ajustes contables visibles en res.config.settings.
    """
    try:
        # 1) Obtener país VE
        ve = env.ref('base.ve', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not ve:
            _logger.error('[l10n_ve_evo] No se encontró el país VE.')
            return

        # 2) Obtener el chart template registrado con @template('ve')
        chart_template = env.ref('l10n_ve_evo.ve_chart_template', raise_if_not_found=False)
        if not chart_template:
            chart_template = env['account.chart.template'].search([('name', '=', 'Evolsys')], limit=1)

        if not chart_template:
            _logger.error('[l10n_ve_evo] No se encontró el chart template Evolsys.')
            return

        # 3) Asignar el chart template al país VE
        chart_template.country_id = ve.id
        _logger.info('[l10n_ve_evo] Chart template Evolsys asignado al país VE.')

        # 4) Instalar el plan de cuentas en la compañía principal
        company = env['res.company'].search([], limit=1)
        if company:
            try:
                chart_template.try_loading(company)
                _logger.info('[l10n_ve_evo] Plan de cuentas Evolsys instalado en la compañía %s.', company.name)
            except Exception:
                _logger.exception('[l10n_ve_evo] Error instalando plan de cuentas Evolsys en la compañía.')

        # 5) Ajustar cuentas por defecto exigidas por Odoo 19 (ir.default)
        defaults_map = {
            'property_account_receivable_id': 'l10n_ve_evo.l10n_ve_evo_130000',
            'property_account_payable_id': 'l10n_ve_evo.l10n_ve_evo_210000',
            'downpayment_account_id': 'l10n_ve_evo.l10n_ve_evo_115000',
        }
        for field, xmlid in defaults_map.items():
            rec = env.ref(xmlid, raise_if_not_found=False)
            if rec and company:
                try:
                    env['ir.default'].set('res.company', field, rec.id, company_id=company.id)
                    _logger.info('[l10n_ve_evo] ir.default set %s -> %s', field, xmlid)
                except Exception:
                    _logger.exception('[l10n_ve_evo] Error asignando default %s con xmlid %s', field, xmlid)

        # 6) Establecer cuentas por defecto en res.config.settings (ajustes contables)
        try:
            config_vals = {}
            def safe_ref(xmlid):
                return env.ref(xmlid, raise_if_not_found=False)

            mapping = {
                'income_account_id': 'l10n_ve_evo.l10n_ve_evo_700000',
                'expense_account_id': 'l10n_ve_evo.l10n_ve_evo_611100',
                'downpayment_account_id': 'l10n_ve_evo.l10n_ve_evo_115000',
                'account_stock_valuation_id': 'l10n_ve_evo.l10n_ve_evo_140000',
                'account_journal_stock_valuation_id': 'l10n_ve_evo.l10n_ve_evo_stock_valuation_journal',
            }

            for field, xmlid in mapping.items():
                rec = safe_ref(xmlid)
                if rec:
                    config_vals[field] = rec.id
                else:
                    _logger.warning('[l10n_ve_evo] No se encontró xmlid para %s -> %s', field, xmlid)

            if config_vals:
                settings = env['res.config.settings'].create(config_vals)
                settings.execute()
                _logger.info('[l10n_ve_evo] Configuración contable aplicada en res.config.settings.')
            else:
                _logger.warning('[l10n_ve_evo] No se aplicó configuración contable: ningún xmlid válido encontrado.')

        except Exception:
            _logger.exception('[l10n_ve_evo] Error aplicando configuración contable en ajustes.')

    except Exception as e:
        _logger.exception('[l10n_ve_evo] Error en _post_init_hook: %s', e)


# ---------------------------------------------------------
# UNINSTALL HOOK (Odoo 19)
# ---------------------------------------------------------
def uninstall_hook(env):
    """
    Uninstall hook: limpia geografía creada por el módulo, restaura tax groups y chart template,
    y revierte cambios en impuestos.
    """
    try:
        for model in ['res.country.parish', 'res.country.municipality', 'res.city']:
            records = env[model].search([('create_uid', '=', SUPERUSER_ID)])
            if records:
                count = len(records)
                records.unlink()
                _logger.info('[l10n_ve_evo] Eliminados %d registros de %s.', count, model)

        groups = env['account.tax.group'].search([('country_id.code', '=', 'VE')])
        if groups:
            groups.write({'country_id': False})
            _logger.info('[l10n_ve_evo] Restaurado country_id en %d tax groups.', len(groups))

        chart_template = env.ref('l10n_ve_evo.ve_chart_template', raise_if_not_found=False)
        if chart_template:
            try:
                chart_template.country_id = False
                _logger.info('[l10n_ve_evo] Chart template restaurado.')
            except Exception:
                _logger.exception('[l10n_ve_evo] Error restaurando chart template.')

        for xmlid in ['l10n_ve_evo.l10n_ve_evo_iva_sale_16', 'l10n_ve_evo.l10n_ve_evo_iva_sale_8']:
            tax = env.ref(xmlid, raise_if_not_found=False)
            if tax:
                try:
                    refund_lines = tax.refund_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                    refund_lines.write({'factor_percent': 100})
                    _logger.info('[l10n_ve_evo] Restaurado refund factor para impuesto %s.', tax.name)
                except Exception:
                    _logger.exception('[l10n_ve_evo] Error restaurando refund factor para %s', xmlid)

    except Exception as e:
        _logger.exception('[l10n_ve_evo] Error en uninstall_hook: %s', e)
