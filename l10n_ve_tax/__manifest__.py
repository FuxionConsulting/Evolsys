{
    "name": "Venezuela - Impuestos",
    "summary": """
        Impuestos para la localizacion en Venezuela
    """,
    "license": "LGPL-3",
    "author": "evolsys",
    "website": "https://evolsys.net/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "17.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_base", "l10n_ve_rate"],
    "data": [
        "views/res_config_settings.xml",
        "views/account_move.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "assets": {
        "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    },
}
