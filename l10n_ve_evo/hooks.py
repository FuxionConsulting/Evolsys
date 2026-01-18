# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
from odoo.tools import convert
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'
ACCOUNT_XML = 'data/account_account_ve.xml'

# Mapeo account_type -> xmlid de user_type
_ACCOUNT_TYPE_MAP = {
    'asset_current': 'account.data_account_type_current_assets',
    'asset_receivable': 'account.data_account_type_receivable',
    'liability_payable': 'account.data_account_type_payable',
    'equity': 'account.data_account_type_equity',
    'income': 'account.data_account_type_revenue',
    'expense': 'account.data_account_type_expenses',
    'expense_direct_cost': 'account.data_account_type_direct_costs',
    'income_other': 'account.data_account_type_other_income',
}

def _get_company(env):
    return env['res.company'].search(['|', ('name', '=', COMPANY_NAME), ('vat', '=', COMPANY_VAT)], limit=1)

def _parse_account_xml_for_types(env, relative_xml_path):
    """
    Lee el XML relativo al módulo y devuelve un dict:
      { 'module.xml_id': {'code': '110000', 'name': 'Caja', 'account_type': 'asset_current'}, ... }
    Solo extrae records <record model="account.account"> y su campo <field name="account_type"> si existe.
    """
    result = {}
    try:
        module_path = env['ir.module.module']._get_module_path(MODULE)
        full_path = module_path and (module_path + '/' + relative_xml_path)
        if not full_path:
            _logger.warning("[%s] No se pudo resolver ruta del addon para %s", MODULE, relative_xml_path)
            return result
        tree = ET.parse(full_path)
        root = tree.getroot()
        # buscar todos los <record> del XML
        for rec in root.findall('.//record'):
            model = rec.get('model')
            rec_id = rec.get('id')
            if model != 'account.account' or not rec_id:
                continue
            # extraer campos
            code = None
            name = None
            account_type = None
            for field in rec.findall('field'):
                fname = field.get('name')
                # el texto puede estar en field.text o en subelementos (eval/ref)
                if fname == 'code':
                    code = (field.text or '').strip()
                elif fname == 'name':
                    name = (field.text or '').strip()
                elif fname == 'account_type':
                    # account_type suele ser texto simple en tu XML
                    account_type = (field.text or '').strip()
            # construir xmlid completo: module.rec_id
            xmlid = f"{MODULE}.{rec_id}"
            result[xmlid] = {'code': code, 'name': name, 'account_type': account_type}
    except Exception as e:
        _logger.exception("[%s] Error parseando XML %s: %s", MODULE, relative_xml_path, e)
    return result

def _resolve_user_type(env, account_type_key):
    xmlid = _ACCOUNT_TYPE_MAP.get(account_type_key)
    if not xmlid:
        return None
    try:
        return env.ref(xmlid, raise_if_not_found=False)
    except Exception:
        return None

def _assign_company_and_user_type(env, company, xmlid_to_meta):
    """
    Para cada xmlid importado, busca el registro real (account.account) y:
      - asigna company_id o company_ids
      - asigna user_type_id según account_type extraído del XML
    """
    Imd = env['ir.model.data']
    Account = env['account.account']
    linked = 0
    updated_ut = 0
    for xmlid, meta in xmlid_to_meta.items():
        try:
            # resolver external id a (module, name) -> ir.model.data
            module, name = xmlid.split('.', 1)
            imd = Imd.search([('module', '=', module), ('name', '=', name), ('model', '=', 'account.account')], limit=1)
            if not imd:
                # no hay external id creado (posible si la importación falló o el record no tenía id)
                continue
            acc = Account.browse(imd.res_id)
            if not acc.exists():
                continue
            # asignar company
            if 'company_ids' in acc._fields:
                if company.id not in (acc.company_ids.ids or []):
                    acc.write({'company_ids': [(4, company.id)]})
                    linked += 1
            elif 'company_id' in acc._fields:
                if not acc.company_id or acc.company_id.id != company.id:
                    acc.write({'company_id': company.id})
                    linked += 1
            # asignar user_type_id si account_type presente en XML
            acct_type = meta.get('account_type')
            if acct_type:
                ut = _resolve_user_type(env, acct_type)
                if ut and (not acc.user_type_id or acc.user_type_id.id != ut.id):
                    try:
                        acc.write({'user_type_id': ut.id})
                        updated_ut += 1
                    except Exception:
                        _logger.exception("[%s] No se pudo escribir user_type_id en cuenta %s", MODULE, acc.id)
        except Exception:
            _logger.exception("[%s] Error procesando xmlid %s", MODULE, xmlid)
            continue
    _logger.info("[%s] Cuentas vinculadas a company: %s; user_type asignados: %s", MODULE, linked, updated_ut)

def post_init_hook(cr, registry):
    """
    post_init_hook que:
      1) parsea account_account_ve.xml para extraer account_type por xmlid
      2) importa el XML con convert.convert_file
      3) vincula las cuentas importadas a la compañía y asigna user_type_id según account_type
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("[%s] post_init_hook (B) inicio: importar y mapear cuentas", MODULE)
    try:
        company = _get_company(env)
        if not company:
            _logger.warning("[%s] No se encontró la compañía objetivo; abortando importación de cuentas", MODULE)
            return

        # 1) parsear XML y obtener metadata por xmlid
        xml_meta = _parse_account_xml_for_types(env, ACCOUNT_XML)
        if not xml_meta:
            _logger.info("[%s] No se detectaron records account.account en %s o no se pudo parsear", MODULE, ACCOUNT_XML)

        # 2) importar el XML (convertir)
        try:
            _logger.info("[%s] Importando %s via convert.convert_file", MODULE, ACCOUNT_XML)
            convert.convert_file(cr, MODULE, ACCOUNT_XML, {}, 'init', noupdate=False)
            _logger.info("[%s] Importación de %s completada", MODULE, ACCOUNT_XML)
        except Exception as e:
            _logger.exception("[%s] Error importando %s: %s", MODULE, ACCOUNT_XML, e)
            # continuamos: intentaremos vincular y asignar lo que exista

        # 3) asignar company y user_type a los registros importados
        _assign_company_and_user_type(env, company, xml_meta)

        _logger.info("[%s] post_init_hook (B) finalizado", MODULE)
    except Exception as e:
        _logger.exception("[%s] Error general en post_init_hook (B): %s", MODULE, e)
