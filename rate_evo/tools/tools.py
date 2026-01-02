# tools.py
from urllib3.exceptions import InsecureRequestWarning
from urllib3 import disable_warnings
from odoo import fields
import requests
import logging
from bs4 import BeautifulSoup
import re

_logger = logging.getLogger(__name__)

def _normalize_number_string(s):
    """Normaliza una cadena numérica que puede usar '.' como separador de miles
    y ',' como decimal, o viceversa. Devuelve una cadena con '.' como separador decimal.
    Ejemplos:
      '270.789,30' -> '270789.30'
      '270,789300000000' -> '270.789300000000'
      '0,003692908102' -> '0.003692908102'
      '270789.3' -> '270789.3'
    """
    if not s:
        return None
    s = s.strip()
    # Extraer la primera subcadena que contenga dígitos, puntos o comas
    m = re.search(r'[\d\.,]+', s)
    if not m:
        return None
    num = m.group(0)

    # Si contiene ambos '.' y ',', asumimos que el que aparece más a la derecha es el decimal
    if '.' in num and ',' in num:
        if num.rfind(',') > num.rfind('.'):
            # coma como decimal, puntos como separador de miles
            num = num.replace('.', '')
            num = num.replace(',', '.')
        else:
            # punto como decimal, comas como separador de miles
            num = num.replace(',', '')
    else:
        # Si solo tiene coma, la tratamos como decimal
        if ',' in num and '.' not in num:
            num = num.replace(',', '.')
        # Si solo tiene punto o solo dígitos, lo dejamos tal cual

    num = num.strip()
    return num

def get_usd_rate_of_the_day_bcv(self):
    """
    Extrae la tasa USD desde la web del BCV.
    Devuelve una tupla (valor_float, fecha) donde:
      - valor_float es el número tal como aparece en la web (sin invertir).
      - fecha es fields.Date.context_today(self) o False en caso de error.
    NOTA: la semántica (si es VES por USD o USD por VES) debe normalizarla el consumidor.
    """
    disable_warnings(InsecureRequestWarning)
    URL = "https://www.bcv.org.ve/"
    current_date = fields.Date.context_today(self)

    try:
        resp = requests.get(URL, verify=False, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        usd_container = soup.find(id="dolar")
        if not usd_container:
            _logger.error("BCV: no se encontró el contenedor con id='dolar'")
            return (None, False)

        raw_text = usd_container.get_text(separator=" ", strip=True)
        _logger.debug("BCV raw text for dolar: %s", raw_text)

        normalized = _normalize_number_string(raw_text)
        if not normalized:
            _logger.error("BCV: no se pudo normalizar el número extraído: %s", raw_text)
            return (None, False)

        try:
            value = float(normalized)
        except Exception as e:
            _logger.exception("BCV: error convirtiendo a float '%s': %s", normalized, e)
            return (None, False)

        _logger.info("BCV: tasa cruda extraída: %s (normalizada: %s) fecha: %s", raw_text, value, current_date)
        return (value, current_date)

    except Exception as e:
        _logger.exception("BCV: error al obtener la página: %s", e)
        return (None, False)
