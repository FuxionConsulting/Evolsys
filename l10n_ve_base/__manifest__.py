{
    "name": "Venezuela - Base",
    "summary": """
        Modulo Base de la localizacion de Venezuela
    """,
    "license": "LGPL-3",
    "author": "evolsys",
    "website": "https://evolsys.net/",
    "category": "Technical",
    "version": "17.0.0.0.3",
    "depends": ["base", "web"],
    "auto_install": True,
    "data": ["security/ir.model.access.csv", "views/res_config_settings_views.xml"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_base/static/src/core/debug/debug_menu_items.js",
        ],
    },
}
