# -*- coding: utf-8 -*-
from . import models
# Importar hooks en el namespace del paquete para que Odoo pueda localizar las funciones
from . import hooks

# Exponer los nombres que el manifest espera
# Asegúrate de que hooks.py define exactamente estas funciones:
# def _post_init_hook(env): ...
# def uninstall_hook(env): ...
_post_init_hook = hooks._post_init_hook
uninstall_hook = hooks.uninstall_hook
