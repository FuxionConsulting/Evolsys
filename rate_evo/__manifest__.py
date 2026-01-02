# -*- coding: utf-8 -*-
{
    "name": "Venezuela - Moneda dual (Evolsys)",
    "version": "19.0.2.0.3",
    "summary": "Gestión de precios convertidos y auditoría de tasas de cambio",
    "description": """
Venezuela - Moneda dual (Evolsys)
=================================
Este módulo extiende la funcionalidad estándar de Odoo 19 para:
- Usar las tasas de cambio oficiales (Banco Central de Venezuela) integradas en `res.currency.rate`.
- Mostrar el precio unitario convertido en documentos (facturas, pedidos de venta y compra).
- Registrar auditoría de cambios de tasa y mantener un log de importaciones.
    """,
    "author": "Evolsys",
    "website": "https://www.evolsys.net",
    "category": "Accounting",
    "depends": [
        "account",
        "sale",
        "sale_management",
        "purchase",
        "currency_rate_live",
        "stock",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/account_move_line_views.xml",
        "views/sale_order_line_views.xml",
        "views/purchase_order_line_views.xml",
        "views/account_move_views.xml",
        "views/account_move_totals_views.xml",
        "views/sale_order_views.xml",
        "views/sale_order_converted_totals.xml",
        "views/purchase_order_views.xml",
        "views/purchase_order_converted_totals.xml",
        "views/account_payment_register_views.xml",
        #'views/currency_rate_provider_views.xml',
        #"views/audit_views.xml",
        #"views/rate_log_views.xml",
      
    ],


     "installable": True,
    "application": False,
    "license": "LGPL-3",
    'images': ['static/description/icon.png'],
}