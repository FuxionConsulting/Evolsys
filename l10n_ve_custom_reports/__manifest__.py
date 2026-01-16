# -*- coding: utf-8 -*-
{
    'name': 'Venezuela - Reportes de personalizados',
    'summary': 'Reportes contables personalizados.',
    'description': 'Añade un reporte de facturas personalizado que calcula el monto neto después de restar las notas de crédito conciliadas. Parte de los reportes personalizados para Venezuela.',
    'license': 'LGPL-3',
    'author': 'evolsys',
    'website': 'https://evolsys.net/',
    'category': 'Accounting/Accounting',
    'version': '17.0.0.0.0',
    # Incluimos 'account' explícitamente además de 'account_reports' para asegurar el orden de carga.
    'depends': ["base", "account_reports", "l10n_ve_accountant", "account"], 
    'data': [
        'security/ir.model.access.csv',
        'views/report_views.xml',
    ],
    'installable': True,
    'application': False,
}