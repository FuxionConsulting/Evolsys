{
    "name": "Venezuela - Libro de Inventario",
    "summary": """
        Modulo de libro de Inventario Venezuela
    """,
    "license": "LGPL-3",
    "author": "evolsys",
    "website": "https://www.evolsys.net",
    "category": "Stock / Inventory",
    "version": "17.0.0.0.8",
    "depends": ["stock", "account","sale_stock","l10n_ve_invoice","l10n_ve_stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/stock_book_report.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
}
