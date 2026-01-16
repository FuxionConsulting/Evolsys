# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
import logging

_logger = logging.getLogger(__name__)

class AccountDailyLedger(models.AbstractModel):
    _inherit = "account.general.ledger.report.handler"
    _name = "account.daily.ledger.report.handler"
    _description = "Daily Ledger Custom Handler"

    @api.model
    def _get_query_sums(self, report, options):
        """
        Override to set strict range to True so the report will not show the opening balance of the
        account. Also ensures options for multi-company and foreign currency are correctly formatted
        before calling super.
        """
        options.setdefault("general_ledger_strict_range", True)

        # Propagate 'usd_report' from context into options for deeper methods
        if 'usd_report' not in options:
            options['usd_report'] = self.env.context.get('usd_report', False)
        
        # Ensure 'multi_company' and 'excluded_company_ids' are correctly formatted in options
        # as per account_report.py modifications, for consistency.
        # This might be redundant if the caller already formats it, but ensures robustness.
        if options.get('multi_company') and not (isinstance(options['multi_company'], list) and all(isinstance(c, dict) and 'id' in c for c in options['multi_company'])):
            company_ids_to_format = []
            if isinstance(options['multi_company'], list):
                for mc_data in options['multi_company']:
                    if isinstance(mc_data, dict) and 'id' in mc_data:
                        company_ids_to_format.append(mc_data['id'])
                    elif isinstance(mc_data, int):
                        company_ids_to_format.append(mc_data)
            elif isinstance(options['multi_company'], int):
                company_ids_to_format = [options['multi_company']]
            options['multi_company'] = [{'id': cid} for cid in company_ids_to_format]

        if 'excluded_company_ids' in options and isinstance(options['excluded_company_ids'], list):
            options['excluded_company_ids'] = [int(cid) for cid in options['excluded_company_ids'] if isinstance(cid, (int, str)) and str(cid).isdigit()]
        else:
            options['excluded_company_ids'] = []

        _logger.info(f"[account_daily_ledger] _get_query_sums options before super call: {options}")

        return super()._get_query_sums(report, options)

    @api.model
    def _get_account_title_line(self, report, options, account, has_lines, eval_dict):
        """
        Override to set has_lines to False so the report lines will not be foldable.
        Propagates 'usd_report' to options if not present.
        """
        has_lines = False
        
        # Propagate 'usd_report' from context into options for deeper methods
        if 'usd_report' not in options:
            options['usd_report'] = self.env.context.get('usd_report', False)
        
        _logger.info(f"[account_daily_ledger] _get_account_title_line options: {options}")

        return super()._get_account_title_line(report, options, account, has_lines, eval_dict)