# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'
EXTERNAL_ID_NAME = 'company_main'

# -------------------------
# Verificación de XML IDs
# -------------------------
XML_IDS_TO_CHECK = [
    'l10n_ve_evo_group_1', 'l10n_ve_evo_group_10', 'l10n_ve_evo_group_11',
    'l10n_ve_evo_110000', 'l10n_ve_evo_111000', 'l10n_ve_evo_114000',
    'l10n_ve_evo_115000', 'l10n_ve_evo_130000', 'l10n_ve_evo_140000',
    'l10n_ve_evo_151100', 'l10n_ve_evo_159000', 'l10n_ve_evo_210000',
    'l10n_ve_evo_214000', 'l10n_ve_evo_215000', 'l10n_ve_evo_270000',
    'l10n_ve_evo_290000', 'l10n_ve_evo_310000', 'l10n_ve_evo_390000',
    'l10n_ve_evo_410000', 'l10n_ve_evo_420000', 'l10n_ve_evo_490000',
    'l10n_ve_evo_511000', 'l10n_ve_evo_601000', 'l10n_ve_evo_611100',
    'l10n_ve_evo_621000', 'l10n_ve_evo_700000', 'l10n_ve_evo_710000',
    'l10n_ve_evo_720000', 'l10n_ve_evo_730000', 'l10n_ve_evo_740000',
    'l10n_ve_evo_stock_journal', 'l10n_ve_evo_stock_valuation_journal',
    'l10n_ve_evo_tax_group_iva_16', 'l10n_ve_evo_tax_group_iva_8', 'l10n_ve_evo_tax_group_exento',
    'l10n_ve_evo_iva_sale_16', 'l10n_ve_evo_iva_purchase_16',
    'l10n_ve_evo_iva_sale_8', 'l10n_ve_evo_iva_sale_exento',
    'l10n_ve_evo_domestic_fp', 'l10n_ve_evo_contribuyente_fp', 'l10n_ve_evo_export_fp',
]

def _ensure_records_exist(env):
    missing = []
    for xml_id in XML_IDS_TO_CHECK:
        full_xmlid = f'{MODULE}.{xml_id}'
        try:
            res = env.ref(full_xmlid, raise_if_not_found=False)
            if not res:
                missing.append(full_xmlid)
        except Exception as e:
            _logger.exception("Error comprobando xmlid %s: %s", full_xmlid, e)
            missing.append(full_xmlid)
    if missing:
        _logger.warning("Faltan xml ids tras instalar %s: %s", MODULE, ', '.join(missing))
    else:
        _logger.info("Todos los xml ids esperados para %s están presentes.", MODULE)

# -------------------------
# Hook principal
# -------------------------
def create_company_if_missing(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Iniciando post-init hook para %s", MODULE)

    # 1) Verificar/crear compañía
    Company = env['res.company'].sudo()
    Partner = env['res.partner'].sudo()
    Imd = env['ir.model.data'].sudo()

    company = Company.search([('name', '=', COMPANY_NAME)], limit=1)
    if not company:
        partner = Partner.create({
            'name': COMPANY_NAME,
            'is_company': True,
            'vat': COMPANY_VAT,
            'company_type': 'company',
        })
        company = Company.create({'name': COMPANY_NAME, 'partner_id': partner.id})
        _logger.info("Compañía creada: %s", company.name)
    else:
        _logger.info("Compañía ya existe: %s", company.name)

    # External ID opcional
    if not Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME)], limit=1):
        Imd.create({'module': MODULE, 'name': EXTERNAL_ID_NAME, 'model': 'res.company', 'res_id': company.id})

    # 2) Verificar XML IDs
    _ensure_records_exist(env)

    # 3) Activar impuestos si están inactivos
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

    _logger.info("create_company_if_missing: finalizado.")
