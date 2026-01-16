# -*- coding: utf-8 -*-
from odoo import models

class ReportAccountGeneralLedger(models.AbstractModel):
    _inherit = 'account.general.ledger'
    # Aquí se anadirán métodos personalizados más adelante si es necesario,
    # pero por ahora, solo aseguramos que el modelo se herede correctamente.