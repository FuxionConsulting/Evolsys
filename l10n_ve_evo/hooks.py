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
    """Verifica que los xml ids listados existan en la base."""
    missing = []
    for xml_id in XML_IDS_TO_CHECK:
        full_xmlid = f'{MODULE}.{xml_id}'
        res = env.ref(full_xmlid, raise_if_not_found=False)
        if not res:
            missing.append(full_xmlid)
    if missing:
        _logger.warning("Faltan xml ids tras instalar %s: %s", MODULE, ', '.join(missing))

def create_company_if_missing(env):
    """Hook post-init para crear compañía y vincularla correctamente antes de cargar datos."""
    # Forzar modo superusuario y asegurar que trabajamos con la base de datos correcta
    env = env(user=SUPERUSER_ID)
    _logger.info("Iniciando post-init hook para %s", MODULE)
    
    Company = env['res.company']
    Partner = env['res.partner']
    Imd = env['ir.model.data']

    # 1. Intentar localizar la compañía por RIF (VAT) o Nombre
    company = Company.search(['|', ('vat', '=', COMPANY_VAT), ('name', '=', COMPANY_NAME)], limit=1)
    
    if not company:
        _logger.info("Creando partner para la compañía...")
        partner = Partner.create({
            'name': COMPANY_NAME,
            'is_company': True,
            'vat': COMPANY_VAT,
            'country_id': env.ref('base.ve').id,
        })
        
        _logger.info("Creando compañía %s...", COMPANY_NAME)
        company = Company.create({
            'name': COMPANY_NAME, 
            'partner_id': partner.id,
            'currency_id': env.ref('base.VED', raise_if_not_found=False).id if env.ref('base.VED', raise_if_not_found=False) else env.company.currency_id.id
        })
    
    # 2. Vincular el External ID manualmente (CRÍTICO)
    # Esto permite que los archivos XML usen ref('l10n_ve_evo.company_main') sin fallar
    exist_id = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME)], limit=1)
    if not exist_id:
        Imd.create({
            'module': MODULE, 
            'name': EXTERNAL_ID_NAME, 
            'model': 'res.company', 
            'res_id': company.id,
            'noupdate': True
        })
        _logger.info("External ID %s asignado a la compañía %s", EXTERNAL_ID_NAME, company.name)

    # 3. Solución al error de diarios: 
    # Si Odoo creó diarios automáticos al crear la compañía, 
    # los marcamos para que no interfieran o los dejamos listos.
    # El error suele venir porque el XML intenta crear 'l10n_ve_evo_stock_journal' 
    # y hay un conflicto de borrado de otros diarios de la misma compañía.
    
    _ensure_records_exist(env)

    # 4. Activación de impuestos (si ya fueron cargados por el XML de data)
    try:
        taxes = [
            f'{MODULE}.l10n_ve_evo_iva_sale_16',
            f'{MODULE}.l10n_ve_evo_iva_purchase_16',
            f'{MODULE}.l10n_ve_evo_iva_sale_8',
            f'{MODULE}.l10n_ve_evo_iva_sale_exento',
        ]
        for xmlid in taxes:
            tax = env.ref(xmlid, raise_if_not_found=False)
            if tax and not tax.active:
                tax.active = True
                _logger.info("Impuesto activado: %s", xmlid)
    except Exception as e:
        _logger.error("Error activando impuestos: %s", e)

    _logger.info("Hook de post-instalación finalizado exitosamente.")