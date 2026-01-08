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

# Lista corregida con los nombres exactos de tus archivos .xml
DATA_FILES = [
    'data/account.group-ve.xml',
    'data/account.tax.group.xml',
    'data/account.journal.xml',
    'data/account.fiscal.position.xml',
    'data/account_account_ve.xml', # Asegúrate que el archivo se llame así en la carpeta data
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

    # 1. Localizar o crear la compañía
    company = Company.search(['|', ('name', '=', COMPANY_NAME), ('vat', '=', COMPANY_VAT)], limit=1)
    
    if not company:
        _logger.info("Creando compañía %s", COMPANY_NAME)
        company = Company.create({
            'name': COMPANY_NAME,
            'vat': COMPANY_VAT,
            'country_id': env.ref('base.ve').id,
            'currency_id': env.ref('base.VED').id, # Asegúrate que el ISO de Bolívares sea VED o VES
        })
    
    # Asegurar el External ID para que otros XML puedan referenciarlo si es necesario
    imd_rec = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME)])
    if not imd_rec:
        Imd.create({
            'module': MODULE,
            'name': EXTERNAL_ID_NAME,
            'model': 'res.company',
            'res_id': company.id,
            'noupdate': True,
        })

    # 2. Cargar los archivos de datos manualmente
    _load_data_files(env)

    # 3. Vincular registros huérfanos
    _assign_orphans(env, company)
    
    # 4. Forzar activación
    _force_activation(env, company)

def _load_data_files(env):
    """Carga los archivos XML definidos en DATA_FILES."""
    for relative_path in DATA_FILES:
        try:
            # Construir ruta absoluta
            path = os.path.join(os.path.dirname(__file__), relative_path.replace('data/', ''))
            # Si los archivos están dentro de una carpeta 'data', asegúrate de que la ruta sea correcta
            # Aquí asumimos que están en la subcarpeta 'data' del módulo
            real_path = os.path.join(os.path.dirname(__file__), '..', relative_path)
            
            if os.path.exists(real_path):
                _logger.info("Cargando archivo de datos: %s", relative_path)
                convert.convert_file(env.cr, MODULE, relative_path, {}, 'init', noupdate=False)
            else:
                _logger.error("No se encontró el archivo: %s", real_path)
        except Exception as e:
            _logger.error("Error cargando %s: %s", relative_path, e)

def _assign_orphans(env, company):
    """Vincula registros cargados por XML a la compañía creada."""
    models = [
        ('account.tax', 'Impuestos'),
        ('account.journal', 'Diarios'),
        ('account.fiscal.position', 'Posiciones Fiscales'),
        ('account.group', 'Grupos de Cuentas'),
        ('account.account', 'Cuentas')
    ]
    for model_name, label in models:
        records = env[model_name].search([('company_id', '=', False)])
        for rec in records:
            # Verificar si el registro pertenece a este módulo mediante su XML ID
            xml_id = rec.get_external_id().get(rec.id)
            if xml_id and xml_id.startswith(MODULE):
                rec.write({'company_id': company.id})

def _force_activation(env, company):
    """Activa los registros para la compañía."""
    env['account.tax'].search([('company_id', '=', company.id)]).write({'active': True})
    env['account.fiscal.position'].search([('company_id', '=', company.id)]).write({'active': True})