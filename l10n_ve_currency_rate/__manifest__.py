{
    "name": "Auto Currency Rate for VE",
    "version": "17.0.1.0.1",
    "description": "Sync Currency Rates Automatically for VE",
    "summary": """
    This module syncs the currency rate of currencies used in 
    Venezuela (USD, EUR, CNY, RUB, TRY) in the database automatically. 
    This feature is something similar to what is available in Odoo 
    Enterprise, but uses `https://www.bcv.org.ve` to get the currency rates.
    """,
    "author": "Tecnodomotik, Hynsys Technologies",
    "maintainer": "tecnodomotik@gmail.com",
    "support": "tecnodomotik@gmail.com",
    "website": "https://tecnodomotik.odoo.com",
    "license": "LGPL-3",
    "category": "Accounting",
    "images": ["static/description/images/automatic_currency_rate.png"],
    "depends": ["account"],
    "data": [
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
    ],
    "excludes": [
        "web_enterprise",
    ],
    "auto_install": False,
    "application": False,
}
