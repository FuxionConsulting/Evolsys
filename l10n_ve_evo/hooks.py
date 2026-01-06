# hooks.py
# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'  # reemplaza por el RIF real
EXTERNAL_ID_NAME = 'company_main'  # xml_id opcional que se creará en ir.model.data

def duplicate_accounts_per_company(env, codes_to_duplicate=None):
    """
    Duplica cuentas para cada compañía si es necesario evitar errores de unicidad
    del campo `code`. Si `codes_to_duplicate` es None, procesa todas las cuentas.
    Esta función crea nuevas cuentas (copias) asignadas a la compañía objetivo cuando
    la cuenta original no está asignada a esa compañía.
    """
    Account = env['account.account'].sudo()
    Company = env['res.company'].sudo()
    companies = Company.search([])
    if not companies:
        _logger.info('duplicate_accounts_per_company: no hay compañías registradas.')
        return

    # Seleccionar cuentas a procesar
    accounts = Account.search([]) if not codes_to_duplicate else Account.search([('code', 'in', codes_to_duplicate)])
    _logger.info('duplicate_accounts_per_company: procesando %d cuentas para %d compañías', len(accounts), len(companies))

    for acc in accounts:
        assigned_company_ids = set(acc.company_ids.ids)
        for comp in companies:
            if comp.id in assigned_company_ids:
                continue
            try:
                vals = acc.copy_data()[0]
                # Asegurarse de que la copia quede ligada solo a la compañía objetivo
                # copy_data devuelve relaciones many2many como listas; aquí las reemplazamos
                vals.update({
                    'company_ids': [(6, 0, [comp.id])],
                })
                # Si existe company_id en el modelo, asignarla también
                if 'company_id' in vals:
                    vals['company_id'] = comp.id
                Account.create(vals)
                _logger.info('Duplicada cuenta code=%s para compañía %s (id=%s)', acc.code, comp.name, comp.id)
            except Exception:
                _logger.exception('Error duplicando cuenta %s para compañía %s', acc.code, comp.name)


def _assign_company_to_accounts(env, company):
    """
    Asigna company_ids y company_id (si existe) a las cuentas que no tengan compañía.
    Devuelve una tupla (success_count, error_count).
    """
    Account = env['account.account'].sudo()
    accounts = Account.search(['|', ('company_ids', '=', False), ('company_id', '=', False)])
    success = 0
    errors = 0
    _logger.info('_assign_company_to_accounts: asignando compañía %s a %d cuentas', company.name, len(accounts))
    for acc in accounts:
        try:
            # Añadir a company_ids si no está presente
            if company.id not in acc.company_ids.ids:
                acc.write({'company_ids': [(4, company.id)]})
            # También establecer company_id si existe el campo
            if hasattr(acc, 'company_id') and (not acc.company_id or acc.company_id.id != company.id):
                acc.write({'company_id': company.id})
            success += 1
        except Exception as exc:
            errors += 1
            _logger.exception('_assign_company_to_accounts: error asignando compañía a la cuenta %s (%s): %s', acc.display_name, acc.id, exc)
            # Si detectamos un error de unicidad, lo propagamos para que el caller decida duplicar
            # Comprobación simple en el texto del error para detectar constraint de duplicidad
            msg = str(exc).lower()
            if 'unique' in msg or 'duplicate' in msg or 'duplicate key' in msg:
                raise
    return success, errors


def create_company_if_missing(cr, registry):
    """
    Hook de post instalación: asegura la existencia de la compañía (por nombre),
    crea external id opcional y asigna company_ids/company_id a las cuentas que no
    tengan compañía. Si aparece un error de unicidad en `code`, intenta duplicar
    las cuentas por compañía y reintentar la asignación.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env['res.company'].sudo()
    Partner = env['res.partner'].sudo()
    Imd = env['ir.model.data'].sudo()

    # 1) Obtener o crear partner+company (lógica original)
    company = Company.search([('name', '=', COMPANY_NAME)], limit=1)
    if company:
        _logger.info('create_company_if_missing: la compañía ya existe (id=%s).', company.id)
        partner = company.partner_id
        if partner and not partner.vat:
            try:
                partner.write({'vat': COMPANY_VAT})
                _logger.info('create_company_if_missing: actualizado vat del partner de la compañía existente.')
            except Exception:
                _logger.exception('create_company_if_missing: error actualizando vat del partner.')
        elif not partner:
            try:
                p = Partner.create({
                    'name': COMPANY_NAME,
                    'is_company': True,
                    'vat': COMPANY_VAT,
                    'company_type': 'company',
                })
                company.write({'partner_id': p.id})
                _logger.info('create_company_if_missing: partner creado y asignado a la compañía existente.')
            except Exception:
                _logger.exception('create_company_if_missing: error creando partner para la compañía existente.')
    else:
        _logger.info('create_company_if_missing: no existe la compañía; creando partner y company.')
        try:
            p = Partner.create({
                'name': COMPANY_NAME,
                'is_company': True,
                'vat': COMPANY_VAT,
                'company_type': 'company',
            })
            company = Company.create({
                'name': COMPANY_NAME,
                'partner_id': p.id,
            })
            _logger.info('create_company_if_missing: compañía creada (id=%s).', company.id)
        except Exception:
            _logger.exception('create_company_if_missing: error creando partner/company.')
            return

    # 2) Crear external id en ir.model.data para poder referenciar la compañía por xml_id si se desea
    try:
        existing = Imd.search([('module', '=', 'l10n_ve_evo'), ('name', '=', EXTERNAL_ID_NAME), ('model', '=', 'res.company')], limit=1)
        if not existing:
            Imd.create({
                'module': 'l10n_ve_evo',
                'name': EXTERNAL_ID_NAME,
                'model': 'res.company',
                'res_id': company.id,
            })
            _logger.info('Se creó external id l10n_ve_evo.%s para la compañía %s', EXTERNAL_ID_NAME, company.name)
    except Exception:
        _logger.exception('No se pudo crear ir.model.data para la compañía %s', company.name)

    # 3) Intentar asignar company_ids/company_id a las cuentas sin compañía
    try:
        _assign_company_to_accounts(env, company)
        _logger.info('create_company_if_missing: asignación de compañías a cuentas finalizada sin errores críticos.')
    except Exception as exc:
        # Si detectamos un error de unicidad (IntegrityError) intentamos duplicar cuentas por compañía
        msg = str(exc).lower()
        if 'unique' in msg or 'duplicate' in msg or 'duplicate key' in msg:
            _logger.warning('create_company_if_missing: detectado posible error de unicidad en account.code. Intentando duplicar cuentas por compañía y reintentar asignación.')
            try:
                # Opcional: limitar duplicación a códigos que provienen de tu módulo
                # Si quieres limitar, pasa una lista de códigos concretos a duplicate_accounts_per_company
                duplicate_accounts_per_company(env)
                # Reintentar asignación después de duplicar
                try:
                    _assign_company_to_accounts(env, company)
                    _logger.info('create_company_if_missing: reintento de asignación tras duplicar cuentas completado.')
                except Exception:
                    _logger.exception('create_company_if_missing: fallo en reintento de asignación tras duplicar cuentas.')
            except Exception:
                _logger.exception('create_company_if_missing: error durante la duplicación de cuentas por compañía.')
        else:
            _logger.exception('create_company_if_missing: error no relacionado con unicidad al asignar compañías a cuentas: %s', exc)

    _logger.info('create_company_if_missing: finalizado.')
