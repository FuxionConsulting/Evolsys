# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

COMPANY_NAME = 'MOTOFIT PRO, C.A'
COMPANY_VAT = 'J507849082'  # reemplaza por el RIF real

def create_company_if_missing(cr, registry):
    """Hook de post instalación: crea partner+company solo si no existe la compañía."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env['res.company']
    Partner = env['res.partner']

    # Buscar compañía por nombre
    company = Company.search([('name', '=', COMPANY_NAME)], limit=1)
    if company:
        _logger.info('create_company_if_missing: la compañía ya existe (id=%s). No se crea otra.', company.id)
        # Opcional: asegurar que el partner tenga vat; si no, crear/actualizar partner
        partner = company.partner_id
        if partner and not partner.vat:
            _logger.info('create_company_if_missing: partner existente sin vat; actualizando vat.')
            partner.sudo().write({'vat': COMPANY_VAT})
        elif not partner:
            _logger.info('create_company_if_missing: company sin partner; creando partner y asignando.')
            p = Partner.sudo().create({
                'name': COMPANY_NAME,
                'is_company': True,
                'vat': COMPANY_VAT,
                'company_type': 'company',
            })
            company.sudo().write({'partner_id': p.id})
        return

    # Si no existe, crear partner primero (para pasar validaciones) y luego la company
    _logger.info('create_company_if_missing: no existe la compañía; creando partner y company.')
    partner_vals = {
        'name': COMPANY_NAME,
        'is_company': True,
        'vat': COMPANY_VAT,
        'company_type': 'company',
    }
    p = Partner.sudo().create(partner_vals)
    Company.sudo().create({
        'name': COMPANY_NAME,
        'partner_id': p.id,
    })
    _logger.info('create_company_if_missing: compañía creada correctamente.')
