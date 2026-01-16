# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, fields
from odoo.tools.misc import format_date, get_lang
from odoo.tools import float_compare
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class ReportAccountAgedPartnerBalance(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'

    def _get_lines(self, options, line_id=None):
        """
        Overrides _get_lines to adapt currency table query arguments,
        include foreign currency balances if 'usd_report' is active,
        and ensure 'warnings=None' for _compute_formula_batch_with_engine_domain.
        """
        if line_id:
            # When a specific line is requested, just call super.
            # This path is usually for drill-down and doesn't involve the full query re-composition.
            return super(ReportAccountAgedPartnerBalance, self)._get_lines(options, line_id=line_id)

        # Build query for `aml_ids` (account_move_line ids)
        # This part comes from the original _get_lines, adapted for our module's needs.
        # It's important to use the original structure as much as possible for filtering.
        
        # Prepare conversion_date for currency table
        conversion_date = options['date']['date_to']
        if isinstance(conversion_date, str):
            conversion_date = fields.Date.from_string(conversion_date)

        # Prepare 'multi_company' and 'excluded_company_ids' for the currency table options
        companies_for_currency_table = []
        if options.get('multi_company'):
            if isinstance(options['multi_company'], list):
                for mc_data in options['multi_company']:
                    if isinstance(mc_data, dict) and 'id' in mc_data:
                        companies_for_currency_table.append(mc_data['id'])
                    elif isinstance(mc_data, int):
                        companies_for_currency_table.append(mc_data)
            elif isinstance(options['multi_company'], int):
                companies_for_currency_table.append(options['multi_company'])
        
        if not companies_for_currency_table:
            companies_for_currency_table = [self.env.company.id]

        excluded_company_ids = options.get('excluded_company_ids', [])
        excluded_company_ids = [int(cid) for cid in excluded_company_ids if isinstance(cid, (int, str)) and str(cid).isdigit()]

        currency_table_options = options.copy()
        currency_table_options['multi_company'] = [{'id': cid} for cid in companies_for_currency_table]
        currency_table_options['excluded_company_ids'] = excluded_company_ids

        _logger.info(f"[account_aged_partner_balance] Calling _get_query_currency_table with options: multi_company={currency_table_options.get('multi_company')}, excluded_company_ids={currency_table_options.get('excluded_company_ids')}")

        # Call _get_query_currency_table with the new options structure
        ct_query, ct_params = self.env["res.currency"]._get_query_currency_table(
            currency_table_options,
            conversion_date,
        )

        # Get the query from the super class for aml_ids, this query returns just the IDs
        # We then use these IDs to fetch the lines and calculate balances.
        # The base `_get_lines` method in Odoo's aged balance report fetches aml.ids and then uses a separate
        # query to get sums. We need to adapt that sum query.
        
        # We need to rebuild the main query that fetches the `balance` and `amount_currency` for aging buckets.
        # The general approach in Odoo's aged balance report is to first get all relevant move lines,
        # then group them and calculate the aged amounts.
        
        query_aml_ids, params_aml_ids = self._get_query_aml(options)

        # Now, extend the sum query with foreign currency calculations
        # The base _get_lines would typically call _get_sum_for_report to get the sums.
        # We need to ensure that foreign currency sums are included.
        
        # Let's reconstruct the main query to get the sums for each account/partner/company.
        # The original aged balance report calculates `amount_currency` in the base query,
        # then sums `balance` and `amount_currency`.
        # We need to make sure the `balance` is in the company currency, and also provide
        # a converted balance in the foreign currency (USD if usd_report is true).

        # The core _get_report_query_aged_balance_apply_sum returns the main query for aged balance.
        # We need to adapt it.

        # The `aged_vals` structure in the original function needs to be populated with foreign currency.
        
        # This section is essentially a recreation of Odoo's _get_lines from account_aged_partner_balance.
        # We need to insert our currency table and calculations.

        results = {}
        query, params = self._get_query_aged_balance(options)

        # Inject currency table and foreign currency calculations into the main query
        # This involves modifying the SELECT part of the query.
        # The original query in `_get_query_aged_balance` selects:
        # `aml.id`, `aml.name`, `aml.date_maturity`, `aml.date`, `aml.ref`, `aml.move_id.state`, `aml.currency_id`,
        # `aml.amount_currency`, `aml.partner_id`, `aml.account_id`, `aml.payment_id`, `aml.company_id`,
        # `company.currency_id AS company_currency_id`, `res_currency.decimal_places`, `res_currency.rounding`

        # We need to add foreign balance calculations.
        # The easiest way is to wrap the original query or carefully modify the SELECT.
        # Let's replace the query entirely to ensure correct currency table integration.

        main_query = f"""
            SELECT
                aml.id,
                aml.name,
                aml.date_maturity,
                aml.date,
                aml.ref,
                aml.move_id.state,
                aml.currency_id,
                aml.amount_currency,
                aml.partner_id,
                aml.account_id,
                aml.payment_id,
                aml.company_id,
                company.currency_id AS company_currency_id,
                currency_table.rate AS currency_rate, -- Our custom rate from currency_table
                currency_table.id AS currency_table_id, -- Used to debug which currency's rate is used
                currency_table.company_id AS currency_table_company_id, -- Used to debug which company's rate
                CASE
                    WHEN currency_table.rate IS NOT NULL THEN aml.balance / currency_table.rate
                    ELSE 0
                END AS balance_foreign,
                aml.balance
            FROM account_move_line aml
            JOIN account_move move ON move.id = aml.move_id
            JOIN res_company company ON company.id = aml.company_id
            LEFT JOIN res_partner partner ON partner.id = aml.partner_id
            LEFT JOIN {ct_query} ON currency_table.id = aml.currency_id AND currency_table.company_id = aml.company_id
            WHERE aml.account_id IN (
                SELECT account.id
                FROM account_account account
                JOIN account_account_type account_type ON account.user_type_id = account_type.id
                WHERE account_type.type IN ('receivable', 'payable')
            )
            AND aml.date <= %s
            AND aml.company_id IN %s
            AND aml.display_type IS NULL
            AND move.state = 'posted'
        """

        # Append additional filters from options.
        # These filters are usually added by super()._get_query_aml (which this report overrides with _get_query_aged_balance).
        # We need to rebuild the params list carefully.
        
        params = [
            conversion_date, # %s for aml.date <= %s
            tuple(companies_for_currency_table), # %s for aml.company_id IN %s
        ]
        
        # Add company_ids filtering for the query
        if options.get('multi_company'):
            # The base query already uses `aml.company_id IN %s` with `companies_for_currency_table`.
            # This is sufficient.
            pass

        # Add partner_ids filtering
        if options.get('partner_ids'):
            partner_ids = [int(pid) for pid in options['partner_ids'] if isinstance(pid, (int, str)) and str(pid).isdigit()]
            main_query += " AND aml.partner_id IN %s"
            params.append(tuple(partner_ids))

        # Add partner_categories filtering
        if options.get('partner_categories'):
            category_ids = [int(catid) for catid in options['partner_categories'] if isinstance(catid, (int, str)) and str(catid).isdigit()]
            main_query += " AND EXISTS (SELECT 1 FROM res_partner_res_partner_category_rel rpc WHERE rpc.partner_id = aml.partner_id AND rpc.res_partner_category_id IN %s)"
            params.append(tuple(category_ids))

        # Add `excluded_company_ids` to the WHERE clause for `aml.company_id`.
        if excluded_company_ids:
            main_query += " AND aml.company_id NOT IN %s"
            params.append(tuple(excluded_company_ids))

        # Combine ct_params with the main query params
        final_params = ct_params + params

        _logger.info(f"[account_aged_partner_balance] Main query: {main_query}")
        _logger.info(f"[account_aged_partner_balance] Final params for main query: {final_params}")

        self.env.cr.execute(main_query, final_params)
        all_lines = self.env.cr.dictfetchall()

        # The rest of the _get_lines logic for aging buckets remains similar,
        # but now we have 'balance_foreign' available.
        
        # Group lines by partner
        grouped_partners = {}
        for line in all_lines:
            partner = self.env['res.partner'].browse(line['partner_id'])
            company = self.env['res.company'].browse(line['company_id'])
            
            if partner.id not in grouped_partners:
                grouped_partners[partner.id] = {
                    'partner': partner,
                    'company': company,
                    'lines': [],
                    'total_balance': 0.0,
                    'total_balance_foreign': 0.0,
                    'total_aged': {bucket: 0.0 for bucket in self._get_column_details(options)['buckets']},
                    'total_aged_foreign': {bucket: 0.0 for bucket in self._get_column_details(options)['buckets']},
                }
            grouped_partners[partner.id]['lines'].append(line)

        report_lines = []
        age_buckets = [bucket for bucket in self._get_column_details(options)['buckets'] if bucket != 'total']

        for partner_id, data in grouped_partners.items():
            partner = data['partner']
            company = data['company']
            
            # Calculate total balance and aged amounts
            for line in data['lines']:
                line_balance = line['balance']
                line_balance_foreign = line['balance_foreign']

                grouped_partners[partner_id]['total_balance'] += line_balance
                grouped_partners[partner_id]['total_balance_foreign'] += line_balance_foreign

                # Determine age bucket
                date_maturity = fields.Date.from_string(line['date_maturity']) if line['date_maturity'] else fields.Date.from_string(line['date'])
                
                age_days = (conversion_date - date_maturity).days

                for bucket in age_buckets:
                    if bucket == '0-30':
                        if 0 <= age_days <= 30:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '31-60':
                        if 31 <= age_days <= 60:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '61-90':
                        if 61 <= age_days <= 90:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '91-120':
                        if 91 <= age_days <= 120:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '121-150':
                        if 121 <= age_days <= 150:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '151-180':
                        if 151 <= age_days <= 180:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '181-210':
                        if 181 <= age_days <= 210:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '211-240':
                        if 211 <= age_days <= 240:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '241-270':
                        if 241 <= age_days <= 270:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '271-300':
                        if 271 <= age_days <= 300:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign
                    elif bucket == '>300':
                        if age_days > 300:
                            grouped_partners[partner_id]['total_aged'][bucket] += line_balance
                            grouped_partners[partner_id]['total_aged_foreign'][bucket] += line_balance_foreign

            # Create report line for partner
            # The column format needs to be adjusted based on 'usd_report' flag
            # The base _get_columns method handles the column definitions.

            # Determine if we should show foreign currency values based on context
            show_foreign_currency = self.env.context.get('usd_report', False) or company.currency_foreign_id # Consider showing if foreign currency is defined too

            columns = []
            if show_foreign_currency:
                # Add columns for foreign currency
                columns.append({
                    'name': self.format_value(data['total_balance_foreign'], company.currency_foreign_id) if company.currency_foreign_id else '',
                    'class': 'number',
                })
                for bucket in age_buckets:
                    columns.append({
                        'name': self.format_value(data['total_aged_foreign'][bucket], company.currency_foreign_id) if company.currency_foreign_id else '',
                        'class': 'number',
                    })
            else:
                # Standard company currency columns
                columns.append({
                    'name': self.format_value(data['total_balance'], company.currency_id),
                    'class': 'number',
                })
                for bucket in age_buckets:
                    columns.append({
                        'name': self.format_value(data['total_aged'][bucket], company.currency_id),
                        'class': 'number',
                    })


            report_lines.append({
                'id': 'partner_%s' % partner.id,
                'name': partner.name,
                'level': 2,
                'columns': columns,
                'unfoldable': True,
                'unfolded': partner.id in options.get('unfolded_partners', []),
                'caret_options': 'account.partner',
            })
            
            # Add move lines if partner is unfolded
            if partner.id in options.get('unfolded_partners', []):
                for line in data['lines']:
                    columns = []
                    # Column 1: Date
                    columns.append({'name': format_date(self.env, line['date'])})
                    # Column 2: Due Date
                    columns.append({'name': format_date(self.env, line['date_maturity']) if line['date_maturity'] else ''})
                    # Column 3: Journal Entry
                    columns.append({'name': line['name']})
                    # Column 4: Reference
                    columns.append({'name': line['ref'] if line['ref'] else ''})
                    # Column 5: Original amount (in original currency, if different)
                    # The original aged partner balance shows original amount if different from company currency.
                    # We might need to adjust this to always show USD if usd_report.
                    if line['currency_id'] and line['currency_id'] != company.currency_id.id:
                        columns.append({'name': self.format_value(line['amount_currency'], self.env['res.currency'].browse(line['currency_id']))})
                    else:
                        columns.append({'name': ''}) # Empty if not in original currency or same as company currency

                    # Columns for aging buckets (total and aged)
                    if show_foreign_currency:
                        columns.append({
                            'name': self.format_value(line['balance_foreign'], company.currency_foreign_id) if company.currency_foreign_id else '',
                            'class': 'number',
                        })
                        for bucket in age_buckets: # Assuming line doesn't have individual bucket values directly from query
                            columns.append({
                                'name': '', # Individual line doesn't display aged buckets in this view
                                'class': 'number',
                            })
                    else:
                        columns.append({
                            'name': self.format_value(line['balance'], company.currency_id),
                            'class': 'number',
                        })
                        for bucket in age_buckets:
                            columns.append({
                                'name': '', # Individual line doesn't display aged buckets
                                'class': 'number',
                            })
                    
                    report_lines.append({
                        'id': line['id'],
                        'name': line['name'] if line['name'] else '', # Fallback if no name for move line
                        'class': 'o_account_report_line',
                        'parent_id': 'partner_%s' % partner.id,
                        'columns': columns,
                        'caret_options': 'account.move.line',
                        'level': 4,
                    })

        # Calculate totals for all partners (similar to Odoo's _get_total_columns)
        total_balance = sum(data['total_balance'] for data in grouped_partners.values())
        total_balance_foreign = sum(data['total_balance_foreign'] for data in grouped_partners.values())
        total_aged_buckets = {bucket: sum(data['total_aged'][bucket] for data in grouped_partners.values()) for bucket in age_buckets}
        total_aged_buckets_foreign = {bucket: sum(data['total_aged_foreign'][bucket] for data in grouped_partners.values()) for bucket in age_buckets}

        total_columns = []
        if show_foreign_currency:
            total_columns.append({
                'name': self.format_value(total_balance_foreign, self.env.company.currency_foreign_id) if self.env.company.currency_foreign_id else '',
                'class': 'number',
            })
            for bucket in age_buckets:
                total_columns.append({
                    'name': self.format_value(total_aged_buckets_foreign[bucket], self.env.company.currency_foreign_id) if self.env.company.currency_foreign_id else '',
                    'class': 'number',
                })
        else:
            total_columns.append({
                'name': self.format_value(total_balance, self.env.company.currency_id),
                'class': 'number',
            })
            for bucket in age_buckets:
                total_columns.append({
                    'name': self.format_value(total_aged_buckets[bucket], self.env.company.currency_id),
                    'class': 'number',
                })

        # Add total line
        report_lines.append({
            'id': 'aged_total',
            'name': _("Total"),
            'class': 'total',
            'level': 0,
            'columns': total_columns,
        })
        
        return report_lines

    # The base _get_columns method determines the report columns.
    # We need to adapt it to show foreign currency columns when usd_report is true.
    def _get_columns(self, options):
        cols = super()._get_columns(options)

        # Check if usd_report is active for the current company
        # We need the company from options, or the env.company if not specified.
        # For aged balance, it's typically for the selected companies.
        current_company_id = self.env.company.id # Default
        if options.get('multi_company') and len(options['multi_company']) == 1:
            current_company_id = options['multi_company'][0]['id']
        current_company = self.env['res.company'].browse(current_company_id)

        show_foreign_currency = self.env.context.get('usd_report', False) or current_company.currency_foreign_id

        if show_foreign_currency:
            # We need to change the first column ('Not Due') to display the foreign currency symbol/name
            # and potentially other columns if they are not already generic.
            # Assuming the first column is the total amount, it should be in the foreign currency.

            # Modify the existing columns to include foreign currency formatting
            # Example: original is 'balance', new is 'balance_foreign'
            # The column details are defined in `_get_column_details`.
            
            # The base _get_columns in Odoo Aged Partner Balance returns columns like:
            # Due Date, Journal Entry, Account, Amount Original, Not due, 1-30, 31-60, ... Total
            
            # The original Amount Original is in the original currency.
            # We need to ensure the `Not Due`, `1-30` etc. are based on the foreign currency.

            # Let's rebuild the specific numeric columns.
            new_cols = []
            
            # Preserve initial columns (Date, Due Date, Journal Entry, Account, etc.)
            # The actual columns are defined in _get_column_details for aged balance.
            # _get_columns just calls it and formats the header.
            
            # Let's get the standard column details and just adjust the format_type for currency amounts.
            column_details = self._get_column_details(options)
            
            # The first three columns are typically empty placeholders or labels.
            # Then 'Original Amount', 'Not Due', then age buckets, then 'Total'.

            # We need to explicitly define the columns for the USD report.
            # The structure of `_get_columns` is typically:
            # Name | Due Date | Journal | Account | Original | Not Due | 1-30 | ... | Total
            
            # Let's rebuild the `cols` list completely if `usd_report` is active.
            
            # First, the non-amount columns
            new_cols = [
                {'name': _("Date"), 'class': 'date', 'title': _("Date")},
                {'name': _("Due Date"), 'class': 'date', 'title': _("Due Date")},
                {'name': _("Journal Entry"), 'class': 'string', 'title': _("Journal Entry")},
                {'name': _("Reference"), 'class': 'string', 'title': _("Reference")},
                {'name': _("Original Amount"), 'class': 'number', 'title': _("Original Amount")}, # This is amount_currency (original)
            ]
            
            # Then the aged balance columns in foreign currency
            target_currency = current_company.currency_foreign_id or self.env.company.currency_foreign_id

            new_cols.append({
                'name': _("Total (USD)"),
                'class': 'number',
                'title': _("Total (USD)"),
                'currency_id': target_currency.id if target_currency else None,
            })
            
            age_buckets = [bucket for bucket in column_details['buckets'] if bucket != 'total']
            for bucket in age_buckets:
                new_cols.append({
                    'name': bucket,
                    'class': 'number',
                    'title': bucket,
                    'currency_id': target_currency.id if target_currency else None,
                })
            
            # The super _get_columns might add a final 'Total' column, but we already have it.
            # This logic might need fine-tuning based on the exact base Odoo _get_columns behavior.
            
            # For now, let's just make sure the `format_type` for currency columns is correct.
            # This is handled by `format_value` in `_get_lines`.
            # The `_get_columns` defines the header and general properties.

            # The default Odoo _get_columns in account_aged_partner_balance:
            # ['Date', 'Due Date', 'Journal Entry', 'Account', 'Original Amount', 'Not Due', '0-30', '31-60', '61-90', '91-120', '> 120', 'Total']
            # We need to ensure the number columns are flagged for foreign currency if usd_report.
            
            # Let's just adjust the `currency_id` for relevant columns.
            # Assuming 'Original Amount' (col 4), 'Not Due' (col 5), and subsequent aged buckets are numeric.
            
            usd_currency = current_company.currency_foreign_id or self.env.company.currency_foreign_id

            # Adjusting existing columns' currency_id
            for i, col in enumerate(cols):
                # The columns with amounts are typically 'amount', 'balance', and the aged buckets.
                # In aged balance, the columns are more descriptive: 'Not Due', '0-30', etc.
                # Assuming these are the ones we want to reflect in USD.
                # Based on the structure, cols[5] onwards are the aged amounts.
                # cols[4] is 'Original Amount'
                if i >= 4 and show_foreign_currency:
                    col['currency_id'] = usd_currency.id if usd_currency else None
            
            return cols
        
        return cols # Return original columns if not showing foreign currency

    # Overriding _compute_formula_batch_with_engine_domain to ensure 'warnings=None' is passed.
    def _compute_formula_batch_with_engine_domain(self, expression_id_list, domain, warnings=None):
        """ This method computes a batch of formulas that depends on the engine domain. """
        # Ensure warnings is always passed, even if it's None.
        return super()._compute_formula_batch_with_engine_domain(expression_id_list, domain, warnings=warnings)