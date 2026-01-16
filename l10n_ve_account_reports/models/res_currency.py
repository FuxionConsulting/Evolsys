# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, float_round
import datetime
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _get_query_currency_table(self, options, conversion_date):
        """
        Generates the SQL query for the currency conversion table.
        This version is adapted to handle 'usd_report' context and company filtering
        via the 'options' dictionary, as the Odoo 17 base might not accept
        'companies'/'excluded_company_ids' as direct keyword arguments in some contexts.

        :param options: A dictionary containing report options, including:
            - 'multi_company': A list of dicts [{'id': company_id}, ...] or list of ids,
                                  representing companies to include.
            - 'excluded_company_ids': A list of company IDs to exclude.
        :param conversion_date: The date for which to get the currency rates.
        :return: A string representing the SQL query for the currency table.
        """
        # Extract companies and excluded_company_ids from options
        company_ids = []
        if options.get('multi_company'):
            # multi_company can be a list of {'id': X} or just a list of IDs
            if isinstance(options['multi_company'], list):
                for mc_data in options['multi_company']:
                    if isinstance(mc_data, dict) and 'id' in mc_data:
                        company_ids.append(mc_data['id'])
                    elif isinstance(mc_data, int):
                        company_ids.append(mc_data)
            elif isinstance(options['multi_company'], int):
                company_ids.append(options['multi_company'])
        
        # If no specific companies are selected, default to the current company
        if not company_ids:
            company_ids = [self.env.company.id]

        excluded_company_ids = options.get('excluded_company_ids', [])
        excluded_company_ids = [int(cid) for cid in excluded_company_ids if isinstance(cid, (int, str)) and str(cid).isdigit()]


        # Ensure unique and valid company IDs, excluding those in excluded_company_ids
        final_company_ids = list(set(company_ids) - set(excluded_company_ids))
        if not final_company_ids:
            # Fallback if all companies are excluded or none are selected after filtering
            final_company_ids = [self.env.company.id]
        
        _logger.info(f"[_get_query_currency_table] Final company_ids for query: {final_company_ids}")
        _logger.info(f"[_get_query_currency_table] Excluded company_ids: {excluded_company_ids}")
        _logger.info(f"[_get_query_currency_table] Conversion date: {conversion_date}")
        _logger.info(f"[_get_query_currency_table] usd_report context: {self.env.context.get('usd_report', False)}")

        # Convert conversion_date to string for SQL
        date_str = conversion_date.strftime(DEFAULT_SERVER_DATE_FORMAT)

        # Base currency table query (standard Odoo approach)
        # This query typically returns the rate of each currency to the *company's* currency.
        # We need to adapt it if 'usd_report' is active.
        query = """
            SELECT
                currency.id AS id,
                currency.decimal_places AS decimal_places,
                currency.active AS active,
                currency.symbol AS symbol,
                currency.position AS position,
                currency.name AS name,
                currency.full_name AS full_name,
                currency.rounding AS rounding,
                currency.date_format AS date_format,
                COALESCE(rates.rate, 1) AS rate,
                company.id AS company_id
            FROM res_currency currency
            JOIN res_company company ON company.id IN %s
            LEFT JOIN (
                SELECT
                    r.currency_id,
                    r.company_id,
                    r.rate
                FROM res_currency_rate r
                WHERE r.name <= %s AND r.company_id IN %s
                ORDER BY r.name DESC, r.currency_id, r.company_id
            ) rates ON rates.currency_id = currency.id AND rates.company_id = company.id
            WHERE currency.active = TRUE
        """
        query_params = [
            tuple(final_company_ids), # for company.id IN %s
            date_str, # for r.name <= %s
            tuple(final_company_ids), # for r.company_id IN %s
        ]

        # --- Specific logic for 'usd_report' ---
        if self.env.context.get('usd_report', False):
            _logger.info("[_get_query_currency_table] usd_report is TRUE. Adjusting rates for foreign currency report.")
            # When usd_report is True, the goal is to show all values in USD.
            # This means the rate in the currency table should convert the source currency
            # to the company's foreign currency (usually USD).
            # So, rate = (rate_to_company_currency) / (rate_of_foreign_currency_to_company_currency)
            # OR, more directly, rate = rate_from_source_to_foreign_currency.

            # The current USD logic in the provided code is complex; let's try to align it
            # with standard Odoo rate calculation (currency_to_company_currency).
            # Then, if we want USD values, we'll need to divide by the USD rate.

            # Let's adjust the query to provide rates relative to `currency_foreign_id`
            # when `usd_report` is true.

            # Here we assume that `currency_foreign_id` is the target currency (e.g., USD).
            # The rate will be `source_currency_value / target_currency_value`.
            # So, if target is USD:
            # - If source is VEF, rate = VEF_per_USD
            # - If source is USD, rate = 1
            # - If source is EUR, rate = EUR_per_USD

            # To achieve this: we need the rate of each currency to the *foreign* currency.
            # We can do this by first getting the rates to the company's currency,
            # and then normalizing by the rate of the foreign currency to the company's currency.

            query = """
                SELECT
                    currency.id AS id,
                    currency.decimal_places AS decimal_places,
                    currency.active AS active,
                    currency.symbol AS symbol,
                    currency.position AS position,
                    currency.name AS name,
                    currency.full_name AS full_name,
                    currency.rounding AS rounding,
                    currency.date_format AS date_format,
                    CASE
                        -- If the source currency is the foreign currency itself, rate is 1
                        WHEN currency.id = company.currency_foreign_id THEN 1.0
                        -- If the foreign currency is the company's main currency, use rate from source to company currency
                        WHEN company.currency_foreign_id = company.currency_id THEN COALESCE(rates.rate, 1.0)
                        -- Otherwise, convert source to company currency, then company currency to foreign currency
                        ELSE COALESCE(rates.rate, 1.0) / COALESCE(foreign_rates.rate, 1.0)
                    END AS rate,
                    company.id AS company_id
                FROM res_currency currency
                JOIN res_company company ON company.id IN %s
                LEFT JOIN (
                    -- Rates of other currencies to the company's main currency
                    SELECT
                        r.currency_id,
                        r.company_id,
                        r.rate
                    FROM res_currency_rate r
                    WHERE r.name <= %s AND r.company_id IN %s
                    ORDER BY r.name DESC, r.currency_id, r.company_id
                ) rates ON rates.currency_id = currency.id AND rates.company_id = company.id
                LEFT JOIN (
                    -- Rate of the foreign currency (e.g., USD) to the company's main currency (e.g., VEF)
                    SELECT
                        r.currency_id,
                        r.company_id,
                        r.rate
                    FROM res_currency_rate r
                    WHERE r.name <= %s AND r.company_id IN %s
                    ORDER BY r.name DESC, r.currency_id, r.company_id
                ) foreign_rates ON foreign_rates.currency_id = company.currency_foreign_id AND foreign_rates.company_id = company.id
                WHERE currency.active = TRUE
            """
            query_params = [
                tuple(final_company_ids), # for company.id IN %s (main join)
                date_str, # for rates.r.name <= %s
                tuple(final_company_ids), # for rates.r.company_id IN %s
                date_str, # for foreign_rates.r.name <= %s
                tuple(final_company_ids), # for foreign_rates.r.company_id IN %s
            ]
        
        # Finally, filter by active currencies
        # Note: 'currency.active = TRUE' is already in the WHERE clause.

        # Returning the SQL query string
        # The query will be used in a JOIN as: JOIN ({query}) currency_table ON ...
        # So we need to return the full SELECT statement without final semicolon.
        return f"({query}) AS currency_table", query_params