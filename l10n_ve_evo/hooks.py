# hooks.py
# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_ve_evo'
COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'  # reemplaza por el RIF real
EXTERNAL_ID_NAME = 'company_main'  # opcional

# Definición de cuentas a crear por compañía
ACCOUNTS_TO_CREATE = [
    {'xml_id': 'l10n_ve_evo_110000', 'name': 'Caja y Bancos VEB', 'code': '110000', 'account_type': 'asset_current', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_111000', 'name': 'Caja y Bancos USD', 'code': '111000', 'account_type': 'asset_current', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_114000', 'name': 'Cuenta Puente', 'code': '114000', 'account_type': 'asset_current', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_115000', 'name': 'Anticipos (Activo)', 'code': '115000', 'account_type': 'asset_prepayments', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_130000', 'name': 'Cuentas por Cobrar - Clientes', 'code': '130000', 'account_type': 'asset_receivable', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_140000', 'name': 'Inventario de Mercancías', 'code': '140000', 'account_type': 'asset_current', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_151100', 'name': 'Propiedad Planta y Equipo', 'code': '151100', 'account_type': 'asset_fixed', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_159000', 'name': 'Depreciación Acumulada', 'code': '159000', 'account_type': 'asset_non_current', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_210000', 'name': 'Cuentas por Pagar - Proveedores', 'code': '210000', 'account_type': 'liability_payable', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_214000', 'name': 'IVA por Pagar (Ventas)', 'code': '214000', 'account_type': 'liability_current', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_215000', 'name': 'IVA Crédito Fiscal (Compras)', 'code': '215000', 'account_type': 'liability_current', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_270000', 'name': 'Cuenta de Suspenso', 'code': '270000', 'account_type': 'liability_current', 'reconcile': True},
    {'xml_id': 'l10n_ve_evo_290000', 'name': 'Impuestos Retenidos por Pagar', 'code': '290000', 'account_type': 'liability_current', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_310000', 'name': 'Capital Social', 'code': '310000', 'account_type': 'equity', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_390000', 'name': 'Resultado del Ejercicio Anterior', 'code': '390000', 'account_type': 'equity', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_410000', 'name': 'Venta de Bienes', 'code': '410000', 'account_type': 'income', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_420000', 'name': 'Venta de Servicios', 'code': '420000', 'account_type': 'income', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_490000', 'name': 'Descuentos en Ventas', 'code': '490000', 'account_type': 'income_other', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_511000', 'name': 'Costo de Venta', 'code': '511000', 'account_type': 'expense_direct_cost', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_601000', 'name': 'Gastos de Personal', 'code': '601000', 'account_type': 'expense', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_611100', 'name': 'Gastos Administrativos', 'code': '611100', 'account_type': 'expense', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_621000', 'name': 'Gastos de Depreciación', 'code': '621000', 'account_type': 'expense_depreciation', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_700000', 'name': 'Ingresos varios', 'code': '700000', 'account_type': 'income_other', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_710000', 'name': 'Intereses Ganados', 'code': '710000', 'account_type': 'income_other', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_720000', 'name': 'Pérdida por Venta de Activos', 'code': '720000', 'account_type': 'expense_other', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_730000', 'name': 'Diferencia Cambiaria Ganada', 'code': '730000', 'account_type': 'income_other', 'reconcile': False},
    {'xml_id': 'l10n_ve_evo_740000', 'name': 'Diferencia Cambiaria Perdida', 'code': '740000', 'account_type': 'expense_other', 'reconcile': False},
]

# -------------------------
# Utilidades para cuentas
# -------------------------
def _create_or_update_accounts_per_company(env, companies):
    Account = env['account.account'].sudo()
    Imd = env['ir.model.data'].sudo()
    created = 0
    updated = 0

    for acc_def in ACCOUNTS_TO_CREATE:
        xml_id = acc_def.get('xml_id')
        vals_base = {
            'name': acc_def['name'],
            'code': acc_def['code'],
            'account_type': acc_def.get('account_type'),
            'reconcile': acc_def.get('reconcile', False),
        }

        for comp in companies:
            existing = Account.search([('code', '=', vals_base['code']), ('company_ids', 'in', comp.id)], limit=1)
            if existing:
                try:
                    existing.write(vals_base)
                    updated += 1
                    if xml_id:
                        name_for_imd = f"{xml_id}_{comp.id}"
                        if not Imd.search([('module', '=', MODULE), ('name', '=', name_for_imd)], limit=1):
                            Imd.create({'module': MODULE, 'name': name_for_imd, 'model': 'account.account', 'res_id': existing.id})
                except Exception:
                    _logger.exception('Error actualizando cuenta %s para compañía %s', vals_base['code'], comp.name)
            else:
                vals = vals_base.copy()
                vals.update({'company_ids': [(6, 0, [comp.id])], 'company_id': comp.id})
                try:
                    new_acc = Account.create(vals)
                    created += 1
                    if xml_id:
                        name_for_imd = f"{xml_id}_{comp.id}"
                        Imd.create({'module': MODULE, 'name': name_for_imd, 'model': 'account.account', 'res_id': new_acc.id})
                except Exception:
                    _logger.exception('Error creando cuenta %s para compañía %s', vals_base['code'], comp.name)

    _logger.info('_create_or_update_accounts_per_company: creadas=%d actualizadas=%d', created, updated)
    return created, updated

def duplicate_accounts_per_company(env, codes_to_duplicate=None):
    Account = env['account.account'].sudo()
    Company = env['res.company'].sudo()
    companies = Company.search([])
    if not companies:
        _logger.info('duplicate_accounts_per_company: no hay compañías registradas.')
        return

    accounts = Account.search([]) if not codes_to_duplicate else Account.search([('code', 'in', codes_to_duplicate)])
    _logger.info('duplicate_accounts_per_company: procesando %d cuentas para %d compañías', len(accounts), len(companies))

    for acc in accounts:
        assigned_company_ids = set(acc.company_ids.ids)
        for comp in companies:
            if comp.id in assigned_company_ids:
                continue
            try:
                vals = acc.copy_data()[0]
                vals.update({'company_ids': [(6, 0, [comp.id])], 'company_id': comp.id})
                Account.create(vals)
                _logger.info('Duplicada cuenta code=%s para compañía %s', acc.code, comp.name)
            except Exception:
                _logger.exception('Error duplicando cuenta %s para compañía %s', acc.code, comp.name)

# -------------------------
# Utilidades para impuestos
# -------------------------
def _ensure_tax_group(env, xml_name, group_name):
    Imd = env['ir.model.data'].sudo()
    TaxGroup = env['account.tax.group'].sudo()
    rec = env.ref(f'{MODULE}.{xml_name}', raise_if_not_found=False)
    if rec:
        return rec
    existing = TaxGroup.search([('name', '=', group_name), ('country_id.code', '=', 'VE')], limit=1)
    if existing:
        if not Imd.search([('module', '=', MODULE), ('name', '=', xml_name)], limit=1):
            Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax.group', 'res_id': existing.id})
        return existing
    try:
        grp = TaxGroup.create({'name': group_name, 'country_id': env.ref('base.ve').id})
        Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax.group', 'res_id': grp.id})
        _logger.info('Creado tax.group %s (xml_id=%s)', group_name, xml_name)
        return grp
    except Exception:
        _logger.exception('Error creando tax.group %s', group_name)
        return None

def _ensure_tax(env, xml_name, tax_vals):
    Imd = env['ir.model.data'].sudo()
    Tax = env['account.tax'].sudo()
    rec = env.ref(f'{MODULE}.{xml_name}', raise_if_not_found=False)
    if rec:
        return rec
    existing = Tax.search([('name', '=', tax_vals.get('name')), ('type_tax_use', '=', tax_vals.get('type_tax_use'))], limit=1)
    if existing:
        if not Imd.search([('module', '=', MODULE), ('name', '=', xml_name)], limit=1):
            Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax', 'res_id': existing.id})
        return existing
    try:
        vals = tax_vals.copy()
        if isinstance(vals.get('tax_group_id'), str):
            vals['tax_group_id'] = env.ref(f'{MODULE}.{vals["tax_group_id"]}').id
        tax = Tax.create(vals)
        Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax', 'res_id': tax.id})
        _logger.info('Creado account.tax %s (xml_id=%s)', vals.get('name'), xml_name)
        return tax
    except Exception:
        _logger.exception('Error creando account.tax %s', tax_vals.get('name'))
        return None

def _ensure_repartition_line(env, xml_name, repart_vals):
    Imd = env['ir.model.data'].sudo()
    Repart = env['account.tax.repartition.line'].sudo()
    rec = env.ref(f'{MODULE}.{xml_name}', raise_if_not_found=False)
    if rec:
        return rec
    domain = [
        ('tax_id', '=', repart_vals['tax_id']),
        ('repartition_type', '=', repart_vals['repartition_type']),
        ('document_type', '=', repart_vals['document_type']),
        ('factor_percent', '=', repart_vals.get('factor_percent', 0))
    ]
    if repart_vals.get('account_id'):
        domain.append(('account_id', '=', repart_vals['account_id']))
    existing = Repart.search(domain, limit=1)
    if existing:
        if not Imd.search([('module', '=', MODULE), ('name', '=', xml_name)], limit=1):
            Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax.repartition.line', 'res_id': existing.id})
        return existing
    try:
        rl = Repart.create(repart_vals)
        Imd.create({'module': MODULE, 'name': xml_name, 'model': 'account.tax.repartition.line', 'res_id': rl.id})
        _logger.info('Creada repartition.line %s', xml_name)
        return rl
    except Exception:
        _logger.exception('Error creando repartition.line %s', xml_name)
        return None

def create_taxes_and_repartition_lines(env):
    env = env.sudo()
    grp_16 = _ensure_tax_group(env, 'l10n_ve_evo_tax_group_iva_16', 'IVA 16% (General)')
    grp_8  = _ensure_tax_group(env, 'l10n_ve_evo_tax_group_iva_8', 'IVA 8% (Reducido)')
    grp_ex = _ensure_tax_group(env, 'l10n_ve_evo_tax_group_exento', 'Exento 0%')

    taxes_def = [
        ('l10n_ve_evo_iva_sale_16', {
            'name': 'IVA- Venta 16%',
            'amount': 16.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': 'l10n_ve_evo_tax_group_iva_16',
            'country_id': env.ref('base.ve').id,
            'active': True,
        }),
        ('l10n_ve_evo_iva_purchase_16', {
            'name': 'IVA- Compra 16%',
            'amount': 16.0,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
            'tax_group_id': 'l10n_ve_evo_tax_group_iva_16',
            'country_id': env.ref('base.ve').id,
            'active': True,
        }),
        ('l10n_ve_evo_iva_sale_8', {
            'name': 'IVA- Venta 8%',
            'amount': 8.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'tax_group_id': 'l10n_ve_evo_tax_group_iva_8',
            'country_id': env.ref('base.ve').id,
            'active': True,
        }),
        ('l10n_ve_evo_iva_sale_exento', {
            'name': 'Exento- (Venta)',
            'amount': 0.0,
            'amount_type': 'fixed',
            'type_tax_use': 'sale',
            'tax_group_id': 'l10n_ve_evo_tax_group_exento',
            'country_id': env.ref('base.ve').id,
            'active': True,
        }),
    ]

    created_taxes = {}
    for xml_name, vals in taxes_def:
        tax = _ensure_tax(env, xml_name, vals)
        if tax:
            created_taxes[xml_name] = tax.id

    Account = env['account.account'].sudo()

    def _get_account_id_by_code(code):
        acc = Account.search([('code', '=', code)], limit=1)
        if acc:
            return acc.id
        _logger.warning('create_taxes_and_repartition_lines: no se encontró cuenta con code %s; saltando', code)
        return None

    repart_defs = [
        ('l10n_ve_evo_iva_sale_16_invoice_base', 'l10n_ve_evo_iva_sale_16', 'base', 'invoice', None, 100, False),
        ('l10n_ve_evo_iva_sale_16_invoice_tax', 'l10n_ve_evo_iva_sale_16', 'tax', 'invoice', '214000', 100, True),
        ('l10n_ve_evo_iva_sale_16_refund_base', 'l10n_ve_evo_iva_sale_16', 'base', 'refund', None, 100, False),
        ('l10n_ve_evo_iva_sale_16_refund_tax', 'l10n_ve_evo_iva_sale_16', 'tax', 'refund', '214000', 100, True),

        ('l10n_ve_evo_iva_purchase_16_invoice_base', 'l10n_ve_evo_iva_purchase_16', 'base', 'invoice', None, 100, False),
        ('l10n_ve_evo_iva_purchase_16_invoice_tax', 'l10n_ve_evo_iva_purchase_16', 'tax', 'invoice', '215000', 100, True),
        ('l10n_ve_evo_iva_purchase_16_refund_base', 'l10n_ve_evo_iva_purchase_16', 'base', 'refund', None, 100, False),
        ('l10n_ve_evo_iva_purchase_16_refund_tax', 'l10n_ve_evo_iva_purchase_16', 'tax', 'refund', '215000', 100, True),

        ('l10n_ve_evo_iva_sale_8_invoice_base', 'l10n_ve_evo_iva_sale_8', 'base', 'invoice', None, 100, False),
        ('l10n_ve_evo_iva_sale_8_invoice_tax', 'l10n_ve_evo_iva_sale_8', 'tax', 'invoice', '214000', 100, True),
        ('l10n_ve_evo_iva_sale_8_refund_base', 'l10n_ve_evo_iva_sale_8', 'base', 'refund', None, 100, False),
        ('l10n_ve_evo_iva_sale_8_refund_tax', 'l10n_ve_evo_iva_sale_8', 'tax', 'refund', '214000', 100, True),

        ('l10n_ve_evo_iva_sale_exento_invoice_base', 'l10n_ve_evo_iva_sale_exento', 'base', 'invoice', None, 100, False),
        ('l10n_ve_evo_iva_sale_exento_invoice_tax', 'l10n_ve_evo_iva_sale_exento', 'tax', 'invoice', None, 0, False),
        ('l10n_ve_evo_iva_sale_exento_refund_base', 'l10n_ve_evo_iva_sale_exento', 'base', 'refund', None, 100, False),
        ('l10n_ve_evo_iva_sale_exento_refund_tax', 'l10n_ve_evo_iva_sale_exento', 'tax', 'refund', None, 0, False),
    ]

    for xml_name, tax_xml, repart_type, doc_type, acc_code, factor, use_in_closing in repart_defs:
        tax_id = created_taxes.get(tax_xml)
        if not tax_id:
            _logger.warning('No se encontró impuesto %s para crear %s', tax_xml, xml_name)
            continue
        repart_vals = {
            'tax_id': tax_id,
            'repartition_type': repart_type,
            'document_type': doc_type,
            'factor_percent': factor,
            'use_in_tax_closing': bool(use_in_closing),
        }
        if acc_code:
            acc_id = _get_account_id_by_code(acc_code)
            if not acc_id:
                continue
            repart_vals['account_id'] = acc_id
        _ensure_repartition_line(env, xml_name, repart_vals)

    _logger.info('create_taxes_and_repartition_lines: finalizado.')

# -------------------------
# Hook principal
# -------------------------
def create_company_if_missing(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env['res.company'].sudo()
    Partner = env['res.partner'].sudo()
    Imd = env['ir.model.data'].sudo()

    # 1) Obtener o crear compañía por nombre
    company = Company.search([('name', '=', COMPANY_NAME)], limit=1)
    if company:
        _logger.info('create_company_if_missing: la compañía ya existe (id=%s).', company.id)
        partner = company.partner_id
        if partner and not partner.vat:
            try:
                partner.write({'vat': COMPANY_VAT})
                _logger.info('create_company_if_missing: actualizado vat del partner.')
            except Exception:
                _logger.exception('Error actualizando vat del partner.')
        elif not partner:
            try:
                p = Partner.create({
                    'name': COMPANY_NAME,
                    'is_company': True,
                    'vat': COMPANY_VAT,
                    'company_type': 'company',
                })
                company.write({'partner_id': p.id})
                _logger.info('create_company_if_missing: partner creado y asignado.')
            except Exception:
                _logger.exception('Error creando partner para la compañía existente.')
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
            _logger.exception('Error creando partner/company.')
            return

    # 2) Crear external id para la compañía (opcional)
    try:
        existing = Imd.search([('module', '=', MODULE), ('name', '=', EXTERNAL_ID_NAME), ('model', '=', 'res.company')], limit=1)
        if not existing:
            Imd.create({
                'module': MODULE,
                'name': EXTERNAL_ID_NAME,
                'model': 'res.company',
                'res_id': company.id,
            })
            _logger.info('Se creó external id %s.%s para la compañía %s', MODULE, EXTERNAL_ID_NAME, company.name)
    except Exception:
        _logger.exception('No se pudo crear ir.model.data para la compañía %s', company.name)

    # 3) Crear/actualizar cuentas por compañía
    try:
        companies = Company.search([])  # todas las compañías existentes
        if not companies:
            _logger.warning('No hay compañías registradas; no se crearán cuentas.')
            return
        _create_or_update_accounts_per_company(env, companies)
        _logger.info('create_company_if_missing: creación/actualización de cuentas por compañía finalizada.')
    except Exception:
        _logger.exception('create_company_if_missing: error creando/actualizando cuentas por compañía.')

    # 4) Crear impuestos y repartition lines (usa las cuentas ya creadas)
    try:
        create_taxes_and_repartition_lines(env)
    except Exception:
        _logger.exception('create_company_if_missing: error creando impuestos/repartition lines.')

    _logger.info('create_company_if_missing: finalizado.')
