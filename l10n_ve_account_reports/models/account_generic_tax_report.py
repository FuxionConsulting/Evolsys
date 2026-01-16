# -*- coding: utf-8 -*-
from odoo import models, api, fields
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class GenericTaxReportCustomHandler(models.AbstractModel):
    _inherit = 'account.generic.tax.report.handler'

    # -------------------------------------------------------------------------
    # GENERIC TAX REPORT COMPUTATION (DYNAMIC LINES)
    # -------------------------------------------------------------------------

    @api.model
    def _read_generic_tax_report_amounts_no_tax_details(self, report, options, options_by_column_group):
        """
        Overrides the method to include currency conversion for tax and base amounts
        based on the 'usd_report' option.
        """
        results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        # 1. Prepare options for currency table query
        conversion_date = options.get('date', {}).get('date_to')
        if not conversion_date:
            _logger.warning("No 'date_to' found in options for currency conversion in _read_generic_tax_report_amounts_no_tax_details. Using current date.")
            conversion_date = fields.Date.today()

        # Propagate 'usd_report' from context into options for deeper methods
        usd_report = self.env.context.get('usd_report', False)
        if 'usd_report' not in options: # Ensure options itself has it for consistency
            options['usd_report'] = usd_report

        company_ids_to_use = []
        if options.get('multi_company'):
            if isinstance(options['multi_company'], list):
                for mc_data in options['multi_company']:
                    if isinstance(mc_data, dict) and 'id' in mc_data:
                        company_ids_to_use.append(mc_data['id'])
                    elif isinstance(mc_data, int):
                        company_ids_to_use.append(mc_data)
            elif isinstance(options['multi_company'], int):
                company_ids_to_use = [options['multi_company']]
        
        if not company_ids_to_use:
            company_ids_to_use = [self.env.company.id]

        excluded_company_ids = options.get('excluded_company_ids', [])
        excluded_company_ids = [int(cid) for cid in excluded_company_ids if isinstance(cid, (int, str)) and str(cid).isdigit()]

        currency_table_options = options.copy()
        currency_table_options['multi_company'] = [{'id': cid} for cid in company_ids_to_use]
        currency_table_options['excluded_company_ids'] = excluded_company_ids
        
        _logger.info(f"[account_generic_tax_report] Calling _get_query_currency_table with options: {currency_table_options.get('multi_company')}, excluded: {currency_table_options.get('excluded_company_ids')}")

        ct_query, ct_params = self.env["res.currency"]._get_query_currency_table(
            currency_table_options,
            conversion_date,
        )

        all_params = list(ct_params)

        # 2. Fetch the group of taxes info (no currency conversion needed here)
        group_of_taxes_info = defaultdict(lambda: {'to_expand': False})
        
        # Use the company_ids_to_use from options as the parameter for the IN clause
        group_tax_query_params = [tuple(company_ids_to_use)]
        
        self._cr.execute(
            '''
                SELECT
                    group_tax.id,
                    group_tax.type_tax_use,
                    ARRAY_AGG(child_tax.id) AS child_tax_ids,
                    ARRAY_AGG(DISTINCT child_tax.type_tax_use) AS child_types
                FROM account_tax_filiation_rel group_tax_rel
                JOIN account_tax group_tax ON group_tax.id = group_tax_rel.parent_tax
                JOIN account_tax child_tax ON child_tax.id = group_tax_rel.child_tax
                WHERE group_tax.amount_type = 'group' AND group_tax.company_id IN %s
                GROUP BY group_tax.id
            ''',
            group_tax_query_params
        )
        for row in self._cr.dictfetchall():
            group_of_taxes_info[row['id']]['to_expand'] = 'none' in row['child_types']

        # 3. Iterate through column groups to build the main tax report queries
        for column_group_key, column_group_options in options_by_column_group.items():
            tables, where_clause, where_params = report._query_get(column_group_options, 'normal')
            
            # Use `usd_report` flag to conditionally apply currency conversion in the SQL query
            # We need to make sure the ct_query is joined correctly and used in the sums.
            
            # The original query was:
            # SUM(account_move_line.balance) AS tax_amount,
            # SUM(account_move_line.tax_base_amount) AS base_amount
            
            # Now, we will conditionally convert these amounts if usd_report is True.
            # We assume 'balance' holds the company currency amount, and 'amount_currency' is the foreign amount.
            # However, for tax reports, it's more about the `balance` field on the AML for the tax line,
            # which is already in the company's currency. If we want USD, we need to convert *that* balance.
            # And `tax_base_amount` is also in company currency.

            # We need to convert `account_move_line.balance` and `account_move_line.tax_base_amount`
            # to USD if `usd_report` is True, using `currency_table.rate` and company currency.
            # The 'currency_table.id' should match `account_move_line.company_currency_id` if we are converting
            # company currency to USD, or `account_move_line.currency_id` if we are converting
            # a foreign currency on the line to USD.
            # Given the context, we are trying to convert the report to USD *from company currency*.
            # So, we join on company_id and target currency.
            
            tax_amount_select = f"""
                SUM(
                    CASE WHEN %s THEN account_move_line.balance / currency_table.rate
                    ELSE account_move_line.balance
                    END
                ) AS tax_amount
            """
            base_amount_select = f"""
                SUM(
                    CASE WHEN %s THEN account_move_line.tax_base_amount / currency_table.rate
                    ELSE account_move_line.tax_base_amount
                    END
                ) AS base_amount
            """
            
            all_params.append(usd_report) # Parameter for tax_amount_select
            all_params.append(usd_report) # Parameter for base_amount_select
            all_params.extend(where_params) # Existing where clause params

            _logger.info(f"[account_generic_tax_report] Running query for column_group_key: {column_group_key}")
            _logger.info(f"[account_generic_tax_report] Query params: {all_params}")

            self._cr.execute(
                f'''
                    SELECT
                        tax.id AS tax_id,
                        group_tax.id AS group_tax_id,
                        tax.type_tax_use AS tax_type_tax_use,
                        group_tax.type_tax_use AS group_tax_type_tax_use,
                        {tax_amount_select},
                        {base_amount_select}
                    FROM {tables}
                    JOIN account_tax tax ON tax.id = account_move_line.tax_line_id
                    LEFT JOIN account_tax group_tax ON group_tax.id = tax.tax_group_id
                    LEFT JOIN account_move_line_account_tax_rel aml_tax_rel ON aml_tax_rel.account_move_line_id = account_move_line.id
                    LEFT JOIN account_tax account_tax_on_the_line ON account_tax_on_the_line.id = aml_tax_rel.account_tax_id
                    JOIN account_move account_move_line__move_id ON account_move_line__move_id.id = account_move_line.move_id
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id AND currency_table.id = account_move_line.company_currency_id
                    WHERE {where_clause}
                    AND account_move_line.tax_line_id IN %s
                    AND account_move_line__move_id.state = 'posted'
                    AND account_move_line.date BETWEEN %s AND %s
                    AND account_move_line.company_id IN %s
                    AND (
                        account_move_line__move_id.always_tax_exigible
                        OR account_move_line__move_id.tax_cash_basis_rec_id IS NOT NULL
                        OR tax.tax_exigibility != 'on_payment'
                    )
                    AND (
                        (group_tax.id IS NULL AND tax.type_tax_use IN ('sale', 'purchase'))
                        OR
                        (group_tax.id IS NOT NULL AND group_tax.type_tax_use IN ('sale', 'purchase'))
                    )
                    GROUP BY tax.id, group_tax.id
                ''',
                # Parameters for the main query
                tuple(all_params) + ( # Include all_params (ct_params, usd_report flags)
                    tuple(column_group_options['tax_ids']), # %s for tax_line_id IN
                    column_group_options['date']['date_from'], # %s for date_from
                    column_group_options['date']['date_to'], # %s for date_to
                    tuple(company_ids_to_use), # %s for company_id IN
                )
            )

            for row in self._cr.dictfetchall():
                # Manage group of taxes.
                tax_id = row['tax_id']
                if row['group_tax_id']:
                    tax_type_tax_use = row['group_tax_type_tax_use']
                    if not group_of_taxes_info[row['group_tax_id']]['to_expand']:
                        tax_id = row['group_tax_id']
                else:
                    tax_type_tax_use = row['group_tax_type_tax_use'] or row['tax_type_tax_use']

                results[tax_type_tax_use]['tax_amount'][column_group_key] += row['tax_amount']
                results[tax_type_tax_use]['base_amount'][column_group_key] += row['base_amount']
        
        return results

    @api.model
    def _read_generic_tax_report_amounts_with_tax_details(self, report, options, options_by_column_group):
        """
        This method is for when tax details are required. It would also need similar currency
        conversion logic if it performs SQL queries.
        Assuming it reuses parts of the logic or calls into methods that use `_get_query_currency_table`,
        it should be fine if the options are passed correctly.
        If it also performs direct SQL, it needs to be updated.
        Given the original snippet only showed `_read_generic_tax_report_amounts_no_tax_details`,
        I will assume this method (if it exists and performs direct SQL) will also need similar treatment.
        For now, let's include the existing method and ensure options are ready.
        """
        # (Copy original content of this method and adapt for currency if it also does direct SQL queries)
        # Placeholder: If this method performs SQL queries similar to the above,
        # it will also need the ct_query logic and conditional sums.
        # For now, we will simply call the super, assuming it handles it or does not require it.
        # If the original module had specific logic here, it needs to be re-inserted and adapted.
        
        # Propagate 'usd_report' from context into options for deeper methods
        usd_report = self.env.context.get('usd_report', False)
        if 'usd_report' not in options:
            options['usd_report'] = usd_report

        # Ensure multi_company and excluded_company_ids are formatted for consistency
        company_ids_to_format = []
        if options.get('multi_company'):
            if isinstance(options['multi_company'], list):
                for mc_data in options['multi_company']:
                    if isinstance(mc_data, dict) and 'id' in mc_data:
                        company_ids_to_format.append(mc_data['id'])
                    elif isinstance(mc_data, int):
                        company_ids_to_format.append(mc_data)
            elif isinstance(options['multi_company'], int):
                company_ids_to_format = [options['multi_company']]
        
        options['multi_company'] = [{'id': cid} for cid in company_ids_to_format] if company_ids_to_format else options.get('multi_company')

        if 'excluded_company_ids' in options and isinstance(options['excluded_company_ids'], list):
            options['excluded_company_ids'] = [int(cid) for cid in options['excluded_company_ids'] if isinstance(cid, (int, str)) and str(cid).isdigit()]
        else:
            options['excluded_company_ids'] = []
            
        _logger.info(f"[account_generic_tax_report] _read_generic_tax_report_amounts_with_tax_details options before super call: {options}")

        # This method is likely calling into _read_generic_tax_report_amounts_no_tax_details or similar.
        # If it has its own SQL, similar conversion is needed.
        # Given the previous context, the critical part is `_read_generic_tax_report_amounts_no_tax_details`.
        # I'll rely on the base Odoo implementation or existing module specific logic if there was any in this method.
        # If this method is implemented in your module, you might need to copy its original logic and apply similar currency conversions.
        # For now, returning super().
        return super()._read_generic_tax_report_amounts_with_tax_details(report, options, options_by_column_group)