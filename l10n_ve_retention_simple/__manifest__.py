{
    "name": "Venezuela Retention Simple",
    "version": "17.0.0.2.4",
    "summary": "Generación simple de retenciones al validar facturas",
    "category": "Accounting",
    "author": "Evolsys",
    "license": "LGPL-3",
    "depends": ["base", "account", 'mail', 'l10n_ve_accountant'],
    "data": [
        "data/sequence_retention.xml",
        "security/ir.model.access.csv",
        "views/res_partner_inherit_views.xml",
        "views/account_retention_views.xml",
        "views/account_move_inherit_views.xml",
    ],
    "installable": True,
    "application": False,
}
