from odoo import api, SUPERUSER_ID
from odoo.tools import convert
import logging
import os

_logger = logging.getLogger(__name__)

# Constantes del módulo
MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'
EXTERNAL_ID_NAME = 'company_main'

def create_company_if_missing(env):
    """
    Hook post-init para la localización de Venezuela:
    Carga el plan de cuentas manualmente tras asegurar la existencia de la compañía.
    """
    env = env(user=SUPERUSER_ID)
    _logger.info("Iniciando post-init hook para %s", MODULE)
    
    Company = env['res.company']
    Imd = env['ir.model.data']

    # 1. Localizar o crear la compañía MOTOFIT
    company = Company.search(['|', ('vat', '=', COMPANY_VAT), ('name', '=', COMPANY_NAME)], limit=1)
    if not company:
        partner = env['res.partner'].create({
            'name': COMPANY_NAME,
            'is_company': True,
            'vat': COMPANY_VAT,
            'country_id': env.ref('base.ve').id,
        })
        # Intentar asignar VED (Bolívar Digital)
        currency = env.ref('base.VED', raise_if_not_found=False)
        company = Company.create({
            'name': COMPANY_NAME, 
            'partner_id': partner.id,
            'currency_id': currency.id if currency else env.company.currency_id.id
        })
        _logger.info("Compañía '%s' creada satisfactoriamente.", COMPANY_NAME)
    
    # 2. Asegurar que el ID Externo 'company_main' existe para el XML de cuentas
    exist_id = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME)], limit=1)
    if not exist_id:
        Imd.create({
            'module': MODULE, 
            'name': EXTERNAL_ID_NAME, 
            'model': 'res.company', 
            'res_id': company.id,
            'noupdate': True
        })
        _logger.info("External ID '%s' vinculado a la compañía.", EXTERNAL_ID_NAME)

    # 3. CARGA MANUAL DEL PLAN DE CUENTAS (account_account_data.xml)
    # Esto evita el error de "accounts must be assigned to at least one company"
    _load_chart_of_accounts(env)

    # 4. Vincular registros cargados previamente que no tengan compañía
    _assign_orphans(env, company)

    # 5. Activar impuestos y posiciones
    _force_activation(env, company)

    _logger.info("Proceso de post-instalación completado con éxito.")

def _load_chart_of_accounts(env):
    """Función para cargar el archivo XML de cuentas usando el importador de Odoo."""
    try:
        _logger.info("Importando plan de cuentas desde account_account_data.xml...")
        from odoo.modules.module import get_resource_path
        
        # Obtenemos la ruta física del archivo
        file_path = get_resource_path(MODULE, 'data', 'account_account_data.xml')
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                # convert_xml_import procesa el archivo igual que si estuviera en el manifiesto
                convert.convert_xml_import(env.cr, MODULE, f, idref={}, mode='init', noupdate=False)
            _logger.info("Plan de cuentas cargado exitosamente.")
        else:
            _logger.error("No se encontró el archivo en: data/account_account_data.xml")
    except Exception as e:
        _logger.error("Error durante la carga manual del plan de cuentas: %s", e)

def _assign_orphans(env, company):
    """Vincula impuestos, diarios y posiciones que se cargaron sin compañía asignada."""
    models = [
        ('account.tax', 'Impuestos'),
        ('account.journal', 'Diarios'),
        ('account.fiscal.position', 'Posiciones Fiscales')
    ]
    for model_name, label in models:
        try:
            records = env[model_name].search([
                ('company_id', '=', False)
            ])
            for rec in records:
                # Verificar si el registro pertenece a este módulo
                xml_id = rec.get_external_id().get(rec.id)
                if xml_id and xml_id.startswith(MODULE):
                    rec.write({'company_id': company.id})
                    _logger.debug("Sincronizado %s: %s", label, rec.name)
        except Exception as e:
            _logger.error("Error al vincular registros de %s: %s", label, e)

def _force_activation(env, company):
    """Asegura que los impuestos y posiciones fiscales estén activos."""
    env['account.tax'].search([('company_id', '=', company.id)]).write({'active': True})
    env['account.fiscal.position'].search([('company_id', '=', company.id)]).write({'active': True})
    _logger.info("Configuración contable activada.")