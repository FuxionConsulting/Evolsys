# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID, _
import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'

# Lista de xml ids que queremos asegurar estén presentes cuando se instale el paquete fiscal.
XML_IDS_TO_CHECK = [
    # grupos de cuentas
    'l10n_ve_evo_group_1', 'l10n_ve_evo_group_10', 'l10n_ve_evo_group_11',
    # cuentas
    'l10n_ve_evo_110000', 'l10n_ve_evo_111000', 'l10n_ve_evo_114000',
    'l10n_ve_evo_115000', 'l10n_ve_evo_130000', 'l10n_ve_evo_140000',
    'l10n_ve_evo_151100', 'l10n_ve_evo_159000', 'l10n_ve_evo_210000',
    'l10n_ve_evo_214000', 'l10n_ve_evo_215000', 'l10n_ve_evo_270000',
    'l10n_ve_evo_290000', 'l10n_ve_evo_310000', 'l10n_ve_evo_390000',
    'l10n_ve_evo_410000', 'l10n_ve_evo_420000', 'l10n_ve_evo_490000',
    'l10n_ve_evo_511000', 'l10n_ve_evo_601000', 'l10n_ve_evo_611100',
    'l10n_ve_evo_621000', 'l10n_ve_evo_700000', 'l10n_ve_evo_710000',
    'l10n_ve_evo_720000', 'l10n_ve_evo_730000', 'l10n_ve_evo_740000',
    # journals
    'l10n_ve_evo_stock_journal', 'l10n_ve_evo_stock_valuation_journal',
    # tax groups
    'l10n_ve_evo_tax_group_iva_16', 'l10n_ve_evo_tax_group_iva_8', 'l10n_ve_evo_tax_group_exento',
    # taxes
    'l10n_ve_evo_iva_sale_16', 'l10n_ve_evo_iva_purchase_16',
    'l10n_ve_evo_iva_sale_8', 'l10n_ve_evo_iva_sale_exento',
    # fiscal positions
    'l10n_ve_evo_domestic_fp', 'l10n_ve_evo_contribuyente_fp', 'l10n_ve_evo_export_fp',
]

def _ensure_records_exist(env):
    """Verifica que los xml ids listados existan en la base y registra advertencias si faltan."""
    missing = []
    for xml_id in XML_IDS_TO_CHECK:
        full_xmlid = '%s.%s' % (MODULE, xml_id)
        try:
            res = env.ref(full_xmlid, raise_if_not_found=False)
            if not res:
                missing.append(full_xmlid)
        except Exception as e:
            _logger.exception("Error comprobando xmlid %s: %s", full_xmlid, e)
            missing.append(full_xmlid)
    if missing:
        _logger.warning(
            "Los siguientes xml ids no se encontraron en la base tras instalar %s: %s",
            MODULE, ', '.join(missing)
        )
    else:
        _logger.info("Todos los xml ids esperados para %s están presentes.", MODULE)

def _post_init_install(env):
    """Acciones a ejecutar tras la instalación del módulo o al instalar el paquete fiscal."""
    _logger.info("Iniciando post-init hook para %s", MODULE)
    _ensure_records_exist(env)

    try:
        taxes = [
            'l10n_ve_evo.l10n_ve_evo_iva_sale_16',
            'l10n_ve_evo.l10n_ve_evo_iva_purchase_16',
            'l10n_ve_evo.l10n_ve_evo_iva_sale_8',
            'l10n_ve_evo.l10n_ve_evo_iva_sale_exento',
        ]
        for xmlid in taxes:
            tax = env.ref(xmlid, raise_if_not_found=False)
            if tax and not tax.active:
                tax.active = True
                _logger.info("Activado impuesto %s", xmlid)
    except Exception:
        _logger.exception("Error activando impuestos en post init")

def _uninstall_cleanup(env):
    """Limpieza al desinstalar el módulo (no borra datos por seguridad)."""
    _logger.info(
        "Ejecutando uninstall hook para %s. No se eliminarán registros automáticamente.",
        MODULE
    )

