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

# Lista de archivos que deben cargarse manualmente después de crear la compañía
# para evitar errores de validación y asegurar la vinculación correcta.
DATA_FILES = [
    'data/account.group-ve.xml',
    'data/account.tax.group.xml',
    'data/account.journal.xml',
    'data/account.fiscal.position.xml',
    'data/account_account_ve.xml',
]

def create_company_if_missing(env):
    """
    Hook post-init para la localización de Venezuela:
    1. Asegura la existencia de la compañía y su ID externo.
    2. Carga manualmente todos los XMLs contables.
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
    
    # 2. Asegurar que el ID Externo 'company_main' existe para los XMLs
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

    # 3. CARGA MANUAL DE TODOS LOS DATOS CONTABLES
    # Recorremos la lista de archivos definidos en DATA_FILES
    for xml_file in DATA_FILES:
        _load_data_file(env, xml_file)

    # 4. Vincular registros que pudieran haber quedado huérfanos
    _assign_orphans(env, company)

    # 5. Activar impuestos y posiciones
    _force_activation(env, company)

    _logger.info("Proceso de post-instalación completado con éxito.")

def _load_data_file(env, relative_path):
    """Función genérica para cargar archivos XML del módulo."""
    try:
        _logger.info("Importando archivo: %s", relative_path)
        from odoo.modules.module import get_resource_path
        
        file_path = get_resource_path(MODULE, relative_path)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                convert.convert_xml_import(env.cr, MODULE, f, idref={}, mode='init', noupdate=False)
            _logger.info("Archivo %s cargado exitosamente.", relative_path)
        else:
            _logger.error("No se encontró el archivo en: %s", relative_path)
    except Exception as e:
        _logger.error("Error cargando %s: %s", relative_path, e)

def _assign_orphans(env, company):
    """Vincula impuestos, diarios y posiciones que se cargaron sin compañía asignada."""
    models = [
        ('account.tax', 'Impuestos'),
        ('account.journal', 'Diarios'),
        ('account.fiscal.position', 'Posiciones Fiscales'),
        ('account.group', 'Grupos de Cuentas'),
        ('account.account', 'Cuentas')
    ]
    for model_name, label in models:
        try:
            # Buscamos registros de este módulo sin compañía
            domain = [('company_id', '=', False)]
            records = env[model_name].search(domain)
            for rec in records:
                xml_id = rec.get_external_id().get(rec.id)
                if xml_id and xml_id.startswith(MODULE):
                    rec.write({'company_id': company.id})
                    _logger.debug("Sincronizado %s: %s", label, rec.name)
        except Exception as e:
            _logger.error("Error al vincular registros de %s: %s", label, e)

def _force_activation(env, company):
    """Asegura que los impuestos y posiciones fiscales estén activos."""
    try:
        env['account.tax'].search([('company_id', '=', company.id)]).write({'active': True})
        env['account.fiscal.position'].search([('company_id', '=', company.id)]).write({'active': True})
        _logger.info("Configuración contable activada.")
    except Exception as e:
        _logger.error("Error activando configuración: %s", e)