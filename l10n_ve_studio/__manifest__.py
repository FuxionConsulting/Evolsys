{
    "name": "Venezuela - Studio",
    "summary": """
        Limitacion de Odoo-Studio para la localizacion en Venezuela
    """,
    "license": "LGPL-3",
    "author": "evolsys",
    "website": "https://evolsys.net/",
    "category": "Base",
    "version": "17.0.0.0.1",
    # any module necessary for this one to work correctly
    "depends": ["l10n_ve_base"],
    "data": [],
    "images": ["static/description/icon.png"],
    "application": True,
    "auto_install": True,
    "post_init_hook": "post_init_hook",
}
