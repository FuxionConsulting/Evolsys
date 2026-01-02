# res_company_bcv.py
from odoo import models, fields
import logging
from ..tools.tools import get_usd_rate_of_the_day_bcv

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "[BCV] Banco Central de Venezuela")]
    )

    def _parse_bcv_data(self, available_currencies):
        """
        Proveedor BCV compatible con currency_rate_live.
        Normaliza la tasa para que el valor devuelto sea USD por unidad de VES
        (es decir, cuántos USD vale 1 VES).
        Devuelve un dict: {'USD': (usd_per_unit, date), 'VES': (1.0, date)}
        """
        rates = {}
        available_currency_names = available_currencies.mapped("name")

        try:
            raw_rate, rate_date = get_usd_rate_of_the_day_bcv(self)
            _logger.info("BCV raw_rate=%s date=%s for company %s", raw_rate, rate_date, self.id)

            if not rate_date or raw_rate is None:
                _logger.error("BCV: tasa o fecha inválida para company %s", self.id)
                return {}

            try:
                raw_rate = float(raw_rate)
            except Exception:
                _logger.exception("BCV: raw_rate no convertible a float: %s", raw_rate)
                return {}

            if raw_rate <= 0:
                _logger.error("BCV: raw_rate no válido (<=0): %s", raw_rate)
                return {}

            # Heurístico: si raw_rate > 1 entonces probablemente es VES por USD
            if raw_rate > 1.0:
                unidad_por_usd = raw_rate
                usd_per_unit = 1.0 / unidad_por_usd
                _logger.info("BCV parsed as VES per USD=%s -> USD per VES=%s", unidad_por_usd, usd_per_unit)
            else:
                usd_per_unit = raw_rate
                unidad_por_usd = 1.0 / usd_per_unit
                _logger.info("BCV parsed as USD per VES=%s -> VES per USD=%s", usd_per_unit, unidad_por_usd)

            if "USD" in available_currency_names:
                rates["USD"] = (usd_per_unit, rate_date)

        except Exception as e:
            _logger.exception("Error obteniendo USD desde BCV: %s", e)
            return {}

        if "VES" in available_currency_names:
            rates["VES"] = (1.0, rate_date)

        return rates
