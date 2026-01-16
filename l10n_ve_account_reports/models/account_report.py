# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_report_information(self, options):
        # Add 'usd_report' to options, propagating it from context or ensuring its presence
        # This is important for consistency, especially if the report itself needs this flag.
        if 'usd_report' not in options:
            options['usd_report'] = self.env.context.get('usd_report', False)
        
        # Ensure 'multi_company' and 'excluded_company_ids' are correctly formatted in options
        # for downstream currency table calls.
        if options.get('multi_company') and not (isinstance(options['multi_company'], list) and all(isinstance(c, dict) and 'id' in c for c in options['multi_company'])):
            company_ids_to_format = []
            if isinstance(options['multi_company'], list):
                company_ids_to_format = [c['id'] if isinstance(c, dict) and 'id' in c else c for c in options['multi_company']]
            elif isinstance(options['multi_company'], int):
                company_ids_to_format = [options['multi_company']]
            # Convert to the expected format: list of dicts with 'id'
            options['multi_company'] = [{'id': cid} for cid in company_ids_to_format]

        if 'excluded_company_ids' in options and isinstance(options['excluded_company_ids'], list):
            # Ensure excluded_company_ids are integers
            options['excluded_company_ids'] = [int(cid) for cid in options['excluded_company_ids'] if isinstance(cid, (int, str)) and str(cid).isdigit()]
        else:
            options['excluded_company_ids'] = [] # Ensure it's always a list

        # Call the original method from the super class
        return super()._get_report_information(options)

    # Overriding _compute_formula_batch_with_engine_domain to ensure 'warnings=None' is passed.
    # This was a previous error in the traceback.
    def _compute_formula_batch_with_engine_domain(self, expression_id_list, domain, warnings=None):
        """ This method computes a batch of formulas that depends on the engine domain. """
        # Ensure warnings is always passed, even if it's None.
        return super()._compute_formula_batch_with_engine_domain(expression_id_list, domain, warnings=warnings)

    # You might have other methods here that prepare options or call currency conversions.
    # For now, these are the most critical, based on previous errors.
    # If other methods also make calls to _get_query_currency_table, they would need similar
    # adjustments to how 'options' are prepared before the call.