{
    "name": "Venezuela - Contactos",
    "summary": """
       Modulo para informacion de contactos de Venezuela
    """,
    "license": "LGPL-3",
    "author": "evolsys",
    "website": "https://evolsys.net/",
    "category": "Contacts/Contacts",
    "version": "17.0.0.0.1",
    "depends": ["base", "contacts", "l10n_ve_rate", "l10n_ve_location"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner.xml",
        "views/res_config_settings.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
}
