# hooks.py
# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'
EXTERNAL_ID_NAME = 'company_main'


# -------------------------
# Helpers básicos
# -------------------------
def _ensure_company(env):
    Company = env['res.company']
    Imd = env['ir.model.data']

    company = Company.search(['|', ('name', '=', COMPANY_NAME), ('vat', '=', COMPANY_VAT)], limit=1)
    if company:
        _logger.info("[%s] Compañía existente encontrada: %s (%s)", MODULE, company.name, company.id)
    else:
        _logger.info("[%s] Creando compañía %s", MODULE, COMPANY_NAME)
        country = env.ref('base.ve', raise_if_not_found=False)
        ved = env.ref('base.VED', raise_if_not_found=False)
        ves = env.ref('base.VES', raise_if_not_found=False)
        currency = ved or ves or None
        vals = {'name': COMPANY_NAME, 'vat': COMPANY_VAT}
        if country:
            vals['country_id'] = country.id
        if currency:
            vals['currency_id'] = currency.id
        company = Company.create(vals)
        _logger.info("[%s] Compañía creada: %s (%s)", MODULE, company.name, company.id)

    imd_rec = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME), ('model', '=', 'res.company')], limit=1)
    if not imd_rec:
        Imd.create({'module': MODULE, 'name': EXTERNAL_ID_NAME, 'model': 'res.company', 'res_id': company.id, 'noupdate': True})
        _logger.info("[%s] External ID creado para la compañía: %s", MODULE, EXTERNAL_ID_NAME)
    else:
        _logger.info("[%s] External ID ya existente para la compañía: %s", MODULE, EXTERNAL_ID_NAME)

    return company


def _assign_company_to_record(record, company):
    try:
        if 'company_ids' in record._fields:
            current = record.company_ids.ids or []
            if company.id not in current:
                record.write({'company_ids': [(4, company.id)]})
                return True
            return False
        elif 'company_id' in record._fields:
            if not record.company_id or record.company_id.id != company.id:
                record.write({'company_id': company.id})
                return True
            return False
        else:
            return False
    except Exception:
        _logger.exception("[%s] Error asignando company a %s:%s", MODULE, record._name, record.id)
        return False


def _assign_orphans(env, company):
    """
    Vincula registros importados por los XML listados en data a la compañía objetivo.
    Busca registros sin company_id o sin company_ids y que tengan external id del módulo.
    """
    models = [
        ('account.tax', 'Impuestos'),
        ('account.journal', 'Diarios'),
        ('account.fiscal.position', 'Posiciones Fiscales'),
        ('account.group', 'Grupos de Cuentas'),
        ('account.account', 'Cuentas')
    ]
    for model_name, label in models:
        try:
            Model = env[model_name]
            domain = ['|', ('company_id', '=', False), ('company_ids', '=', False)]
            records = Model.search(domain)
            linked = 0
            for rec in records:
                try:
                    xml_id_dict = rec.get_external_id()
                    xml_id = xml_id_dict.get(rec.id)
                    if xml_id and xml_id.startswith(MODULE):
                        if _assign_company_to_record(rec, company):
                            linked += 1
                except Exception:
                    continue
            _logger.info("[%s] %s: vinculados %s registros a la compañía %s", MODULE, label, linked, company.id)
        except Exception:
            _logger.exception("[%s] Error procesando modelo %s", MODULE, model_name)
            continue


def _force_activation(env, company):
    """Activa impuestos y posiciones fiscales para la compañía."""
    try:
        taxes = env['account.tax'].search([('company_id', '=', company.id)])
        if taxes:
            taxes.write({'active': True})
        positions = env['account.fiscal.position'].search([('company_id', '=', company.id)])
        if positions:
            positions.write({'active': True})
        _logger.info("[%s] Activados impuestos y posiciones fiscales para company %s", MODULE, company.id)
    except Exception:
        _logger.exception("[%s] Error forzando activación para company %s", MODULE, company.id)


# -------------------------
# Resolución de tipos de cuenta
# -------------------------
def _resolve_user_type(env, account_type_key):
    """
    Mapear account_type (string usado en los XML) a user_type record.
    Devuelve record o None.
    """
    if not account_type_key:
        return None
    mapping = {
        'asset_current': 'account.data_account_type_current_assets',
        'asset_receivable': 'account.data_account_type_receivable',
        'liability_payable': 'account.data_account_type_payable',
        'equity': 'account.data_account_type_equity',
        'income': 'account.data_account_type_revenue',
        'expense': 'account.data_account_type_expenses',
        'expense_direct_cost': 'account.data_account_type_direct_costs',
        'income_other': 'account.data_account_type_other_income',
    }
    xmlid = mapping.get(account_type_key)
    if not xmlid:
        return None
    try:
        return env.ref(xmlid, raise_if_not_found=False)
    except Exception:
        return None


def _ensure_account_user_type_for_existing(env, account):
    """
    Si una cuenta existente no tiene user_type_id, intenta inferirlo por prefijo de código.
    Heurístico simple para evitar inconsistencias.
    """
    try:
        if not account.user_type_id:
            code = (account.code or '')[:1]
            if code == '1':
                ut = _resolve_user_type(env, 'asset_current')
            elif code == '2':
                ut = _resolve_user_type(env, 'liability_payable')
            elif code == '4':
                ut = _resolve_user_type(env, 'income')
            elif code == '6':
                ut = _resolve_user_type(env, 'expense')
            else:
                ut = None
            if ut:
                account.write({'user_type_id': ut.id})
                _logger.info("[%s] Asignado user_type_id a cuenta %s (%s)", MODULE, account.code, account.id)
    except Exception:
        _logger.exception("[%s] Error asignando user_type a cuenta %s", MODULE, account.id)


def _assign_journals_company(env, company):
    """
    Asegura que los journals importados estén vinculados a la compañía.
    """
    try:
        journals = env['account.journal'].search(['|', ('company_id', '=', False), ('company_ids', '=', False)])
        linked = 0
        for j in journals:
            try:
                xml_id = j.get_external_id().get(j.id)
                if xml_id and xml_id.startswith(MODULE):
                    if _assign_company_to_record(j, company):
                        linked += 1
            except Exception:
                continue
        _logger.info("[%s] Journals vinculados a company %s: %s", MODULE, company.id, linked)
    except Exception:
        _logger.exception("[%s] Error vinculando journals", MODULE)


# -------------------------
# Mapeo automático de plantillas
# -------------------------
def _map_account_templates(env, company):
    """
    Mapear account.account.template -> account.account.
    Busca por code (preferible) o por name; crea cuenta básica si no existe.
    Asigna user_type_id usando _resolve_user_type cuando sea posible.
    """
    try:
        templates = env['account.account.template'].search([])
        Account = env['account.account']
        created = 0
        linked = 0
        for t in templates:
            code = t.code or False
            name = t.name or ''
            if code:
                existing = Account.search([('code', '=', code)], limit=1)
            else:
                existing = Account.search([('name', '=', name)], limit=1)

            if existing:
                if _assign_company_to_record(existing, company):
                    linked += 1
                # asegurar user_type si falta
                _ensure_account_user_type_for_existing(env, existing)
                continue

            vals = {
                'name': name,
                'code': code,
                'company_ids': [(6, 0, [company.id])],
                'reconcile': bool(t.reconcile),
                'deprecated': bool(t.deprecated),
            }
            # intentar resolver user_type desde la plantilla si existe account_type
            # algunas plantillas pueden no tener account_type; en ese caso se intenta inferir por código
            if hasattr(t, 'account_type') and t.account_type:
                ut = _resolve_user_type(env, t.account_type)
                if ut:
                    vals['user_type_id'] = ut.id
            try:
                Account.create(vals)
                created += 1
            except Exception as e:
                _logger.exception("[%s] Error creando cuenta desde template %s: %s", MODULE, code or name, e)
        _logger.info("[%s] Mapeo cuentas: creadas=%s, vinculadas=%s para company %s", MODULE, created, linked, company.id)
    except Exception:
        _logger.exception("[%s] Error en _map_account_templates", MODULE)


def _map_tax_templates(env, company):
    """
    Mapear account.tax.template -> account.tax.
    No crea impuestos nuevos por defecto; intenta vincular impuestos existentes por nombre o amount.
    """
    try:
        t_templates = env['account.tax.template'].search([])
        Tax = env['account.tax']
        linked = 0
        not_found = 0
        for tt in t_templates:
            name = tt.name or ''
            candidates = Tax.search([('name', '=', name)])
            if not candidates:
                if hasattr(tt, 'amount') and tt.amount is not None:
                    candidates = Tax.search([('amount', '=', tt.amount)])
            if candidates:
                chosen = None
                for c in candidates:
                    if c.company_id and c.company_id.id == company.id:
                        chosen = c
                        break
                    if company.id in (c.company_ids.ids or []):
                        chosen = c
                        break
                if not chosen:
                    chosen = candidates[0]
                if _assign_company_to_record(chosen, company):
                    linked += 1
                continue
            else:
                not_found += 1
                continue
        _logger.info("[%s] Mapeo impuestos: vinculados=%s, no encontrados=%s para company %s", MODULE, linked, not_found, company.id)
    except Exception:
        _logger.exception("[%s] Error en _map_tax_templates", MODULE)


# -------------------------
# Asegurar plan de cuentas por company (desde templates)
# -------------------------
def _unstale_chart_for_companies(env, chart_xmlid='l10n_ve_evo.ve_chart_template'):
    """
    Asegura que las cuentas definidas en account.account.template para el chart_template
    existan y estén asociadas a cada company mediante company_ids.
    """
    try:
        chart_template = env.ref(chart_xmlid, raise_if_not_found=False)
        if not chart_template:
            _logger.info("[%s] Chart template %s no encontrado. Omitiendo unstale.", MODULE, chart_xmlid)
            return

        acct_templates = env['account.account.template'].search([('chart_template_id', '=', chart_template.id)])
        if not acct_templates:
            _logger.info("[%s] No hay account.account.template para el chart %s.", MODULE, chart_template.id)
            return

        Account = env['account.account']
        companies = env['res.company'].search([])
        for company in companies:
            created = 0
            linked = 0
            for at in acct_templates:
                code = at.code or False
                name = at.name or 'Sin nombre'
                existing_for_company = Account.search([('code', '=', code), ('company_ids', 'in', company.id)], limit=1)
                if existing_for_company:
                    continue
                existing_any = Account.search([('code', '=', code)], limit=1)
                if existing_any:
                    if company.id not in existing_any.company_ids.ids:
                        existing_any.write({'company_ids': [(4, company.id)]})
                        linked += 1
                    continue
                vals = {
                    'name': name,
                    'code': code,
                    'company_ids': [(6, 0, [company.id])],
                    'reconcile': bool(at.reconcile),
                    'deprecated': bool(at.deprecated),
                }
                # intentar resolver user_type desde plantilla
                if at.user_type_id:
                    vals['user_type_id'] = at.user_type_id.id
                else:
                    # si plantilla no tiene user_type, intentar por account_type si existe
                    if hasattr(at, 'account_type') and at.account_type:
                        ut = _resolve_user_type(env, at.account_type)
                        if ut:
                            vals['user_type_id'] = ut.id
                try:
                    Account.create(vals)
                    created += 1
                except Exception as e:
                    _logger.exception("[%s] Error creando cuenta %s para company %s: %s", MODULE, code, company.id, e)
            _logger.info("[%s] Empresa %s (%s): cuentas creadas=%s, vinculadas=%s.", MODULE, company.name, company.id, created, linked)
    except Exception:
        _logger.exception("[%s] Error en _unstale_chart_for_companies", MODULE)


# -------------------------
# Entry point
# -------------------------
def post_init_hook(cr, registry):
    """
    Hook a declarar en __manifest__ como 'post_init_hook': 'post_init_hook'
    Flujo:
      1) asegura/crea la compañía objetivo
      2) vincula registros huérfanos importados por los XML en data
      3) activa impuestos y posiciones fiscales
      4) mapea plantillas (cuentas/impuestos) a registros reales
      5) asegura plan de cuentas por empresa (crea o vincula cuentas desde templates)
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("[%s] Iniciando post_init_hook (Opción A: XML en manifest)", MODULE)
    try:
        company = _ensure_company(env)

        # Vincular registros importados por los XML (no recargamos XML aquí)
        _assign_orphans(env, company)

        # Asegurar journals
        _assign_journals_company(env, company)

        # Activar impuestos y posiciones
        _force_activation(env, company)

        # Mapeo automático de plantillas a registros reales
        _map_account_templates(env, company)
        _map_tax_templates(env, company)

        # Asegurar plan de cuentas por empresa (crea o vincula cuentas desde templates si aplica)
        _unstale_chart_for_companies(env, chart_xmlid='l10n_ve_evo.ve_chart_template')

        _logger.info("[%s] post_init_hook finalizado correctamente", MODULE)
    except Exception as e:
        _logger.exception("[%s] Error en post_init_hook: %s", MODULE, e)
