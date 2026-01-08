from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'
EXTERNAL_ID_NAME = 'company_main'

def create_company_if_missing(env):
    """
    Hook post-init: 
    1. Crea/Ubica la compañía.
    2. Vincula el ID externo (company_main).
    3. Asigna registros huérfanos (impuestos/diarios) a la compañía.
    4. Fuerza la activación de impuestos y posiciones fiscales.
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
        company = Company.create({
            'name': COMPANY_NAME, 
            'partner_id': partner.id,
            'country_id': env.ref('base.ve').id,
            'currency_id': env.ref('base.VED', raise_if_not_found=False).id if env.ref('base.VED', raise_if_not_found=False) else env.company.currency_id.id
        })
        _logger.info("Compañía %s creada.", COMPANY_NAME)
    
    # 2. Asegurar el ID Externo para que los XML puedan usar ref('l10n_ve_evo.company_main')
    exist_id = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME)], limit=1)
    if not exist_id:
        Imd.create({
            'module': MODULE, 
            'name': EXTERNAL_ID_NAME, 
            'model': 'res.company', 
            'res_id': company.id,
            'noupdate': True
        })
        _logger.info("ID Externo %s vinculado a la compañía.", EXTERNAL_ID_NAME)

    # 3. Vincular registros del módulo a la compañía (CRÍTICO para visibilidad)
    # Buscamos registros creados por este módulo que no tengan compañía asignada
    models_to_link = [
        ('account.tax.group', 'Grupos de Impuestos'),
        ('account.tax', 'Impuestos'),
        ('account.fiscal.position', 'Posiciones Fiscales'),
        ('account.journal', 'Diarios'),
        ('account.group', 'Grupos de Cuentas')
    ]
    
    for model_name, label in models_to_link:
        try:
            # Buscamos registros cuyos External IDs empiecen por el nombre de nuestro módulo
            # y que no tengan compañía (o tengan la compañía por defecto)
            records = env[model_name].search([
                '|', ('company_id', '=', False), ('company_id', '!=', company.id)
            ])
            
            for rec in records:
                # Obtenemos el XML ID completo (ej: l10n_ve_evo.l10n_ve_evo_iva_sale_16)
                xml_info = rec.get_external_id().get(rec.id)
                if xml_info and xml_info.startswith(MODULE):
                    rec.write({'company_id': company.id})
                    _logger.info("Registro %s [%s] vinculado a MOTOFIT.", label, rec.name)
        except Exception as e:
            _logger.error("Error vinculando %s: %s", label, e)

    # 4. Forzar activación masiva
    _force_activation(env, company)

    _logger.info("Hook de post-instalación finalizado exitosamente.")

def _force_activation(env, company):
    """Activa impuestos y posiciones fiscales para la compañía específica."""
    # Activar Impuestos de la compañía
    taxes = env['account.tax'].search([('company_id', '=', company.id), ('active', '=', False)])
    if taxes:
        taxes.write({'active': True})
        _logger.info("%s impuestos activados.", len(taxes))
    
    # Activar Posiciones Fiscales de la compañía
    fps = env['account.fiscal.position'].search([('company_id', '=', company.id), ('active', '=', False)])
    if fps:
        fps.write({'active': True})
        _logger.info("%s posiciones fiscales activadas.", len(fps))