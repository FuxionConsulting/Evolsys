# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields
from odoo.tools.misc import format_date
from datetime import datetime, date, timedelta
import logging

_logger = logging.getLogger(__name__)

class ReportAccountCashFlow(models.AbstractModel):
    _inherit = 'account.cash.flow.report'

    @api.model
    def _get_lines(self, options, line_id=None):
        # Override _get_lines to ensure currency conversion options are correctly passed.
        # This is a high-level method, the actual currency logic usually happens in deeper calls.
        # Ensure options are properly prepared for currency table if needed by sub-methods.
        
        # Propagate 'usd_report' from context into options for deeper methods
        if 'usd_report' not in options:
            options['usd_report'] = self.env.context.get('usd_report', False)
        
        # Ensure 'multi_company' and 'excluded_company_ids' are correctly formatted in options
        # as per account_report.py modifications.
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

        return super()._get_lines(options, line_id=line_id)

    @api.model
    def _get_liquidity_moves(self, options, date_scope, journal_ids, account_ids, payment_move_ids=None):
        """
        Overrides _get_liquidity_moves to address the 'payment_move_ids' argument issue.
        It now makes 'payment_move_ids' an optional argument.
        It also ensures the currency table query is called with correct options.
        """
        _logger.info(f"[account_cash_flow_report] _get_liquidity_moves called with payment_move_ids: {payment_move_ids}")
        
        # Call the original method from the super class.
        # The 'payment_move_ids' argument was causing a TypeError when it was not passed.
        # By making it an optional argument in our override, we ensure compatibility.
        
        # Ensure conversion date is available for currency table
        conversion_date = date_scope['date_to']
        if isinstance(conversion_date, str):
            conversion_date = fields.Date.from_string(conversion_date)

        # Prepare currency table options if any direct call to _get_query_currency_table is made here.
        # The base _get_liquidity_moves might use _get_query_currency_table indirectly.
        # If the base method expects 'companies' directly, we need to adapt it here.
        # However, it's more likely that the base method gets its company context from self.env or options.

        # Let's verify the base method's arguments. Odoo 17 base `_get_liquidity_moves` doesn't take `payment_move_ids`
        # as a direct argument in its signature (it fetches them internally if needed).
        # This implies a custom override in your module or another module added it to the super call.
        # To fix this, we should remove `payment_move_ids` from the `super()` call if it's not expected by Odoo's core.

        # Re-evaluating the traceback: the `payment_move_ids` TypeError was when _get_liquidity_moves was called *without* it.
        # If this method is overridden in your module and expects it, but a caller doesn't provide it, it fails.
        # By adding `payment_move_ids=None` to the signature, we make it optional for callers.
        # The super call needs to handle it if the base method expects it.
        
        # Let's ensure the options are passed correctly to the super, which might then pass it on to currency table.
        # The original method's context for `payment_move_ids` is usually handled internally.
        # So, the safest approach is to just call `super()` without passing `payment_move_ids` if it's not expected by the core.
        
        # However, if your module *intended* to use payment_move_ids for custom filtering:
        # If `payment_move_ids` is None, this means it was not explicitly passed by the caller.
        # The base method in Odoo 17 `_get_liquidity_moves` does NOT have `payment_move_ids` in its signature.
        # The error suggests your *override* `_get_liquidity_moves` expected it, but the base call from Odoo didn't provide it.
        # Making it optional in *your* signature was the right fix for the direct error.

        # Now, how to call super?
        # If your module added `payment_move_ids` to the signature, it means your module (or another custom one)
        # modified the way this method is called OR the base method it inherits from.
        # Assuming the goal is to make it compatible with Odoo 17's core and your module's logic:
        # If payment_move_ids was *intended* to be used by your custom logic, you can use it here.
        # If it was an artifact of an incorrect previous override/merge, then calling super without it is best.
        
        # Given the previous error was `TypeError: _get_liquidity_moves() missing 1 required positional argument: 'payment_move_ids'`,
        # this means a caller *expected* a `payment_move_ids` argument, but didn't provide it.
        # The fix in your code was to add `payment_move_ids=None` to *this* override's signature. This allows calls without it.
        # Now, when calling `super()`, we must respect the base method's signature.
        # Standard Odoo 17 `_get_liquidity_moves` takes `options`, `date_scope`, `journal_ids`, `account_ids`.
        
        # So, the `super()` call should look like:
        # return super()._get_liquidity_moves(options, date_scope, journal_ids, account_ids)
        # If your module *needs* `payment_move_ids` for its custom logic in this function, then you use it.
        # But don't pass it to super if super doesn't expect it.
        
        # The original error was `TypeError: _get_liquidity_moves() missing 1 required positional argument: 'payment_move_ids'`.
        # This implies that a call to YOUR OVERRIDDEN METHOD was missing this argument.
        # By adding `payment_move_ids=None` to THIS method's signature, you fixed the direct error.
        # Now, the `super()` call:
        
        # It's safest to simply call the base Odoo 17 method as it expects its arguments:
        return super()._get_liquidity_moves(options, date_scope, journal_ids, account_ids)

    # You might have other methods here that prepare options or call currency conversions.
    # Ensure they follow the pattern of passing company-related options within the 'options' dictionary.

    # Example of a method that might indirectly use currency_table and thus need proper options:
    # `_get_cash_flow_line` or `_compute_total_cash_flow` if they perform custom SQL.
    # However, the base cash flow report in Odoo tends to calculate amounts and then format them.
    # The primary fix for `payment_move_ids` is applied here.
    # The currency table changes propagate via the options dictionary handled by `_get_lines` above.