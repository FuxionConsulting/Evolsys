# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _
from odoo.tools.misc import get_lang
import logging

_logger = logging.getLogger(__name__)

class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = "account.partner.ledger.report.handler"

    @api.model
    def _get_query_sums(self, options):
        """
        Overrides _get_query_sums to correctly pass options for currency table query
        and to include foreign currency calculations in the main query.
        """
        params = []
        queries = []
        report = self.env.ref("account_reports.partner_ledger_report")

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
        
        # If no specific companies are selected in options, default to the current company
        if not companies_for_currency_table:
            companies_for_currency_table = [self.env.company.id]

        excluded_company_ids = options.get('excluded_company_ids', [])
        excluded_company_ids = [int(cid) for cid in excluded_company_ids if isinstance(cid, (int, str)) and str(cid).isdigit()]

        currency_table_options = options.copy()
        currency_table_options['multi_company'] = [{'id': cid} for cid in companies_for_currency_table]
        currency_table_options['excluded_company_ids'] = excluded_company_ids
        
        _logger.info(f"[account_partner_ledger] Calling _get_query_currency_table with options: multi_company={currency_table_options.get('multi_company')}, excluded_company_ids={currency_table_options.get('excluded_company_ids')}")

        # Create the currency table.
        # Now, `_get_query_currency_table` expects `options` as the first argument.
        ct_query, ct_params = self.env["res.currency"]._get_query_currency_table(
            currency_table_options,
            conversion_date, # conversion_date is still passed as a separate argument
        )

        # Base query to get initial amounts, adapted for foreign currency
        # The original _get_sums_amount_rows_query is an internal method that builds part of the SELECT.
        # We need to make sure it includes foreign currency calculations.
        # The amounts_query needs to be rebuilt to include foreign currency calculations.
        # Odoo's default Partner Ledger handler uses `balance`, `debit`, `credit`, `amount_currency`.
        # We need to add `balance_foreign`, `debit_foreign`, `credit_foreign`.

        amounts_query = """
            SUM(CASE WHEN aml.debit > 0 THEN aml.debit ELSE 0 END) AS debit,
            SUM(CASE WHEN aml.credit > 0 THEN aml.credit ELSE 0 END) AS credit,
            SUM(aml.balance) AS balance,
            SUM(aml.amount_currency) AS amount_currency,
            SUM(CASE WHEN currency_table.rate IS NOT NULL THEN aml.balance / currency_table.rate ELSE 0 END) AS balance_foreign,
            SUM(CASE WHEN currency_table.rate IS NOT NULL THEN aml.debit / currency_table.rate ELSE 0 END) AS debit_foreign,
            SUM(CASE WHEN currency_table.rate IS NOT NULL THEN aml.credit / currency_table.rate ELSE 0 END) AS credit_foreign
        """
        
        all_params = list(ct_params) # Start with currency table params

        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, "normal")
            
            queries.append(
                f"""
                SELECT
                    account_move_line.partner_id                                          AS groupby,
                    %s                                                                    AS column_group_key,
                    {amounts_query}
                FROM {tables}
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                WHERE {where_clause}
                GROUP BY account_move_line.partner_id
            """
            )
            params.append(column_group_key)
            params.extend(where_params)
        
        all_params.extend(params) # Add query-specific params

        _logger.info(f"[account_partner_ledger] Final query params: {all_params}")
        _logger.info(f"[account_partner_ledger] Generated main queries (first one): {queries[0] if queries else 'No queries generated'}")

        return " UNION ALL ".join(queries), all_params

    # You might have other methods here that need adjustment,
    # such as _get_aml_lines which also constructs SQL.
    # The current code in the file snippets includes `_get_aml_lines` which is also critical.
    # Let's also adjust _get_aml_lines in the same go.

    def _get_aml_lines(self, options, partner_ids, offset=0, limit=None):
        """
        Overrides _get_aml_lines to correctly pass options for currency table query
        and to include foreign currency calculations.
        """
        rslt = {partner_id: [] for partner_id in partner_ids}
        rslt[None] = [] # For 'unknown partner'

        # Prepare conversion_date and currency_table_options similar to _get_query_sums
        conversion_date = options['date']['date_to']
        if isinstance(conversion_date, str):
            conversion_date = fields.Date.from_string(conversion_date)

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

        ct_query, ct_params = self.env["res.currency"]._get_query_currency_table(
            currency_table_options,
            conversion_date,
        )

        all_params = list(ct_params) # Start with currency table params
        
        queries = []
        
        report = self.env.ref("account_reports.partner_ledger_report")
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, "normal")

            # This part comes from the original _get_aml_lines, but with foreign currency columns added.
            queries.append(
                f"""
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name,
                    account_move_line.ref,
                    account_move_line.move_id.state,
                    account_move_line.amount_currency,
                    account_move_line.debit,
                    account_move_line.credit,
                    account_move_line.balance,
                    CASE WHEN currency_table.rate IS NOT NULL THEN account_move_line.balance / currency_table.rate ELSE 0 END AS balance_foreign,
                    CASE WHEN currency_table.rate IS NOT NULL THEN account_move_line.debit / currency_table.rate ELSE 0 END AS debit_foreign,
                    CASE WHEN currency_table.rate IS NOT NULL THEN account_move_line.credit / currency_table.rate ELSE 0 END AS credit_foreign,
                    account_move_line.partner_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    account_move_line.currency_id,
                    account_move_line.company_id,
                    account.code AS account_code,
                    account.name AS account_name,
                    journal.code AS journal_code,
                    journal.name AS journal_name,
                    %s AS column_group_key,
                    'directly_linked_aml' AS key
                FROM {tables}
                JOIN account_account account ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal ON journal.id = account_move_line.journal_id
                LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id AND currency_table.id = account_move_line.currency_id
                WHERE {where_clause}
                AND account_move_line.partner_id IN %s
                AND account.id IN (SELECT id FROM account_account WHERE account_type IN ('asset_receivable', 'liability_payable'))
                ORDER BY account_move_line.date, account_move_line.id
            """
            )
            all_params.extend(where_params)
            all_params.append(column_group_key)
            all_params.append(tuple(partner_ids))

        # This part for `indirectly_linked_aml` also needs the ct_query and foreign currency.
        # This is a complex part from Odoo's core logic for reconciliation.
        # Assuming the original module kept this part, we need to adapt it.

        # The snippet of `_get_aml_lines` you provided doesn't include the full `indirectly_linked_aml` logic.
        # I will reconstruct it based on typical Odoo partner ledger, including the foreign currency.

        # Add the 'indirectly_linked_aml' queries
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            tables, where_clause, where_params = report._query_get(column_group_options, 'normal')

            # This query is for partially reconciled amounts
            queries.append(f"""
                SELECT
                    aml.id,
                    aml.date,
                    aml.date_maturity,
                    aml.name,
                    aml.ref,
                    aml.move_id.state,
                    aml.amount_currency,
                    aml.debit,
                    aml.credit,
                    aml.balance,
                    CASE WHEN currency_table.rate IS NOT NULL THEN aml.balance / currency_table.rate ELSE 0 END AS balance_foreign,
                    CASE WHEN currency_table.rate IS NOT NULL THEN aml.debit / currency_table.rate ELSE 0 END AS debit_foreign,
                    CASE WHEN currency_table.rate IS NOT NULL THEN aml.credit / currency_table.rate ELSE 0 END AS credit_foreign,
                    aml.partner_id,
                    aml.account_id,
                    aml.payment_id,
                    aml.currency_id,
                    aml.company_id,
                    account.code AS account_code,
                    account.name AS account_name,
                    journal.code AS journal_code,
                    journal.name AS journal_name,
                    %s AS column_group_key,
                    'indirectly_linked_aml' AS key
                FROM account_partial_reconcile partial
                JOIN account_move_line aml ON aml.id = partial.debit_move_id OR aml.id = partial.credit_move_id
                JOIN account_move move ON move.id = aml.move_id
                JOIN account_account account ON account.id = aml.account_id
                LEFT JOIN account_journal journal ON journal.id = aml.journal_id
                LEFT JOIN {ct_query} ON currency_table.company_id = aml.company_id AND currency_table.id = aml.currency_id
                WHERE {where_clause}
                AND (partial.debit_move_id IN (SELECT id FROM account_move_line WHERE partner_id IN %s)
                     OR partial.credit_move_id IN (SELECT id FROM account_move_line WHERE partner_id IN %s))
                AND account.id IN (SELECT id FROM account_account WHERE account_type IN ('asset_receivable', 'liability_payable'))
                AND partial.max_date BETWEEN %s AND %s
                ORDER BY aml.date, aml.id
            """)
            all_params.extend(where_params)
            all_params.append(column_group_key)
            all_params.append(tuple(partner_ids))
            all_params.append(tuple(partner_ids))
            all_params.append(column_group_options['date']['date_from'])
            all_params.append(column_group_options['date']['date_to'])


        query = "(\n" + "\n) UNION ALL (\n".join(queries) + "\n)"

        if offset:
            query += " OFFSET %s "
            all_params.append(offset)

        if limit:
            query += " LIMIT %s "
            all_params.append(limit)
        
        _logger.info(f"[account_partner_ledger] Full _get_aml_lines query (first query in UNION ALL): {query}")
        _logger.info(f"[account_partner_ledger] Params for _get_aml_lines: {all_params}")


        self.env.cr.execute(query, all_params)
        for aml_result in self.env.cr.dictfetchall():
            if aml_result["key"] == "indirectly_linked_aml":
                # Append the line to the partner found through the reconciliation.
                if aml_result["partner_id"] in rslt:
                    rslt[aml_result["partner_id"]].append(aml_result)

                # Balance it with an additional line in the Unknown Partner section but having reversed amounts.
                if None in rslt:
                    rslt[None].append(
                        {
                            **aml_result,
                            "debit": aml_result["credit"],
                            "credit": aml_result["debit"],
                            "balance": -aml_result["balance"],
                            "debit_foreign": aml_result["credit_foreign"],
                            "credit_foreign": aml_result["debit_foreign"],
                            "balance_foreign": -aml_result["balance_foreign"],
                        }
                    )
            else:
                rslt[aml_result["partner_id"]].append(aml_result)
        return rslt