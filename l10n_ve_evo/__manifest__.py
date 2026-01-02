# -*- coding: utf-8 -*-
# Copyright 2024 - l10n_ve_evo
{
    'name': 'Venezuela - Contabilidad (Evolsys)',
    'countries': ['ve'],
    'author': 'Evolsys',
    "summary": "Localización Contable para Venezuela",
    'category': 'Accounting/Localizations/Account Charts',
    "version": "19.0.2.4.4",
    'summary': 'Localización Contable para Venezuela (VE) para Odoo 19',
    'depends': [
        
        'base',
        'base_setup',
        'account',
        'accountant',
        'account_accountant',
        'rate_evo',
        
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/res.country.state.csv',
        'data/res.country.municipality.csv',
        'data/res.country.parish.csv',
        'data/res.city.csv',
        'data/account.group-ve.xml',
        'data/account.chart.template.xml',
        #'data/account.account-ve.csv',
        #'data/account.account-ve.xml',        
        'data/account.tax.group.xml',
        'data/account.tax.xml',
        'data/account.journal.xml',
        'data/account.fiscal.position.xml',
        'data/ve_localization_data.xml',
        'views/res_partner_company_view.xml',
        'views/res_partner_person_view.xml',
        
    ],
 

    'post_init_hook': '_post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'auto_install': False,
    'installable': True,
    'images': ['static/description/icon.png'],
    'license': 'LGPL-3',
    'chart_template_id': 'l10n_ve_evo.ve_chart_template',
}
