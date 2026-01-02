# -*- coding: utf-8 -*-
# l10n__ve_evo hooks.py (versión ajustada para Odoo 19)
# Cambios principales:
# - Importa api y usa la firma correcta para post_init_hook (cr, registry)
# - _post_init_assign_template ahora recibe env y crea/registro el account.chart.template con ir.model.data
# - Creación segura de ir.model.data para journals/accounts/templates creados por el módulo
# - Uso de sudo() donde corresponde y logging robusto

from odoo import SUPERUSER_ID, api
import logging
import re

_logger = logging.getLogger(__name__)


def _resolve_xmlid(env, xmlid_or_name, module='l10n__ve_evo'):
    if not xmlid_or_name:
        return None
    if '.' in xmlid_or_name:
        return env.ref(xmlid_or_name, raise_if_not_found=False)
    full = f"{module}.{xmlid_or_name}"
    rec = env.ref(full, raise_if_not_found=False)
    if rec:
        return rec
    imd = env['ir.model.data'].sudo().search([('module', '=', module), ('name', '=', xmlid_or_name)], limit=1)
    if imd:
        try:
            return env[imd.model].browse(imd.res_id)
        except Exception:
            return None
    return None


def _ensure_journal_by_xmlname(env, xmlname, module='l10n__ve_evo', name=None, code=None):
    Journal = env['account.journal'].sudo()
    rec = _resolve_xmlid(env, xmlname, module=module)
    if rec:
        return rec
    domain = []
    if code:
        domain.append(('code', '=', code))
    if name:
        domain.append(('name', '=', name))
    journal = Journal.search(domain, limit=1) if domain else Journal.search([], limit=1)
    if journal:
        imd = env['ir.model.data'].sudo().search([('module', '=', module), ('name', '=', xmlname), ('model', '=', 'account.journal')], limit=1)
        if not imd:
            env['ir.model.data'].sudo().create({'module': module, 'name': xmlname, 'model': 'account.journal', 'res_id': journal.id})
            _logger.info("[l10n__ve_evo] Registrado ir.model.data para journal existente %s -> %s", xmlname, journal.id)
        return journal
    vals = {'name': name or xmlname.replace('_', ' ').title(), 'code': code or (xmlname[:6].upper()), 'type': 'general'}
    if 'company_id' in Journal._fields:
        try:
            vals['company_id'] = env.company.sudo().id
        except Exception:
            pass
    try:
        j = Journal.create(vals)
        env['ir.model.data'].sudo().create({'module': module, 'name': xmlname, 'model': 'account.journal', 'res_id': j.id})
        _logger.info("[l10n__ve_evo] Creado y registrado journal %s -> %s", xmlname, j.id)
        return j
    except Exception:
        _logger.exception("[l10n__ve_evo] No se pudo crear journal %s", xmlname)
        return None


def _find_account_type_record(env, account_type_code):
    AccountType = env['account.account.type'].sudo()
    candidates = [account_type_code, account_type_code.replace('_', ' ').title()] if account_type_code else []
    for c in candidates:
        rec = AccountType.search([('name', 'ilike', c)], limit=1)
        if rec:
            return rec
    if account_type_code and 'receivable' in account_type_code:
        return AccountType.search([('type', '=', 'receivable')], limit=1)
    if account_type_code and 'payable' in account_type_code:
        return AccountType.search([('type', '=', 'payable')], limit=1)
    return AccountType.search([], limit=1) or None


def _ensure_account_by_xmlname(env, xmlname, module='l10n__ve_evo'):
    Account = env['account.account'].sudo()
    rec = _resolve_xmlid(env, xmlname, module=module)
    if rec:
        return rec
    m = re.search(r'(\d{3,6})$', xmlname)
    code = m.group(1) if m else None
    domain = [('code', '=', code)] if code else []
    acc = Account.search(domain, limit=1) if domain else Account.search([], limit=1)
    if acc:
        imd = env['ir.model.data'].sudo().search([('module', '=', module), ('name', '=', xmlname), ('model', '=', 'account.account')], limit=1)
        if not imd:
            env['ir.model.data'].sudo().create({'module': module, 'name': xmlname, 'model': 'account.account', 'res_id': acc.id})
            _logger.info("[l10n__ve_evo] Registrado ir.model.data para cuenta existente %s -> %s", xmlname, acc.id)
        return acc

    account_type_key = None
    if code and code.startswith('13'):
        account_type_key = 'asset_receivable'
    elif code and code.startswith('21'):
        account_type_key = 'liability_payable'
    elif code and code.startswith('51'):
        account_type_key = 'income'
    elif code and code.startswith('60'):
        account_type_key = 'expense'
    elif code and code.startswith('14'):
        account_type_key = 'asset_current'

    vals = {'code': code or xmlname, 'name': xmlname.replace('_', ' ').title()}

    if 'user_type_id' in Account._fields:
        user_type = None
        if account_type_key:
            user_type = _find_account_type_record(env, account_type_key)
        if user_type:
            vals['user_type_id'] = user_type.id
    else:
        if account_type_key and 'account_type' in Account._fields:
            vals['account_type'] = account_type_key

    if 'company_id' in Account._fields:
        try:
            vals['company_id'] = env.company.sudo().id
        except Exception:
            pass

    try:
        a = Account.create(vals)
        env['ir.model.data'].sudo().create({'module': module, 'name': xmlname, 'model': 'account.account', 'res_id': a.id})
        _logger.info("[l10n__ve_evo] Creada y registrada cuenta %s -> %s", xmlname, a.id)
        return a
    except Exception:
        _logger.exception("[l10n__ve_evo] No se pudo crear cuenta %s", xmlname)
        return None


def _assign_template_to_company(env, tpl):
    company = env.company.sudo()
    candidate_fields = [
        'account_chart_template_id',
        'chart_template_id',
        'account_chart_template_evo_id',
        'account_chart_template',
    ]
    for fld in candidate_fields:
        if fld in company._fields:
            try:
                current = getattr(company, fld, False)
                current_id = current.id if hasattr(current, 'id') else current
                if not current_id or current_id != tpl.id:
                    company.write({fld: tpl.id})
                    _logger.info("[l10n__ve_evo] Template %s asignado a res.company.%s", tpl.id, fld)
                return True
            except Exception:
                _logger.exception("[l10n__ve_evo] Error asignando template a res.company.%s", fld)
                return False
    _logger.info("[l10n__ve_evo] Ningún campo estándar para asignar template encontrado en res.company.")
    return False


def _post_init_assign_template(env):
    """Crea y registra el account.chart.template si es posible y lo asigna a la compañía."""
    Model = env['account.chart.template']

    # Si el modelo es abstracto (_auto == False) no hay tabla para crear registros
    if not getattr(Model, '_auto', True):
        _logger.info("l10n__ve_evo: account.chart.template is abstract in this DB; skipping template creation.")
        return None

    name = "Venezuela - EVO (l10n__ve_evo)"
    existing = Model.search([('name', '=', name)], limit=1)
    if existing:
        _logger.info("l10n__ve_evo: Chart template '%s' already exists (id=%s). Skipping creation.", name, existing.id)
        return existing

    country = env.ref('base.ve', raise_if_not_found=False)
    currency = env.ref('base.VES', raise_if_not_found=False)

    vals = {
        'name': name,
        'code_digits': 6,
        'country_id': country.id if country else False,
        'currency_id': currency.id if currency else False,
        'sequence': 10,
    }

    try:
        tpl = Model.create(vals)
        # Registrar ir.model.data para que aparezca como paquete fiscal seleccionable
        try:
            env['ir.model.data'].sudo().create({
                'module': 'l10n__ve_evo',
                'name': 'chart_template_ve_evo',
                'model': 'account.chart.template',
                'res_id': tpl.id,
            })
            _logger.info("l10n__ve_evo: Registered ir.model.data for chart template id=%s", tpl.id)
        except Exception:
            _logger.exception("l10n__ve_evo: Failed to create ir.model.data for chart template id=%s", tpl.id)
        _logger.info("l10n__ve_evo: Created chart template '%s' (id=%s).", name, tpl.id)
        # Intentar asignar inmediatamente a la compañía actual
        try:
            _assign_template_to_company(env, tpl)
        except Exception:
            _logger.exception("[l10n__ve_evo] Error asignando template a la compañía tras creación")
        return tpl
    except Exception as e:
        _logger.exception("l10n__ve_evo: Failed to create chart template: %s", e)
        return None


def _post_init_hook(cr, registry):
    """Hook de post instalación invocado por Odoo: firma (cr, registry)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = 'l10n__ve_evo'
    try:
        # 1) Asignar country_id a tax groups creados por este módulo
        try:
            ve = env.ref('base.ve', raise_if_not_found=False) or env['res.country'].search([('code', '=', 'VE')], limit=1)
            if ve:
                imd = env['ir.model.data'].sudo()
                tax_group_imds = imd.search([('module', '=', module), ('model', '=', 'account.tax.group')])
                if tax_group_imds:
                    tg_ids = []
                    for i in tax_group_imds:
                        try:
                            tg = env['account.tax.group'].browse(i.res_id)
                            if tg.exists():
                                tg_ids.append(tg.id)
                        except Exception:
                            continue
                    if tg_ids:
                        env['account.tax.group'].browse(tg_ids).write({'country_id': ve.id})
                        _logger.info("[l10n__ve_evo] Asignado country_id VE a %s tax groups creados por el módulo.", len(tg_ids))
        except Exception:
            _logger.exception("[l10n__ve_evo] Error asignando country_id a tax groups")

        # 2) Ajustar simetría de impuestos (refund repartition) de forma segura
        try:
            tax_xmlids = [
                'l10n__ve_evo.l10n__ve_evo_iva_sale_16',
                'l10n__ve_evo.l10n__ve_evo_iva_sale_8',
                'l10n__ve_evo.l10n__ve_evo_iva_sale_exento'
            ]
            for xmlid in tax_xmlids:
                tax = env.ref(xmlid, raise_if_not_found=False)
                if tax:
                    invoice_lines = tax.invoice_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                    refund_lines = tax.refund_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                    if invoice_lines and refund_lines:
                        try:
                            # Si hay una sola línea de invoice, usar su factor; si varias, usar 100 por seguridad
                            for r in refund_lines:
                                if len(invoice_lines) == 1:
                                    r.write({'factor_percent': abs(invoice_lines[0].factor_percent)})
                                else:
                                    r.write({'factor_percent': 100})
                            _logger.info("[l10n__ve_evo] Ajustado refund factor para impuesto %s.", tax.name)
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo ajustar refund factor para impuesto %s", tax.name)
        except Exception:
            _logger.exception("[l10n__ve_evo] Error ajustando simetría de impuestos")

        # 3) Crear/registrar chart template y asignarlo a la compañía
        try:
            _post_init_assign_template(env)
        except Exception:
            _logger.exception("[l10n__ve_evo] Error en asignación de template")
    except Exception:
        _logger.exception("[l10n__ve_evo] Error en _post_init_hook")


def uninstall_hook(env):
    module = 'l10n__ve_evo'
    try:
        # 1) Restaurar refund factors de impuestos del módulo a 100 (si existen)
        try:
            tax_xmlids = [
                'l10n__ve_evo.l10n__ve_evo_iva_sale_16',
                'l10n__ve_evo.l10n__ve_evo_iva_sale_8',
                'l10n__ve_evo.l10n__ve_evo_iva_sale_exento'
            ]
            for xmlid in tax_xmlids:
                tax = env.ref(xmlid, raise_if_not_found=False)
                if tax:
                    refund_lines = tax.refund_repartition_line_ids.filtered(lambda l: l.repartition_type == 'tax')
                    if refund_lines:
                        try:
                            refund_lines.write({'factor_percent': 100})
                            _logger.info("[l10n__ve_evo] Restaurado refund factor para impuesto %s.", tax.name)
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo restaurar refund factor para impuesto %s", tax.name)
        except Exception:
            _logger.exception("[l10n__ve_evo] Error restaurando refund factors")

        # 2) Restaurar country_id en tax groups creados por el módulo
        try:
            imd = env['ir.model.data'].sudo()
            tax_group_imds = imd.search([('module', '=', module), ('model', '=', 'account.tax.group')])
            if tax_group_imds:
                tg_ids = []
                for i in tax_group_imds:
                    try:
                        tg = env['account.tax.group'].browse(i.res_id)
                        if tg.exists():
                            tg_ids.append(tg.id)
                    except Exception:
                        continue
                if tg_ids:
                    env['account.tax.group'].browse(tg_ids).write({'country_id': False})
                    _logger.info("[l10n__ve_evo] Restaurado country_id en %s tax groups creados por el módulo.", len(tg_ids))
        except Exception:
            _logger.exception("[l10n__ve_evo] Error restaurando country_id en tax groups")

        # 3) Intentar eliminar accounts/journals creados por el módulo si están sin uso
        try:
            IMD = env['ir.model.data'].sudo()
            for imd in IMD.search([('module', '=', module), ('model', '=', 'account.journal')]):
                try:
                    j = env['account.journal'].browse(imd.res_id)
                    if not j.exists():
                        imd.unlink()
                        continue
                    moves = env['account.move'].search([('journal_id', '=', j.id)], limit=1)
                    if not moves:
                        try:
                            j.unlink()
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo eliminar journal %s (%s)", j.name, j.id)
                        try:
                            imd.unlink()
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo eliminar ir.model.data para journal %s", imd.name)
                        _logger.info("[l10n__ve_evo] Eliminado journal %s (%s)", j.name, j.id)
                    else:
                        _logger.info("[l10n__ve_evo] No se elimina journal %s: tiene movimientos", j.name)
                except Exception:
                    _logger.exception("[l10n__ve_evo] Error procesando journal imd %s", imd.name)
            for imd in IMD.search([('module', '=', module), ('model', '=', 'account.account')]):
                try:
                    a = env['account.account'].browse(imd.res_id)
                    if not a.exists():
                        imd.unlink()
                        continue
                    lines = env['account.move.line'].search([('account_id', '=', a.id)], limit=1)
                    if not lines:
                        try:
                            a.unlink()
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo eliminar cuenta %s (%s)", a.code, a.id)
                        try:
                            imd.unlink()
                        except Exception:
                            _logger.exception("[l10n__ve_evo] No se pudo eliminar ir.model.data para cuenta %s", imd.name)
                        _logger.info("[l10n__ve_evo] Eliminada cuenta %s (%s)", a.code, a.id)
                    else:
                        _logger.info("[l10n__ve_evo] No se elimina cuenta %s: tiene movimientos", a.code)
                except Exception:
                    _logger.exception("[l10n__ve_evo] Error procesando account imd %s", imd.name)
        except Exception:
            _logger.exception("[l10n__ve_evo] Error limpiando accounts/journals en uninstall")

    except Exception:
        _logger.exception("[l10n__ve_evo] Error en uninstall_hook")
