from . import models
try:
    from . import hooks as _hooks
    create_company_if_missing = getattr(_hooks, 'create_company_if_missing', None)
except Exception:
    import logging
    logging.getLogger(__name__).exception('Error importing hooks module')
