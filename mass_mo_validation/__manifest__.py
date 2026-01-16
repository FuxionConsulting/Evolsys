# __manifest__.py

{
    'name': "Mass MO Validation",
    'summary': "Module to validate manufacturing orders in bulk",
    'description': """
        This module allows users to search and validate manufacturing orders in bulk,
        and also to check material availability for selected orders.
    """,
    'author': "evolsys", # <-- Asegúrate de que esto sea una cadena de texto
    'website': "https://www.evolsys.net", # <-- Asegúrate de que esto sea una cadena de texto
    'category': 'Manufacturing',
    'version': '1.0',
    'depends': ['mrp', 'stock'], # Confirma que mrp y stock están instalados
    'data': [
        'security/mass_mo_validation_security.xml',
        'security/mass_mo_validation_security_categories.xml',
        'security/ir.model.access.csv',
        'views/mass_mo_validation_views.xml', # Si este archivo existe y está en 'views/'
        'views/mo_search_wizard_views.xml',
        'views/mo_availability_check_wizard_views.xml',
        'views/mo_validate_wizard_views.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}