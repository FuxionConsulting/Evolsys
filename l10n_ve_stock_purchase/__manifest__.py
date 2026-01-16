{
    "name": "Venezuela - Inventario/Compras",
    "version": "17.0.0.0.0",
    "license": "LGPL-3",
    "summary": "Modulo para gestionar inventario/compras en Venezuela",
    "description": """
        Este modulo personaliza el proceso de gestion de inventario/compras para cumplir con las regulaciones venezolanas.
    """,
    "author": "evolsys",
    "website": "https://evolsys.net/",
    "category": "Purchase",
    "depends": [
        "purchase_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "application": True,
    "images": ["static/description/icon.png"],
}
