# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# POST INIT HOOK (Odoo 19)
# ---------------------------------------------------------
def _post_init_hook(env):
    """
    Hook ejecutado justo después de instalar el módulo.
    Se usa para corregir datos, asignar país VE y ajustar impuestos.
    """
    try:
        # Buscar país Venezuela
        ve = env.ref('base.ve', raise_if_not_found=False)
        if not ve:
            ve = env['res.country'].search([('code', '=', 'VE')], limit=1)

        if ve:
            # 1. Asegurar que todos los tax groups tengan country_id = VE
            groups = env['account.tax.group'].search([('country_id', '=', False)])
            if groups:
                groups.write({'country_id': ve.id})
                _logger.info(f"[l10n_ve_evo] Asignado country_id VE a {len(groups)} tax groups.")

            # 2. Asignar país VE al chart template
            chart_template = env.ref('l10n_ve_evo.ve_chart_template', raise_if_not_found=False)
            if chart_template:
                chart_template.country_id = ve.id
                _logger.info("[l10n_ve_evo] Chart template asignado a VE.")

        # 3. Corregir simetría de impuestos
        tax_ids = []
        for xmlid in ['l10n_ve_evo.iva_sale_16', 'l10n_ve_evo.iva_sale_8']:
            tax = env.ref(xmlid, raise_if_not_found=False)
            if tax:
                tax_ids.append(tax)

        for tax in tax_ids:
            for line in tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax'):
                refund_line = tax.refund_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                if refund_line:
                    refund_line.write({'factor_percent': -abs(line.factor_percent)})
                    _logger.info(f"[l10n_ve_evo] Ajustado refund factor para impuesto {tax.name}.")

    except Exception as e:
        _logger.exception(f"[l10n_ve_evo] Error en _post_init_hook: {e}")


# ---------------------------------------------------------
# UNINSTALL HOOK (Odoo 19)
# ---------------------------------------------------------
def uninstall_hook(env):
    """
    Hook ejecutado al desinstalar el módulo.
    Limpia datos creados por la localización para evitar inconsistencias.
    """
    try:
        # 1. Eliminar ciudades, municipios y parroquias creadas por el módulo
        for model in ['res.country.parish', 'res.country.municipality', 'res.city']:
            records = env[model].search([('create_uid', '=', SUPERUSER_ID)])
            if records:
                count = len(records)
                records.unlink()
                _logger.info(f"[l10n_ve_evo] Eliminados {count} registros de {model}.")

        # 2. Restaurar tax groups sin país
        groups = env['account.tax.group'].search([('country_id.code', '=', 'VE')])
        if groups:
            groups.write({'country_id': False})
            _logger.info(f"[l10n_ve_evo] Restaurado country_id en {len(groups)} tax groups.")

        # 3. Restaurar chart template
        chart_template = env.ref('l10n_ve_evo.ve_chart_template', raise_if_not_found=False)
        if chart_template:
            chart_template.country_id = False
            _logger.info("[l10n_ve_evo] Chart template restaurado.")

        # 4. Restaurar impuestos modificados
        for xmlid in ['l10n_ve_evo.iva_sale_16', 'l10n_ve_evo.iva_sale_8']:
            tax = env.ref(xmlid, raise_if_not_found=False)
            if tax:
                refund_lines = tax.refund_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                refund_lines.write({'factor_percent': 100})
                _logger.info(f"[l10n_ve_evo] Restaurado refund factor para impuesto {tax.name}.")

    except Exception as e:
        _logger.exception(f"[l10n_ve_evo] Error en uninstall_hook: {e}")
