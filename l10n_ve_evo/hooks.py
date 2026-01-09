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

    # 1. Localizar o crear la compañía
    company = Company.search(['|', ('name', '=', COMPANY_NAME), ('vat', '=', COMPANY_VAT)], limit=1)
    
    if not company:
        _logger.info("Creando compañía %s", COMPANY_NAME)
        company = Company.create({
            'name': COMPANY_NAME,
            'vat': COMPANY_VAT,
            'country_id': env.ref('base.ve').id,
            'currency_id': env.ref('base.VED', raise_if_not_found=False).id if env.ref('base.VED', raise_if_not_found=False) else env.ref('base.VES').id,
        })
    
    # Asegurar el External ID
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
            # Intentar encontrar la ruta real del archivo
            # Odoo busca los archivos relativos a la raíz del addon
            _logger.info("Cargando archivo de datos: %s", relative_path)
            convert.convert_file(env.cr, MODULE, relative_path, {}, 'init', noupdate=False)
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
        try:
            records = env[model_name].search([('company_id', '=', False)])
            for rec in records:
                xml_id_dict = rec.get_external_id()
                xml_id = xml_id_dict.get(rec.id)
                if xml_id and xml_id.startswith(MODULE):
                    rec.write({'company_id': company.id})
        except Exception:
            continue

def _force_activation(env, company):
    """Activa los registros para la compañía."""
    try:
        env['account.tax'].search([('company_id', '=', company.id)]).write({'active': True})
        env['account.fiscal.position'].search([('company_id', '=', company.id)]).write({'active': True})
    except Exception:
        pass