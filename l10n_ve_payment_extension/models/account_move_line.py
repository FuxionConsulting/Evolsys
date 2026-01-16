# user/l10n_ve_payment_extension/models/account_move_line.py
from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError, ValidationError
from odoo.tools import frozendict, formatLang, format_date, Query
from datetime import date, timedelta
import traceback
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    not_foreign_recalculate = fields.Boolean()
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate", store=True, index=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
        readonly=False,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_price_total = fields.Monetary(
        help="Foreign Total of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )
    amount_currency = fields.Monetary(precompute=False)

    # Report fields
    foreign_debit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
    )
    foreign_credit = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_debit_credit",
        store=True,
    )
    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_balance",
        inverse="_inverse_foreign_balance",
        store=True,
    )

    foreign_debit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign debit field",
    )
    foreign_credit_adjustment = fields.Monetary(
        currency_field="foreign_currency_id",
        help="When setted, this field will be used to fill the foreign credit field",
    )

    @api.onchange("amount_currency", "currency_id")
    def _inverse_amount_currency(self):
        """
        Inverse for amount_currency: robust handling of rates to avoid ZeroDivisionError
        and avoid raising blocking UserError when a rate is missing. Use sensible fallbacks.
        """
        for line in self:
            try:
                # Case: currency equals company currency -> balance equals amount_currency
                if (
                    line.currency_id == line.company_id.currency_id
                    and line.balance != line.amount_currency
                ):
                    line.balance = line.amount_currency
                    continue

                # If currency differs and it's not an invoice, compute using available rate
                if (
                    line.currency_id != line.company_id.currency_id
                    and not line.move_id.is_invoice(True)
                    and not self.env.is_protected(self._fields["balance"], line)
                ):
                    # Prefer foreign_inverse_rate for known special currencies
                    vef = self.env.ref("base.VEF")
                    usd = self.env.ref("base.USD")
                    if line.currency_id in (vef, usd):
                        rate = getattr(line, "foreign_inverse_rate", None) or getattr(line, "currency_rate", None) or 1.0
                    else:
                        rate = getattr(line, "currency_rate", None) or getattr(line, "foreign_inverse_rate", None) or 1.0

                    # Protect against zero or None
                    if not rate or rate == 0:
                        _logger.warning("Line %s: inverse_amount_currency fallback rate used (1.0)", line.id)
                        rate = 1.0

                    line.balance = line.company_id.currency_id.round(
                        line.amount_currency / rate
                    )
                    continue

                # If currency differs and it's a payment, use payment's foreign_inverse_rate if available
                if (
                    line.currency_id != line.company_id.currency_id
                    and not line.move_id.is_invoice(True)
                    and line.move_id.payment_id
                ):
                    fir = getattr(line.move_id.payment_id, "foreign_inverse_rate", None) or 0.0
                    if fir and line.amount_currency:
                        line.balance = line.company_id.currency_id.round(
                            line.amount_currency / fir
                        )
                    else:
                        # fallback to move rates or 1.0 to avoid blocking
                        fallback = getattr(line.move_id, "foreign_inverse_rate", None) or getattr(line.move_id, "foreign_rate", None) or 1.0
                        if not fallback or fallback == 0:
                            fallback = 1.0
                        line.balance = line.company_id.currency_id.round(
                            line.amount_currency / fallback
                        )
                    continue
            except Exception:
                _logger.exception("Error in _inverse_amount_currency for line %s", line.id)
                # As last resort, do not change balance to avoid corrupting data
                continue

    @api.depends("product_id", "move_id.name")
    def _compute_name(self):
        lines_without_name = self.filtered(lambda l: not l.name)
        res = super(AccountMoveLine, lines_without_name)._compute_name()
        for line in self.filtered(
            lambda l: l.move_type in ("out_invoice", "out_receipt")
            and l.account_id.account_type == "asset_receivable"
        ):
            line.name = line.move_id.name
        return res

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
            # Ensure foreign_inverse_rate has a sensible fallback
            fir = getattr(line, "foreign_inverse_rate", None) or 1.0
            line.foreign_price = (line.price_unit or 0.0) * fir

    @api.depends("foreign_price", "quantity", "discount", "tax_ids", "price_unit")
    def _compute_foreign_subtotal(self):
        for line in self:
            try:
                line_discount_price_unit = (line.foreign_price or 0.0) * (
                    1 - (line.discount or 0.0) / 100.0
                )
                foreign_subtotal = line_discount_price_unit * (line.quantity or 1.0)

                if line.tax_ids:
                    taxes_res = line.tax_ids.compute_all(
                        line_discount_price_unit,
                        quantity=line.quantity,
                        currency=line.foreign_currency_id,
                        product=line.product_id,
                        partner=line.partner_id,
                        is_refund=line.is_refund,
                    )
                    line.foreign_subtotal = taxes_res.get("total_excluded", 0.0)
                    line.foreign_price_total = taxes_res.get("total_included", 0.0)
                else:
                    line.foreign_price_total = line.foreign_subtotal = foreign_subtotal
            except Exception:
                _logger.exception("Error computing foreign subtotal for line %s", line.id)
                line.foreign_subtotal = 0.0
                line.foreign_price_total = 0.0

    @api.depends(
        "debit",
        "credit",
        "foreign_subtotal",
        "foreign_balance",
        "amount_currency",
        "not_foreign_recalculate",
        "foreign_debit_adjustment",
        "foreign_credit_adjustment",
    )
    def _compute_foreign_debit_credit(self):
        for line in self:
            if line.not_foreign_recalculate:
                continue

            # Payment term or tax display types: use foreign_balance
            if line.display_type in ("payment_term", "tax"):
                line.foreign_debit = (
                    abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
                )
                line.foreign_credit = (
                    abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
                )
                continue

            if line.display_type in ("line_section", "line_note"):
                line.foreign_debit = line.foreign_credit = 0.0
                continue

            if line.foreign_debit_adjustment:
                line.foreign_debit = abs(line.foreign_debit_adjustment)
                continue

            if line.foreign_credit_adjustment:
                line.foreign_credit = abs(line.foreign_credit_adjustment)
                continue

            # If the line currency equals the company's foreign currency and amount_currency is set
            if (
                line.currency_id == line.company_id.currency_foreign_id
                and line.amount_currency
            ):
                line.foreign_debit = (
                    abs(line.amount_currency) if line.amount_currency > 0 else 0.0
                )
                line.foreign_credit = (
                    abs(line.amount_currency) if line.amount_currency < 0 else 0.0
                )
                continue

            # Retention payments: use retention_foreign_amount if present
            if (
                line.move_id.payment_id
                and "retention_foreign_amount" in self.env["account.payment"]._fields
                and line.move_id.payment_id.is_retention
            ):
                try:
                    if not line.currency_id.is_zero(line.debit):
                        line.foreign_debit = line.move_id.payment_id.retention_foreign_amount or 0.0
                        continue
                    if not line.currency_id.is_zero(line.credit):
                        line.foreign_credit = line.move_id.payment_id.retention_foreign_amount or 0.0
                        continue
                except Exception:
                    _logger.exception("Error computing retention foreign debit/credit for line %s", line.id)

            # Not invoice: compute using move lines and rates
            if not line.move_id.is_invoice(include_receipts=True):
                foreign_lines = line.move_id.line_ids.filtered(
                    lambda l: l.currency_id == l.company_id.currency_foreign_id
                )
                currency_lines = line.move_id.line_ids.filtered(
                    lambda l: l.currency_id == l.company_id.currency_id
                )

                balance = sum((foreign_lines).mapped("amount_currency"))
                if balance and len(currency_lines) == 1:
                    line.foreign_debit = abs(balance) if balance < 0 else 0.0
                    line.foreign_credit = abs(balance) if balance > 0 else 0.0
                    continue

                # Use foreign_inverse_rate with fallback
                fir = getattr(line, "foreign_inverse_rate", None) or 1.0
                line.foreign_debit = line.debit * fir
                line.foreign_credit = line.credit * fir
                continue

            # Product display type: use foreign_subtotal
            if line.display_type == "product":
                sign = line.move_id.direction_sign * -1
                amount = (line.foreign_subtotal or 0.0) * sign
                line.foreign_debit = abs(amount) if amount < 0 else 0.0
                line.foreign_credit = abs(amount) if amount > 0 else 0.0
                continue

            # Default: use foreign_balance
            line.foreign_debit = (
                abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
            )
            line.foreign_credit = (
                abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
            )

    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
            line.foreign_balance = line.foreign_debit - line.foreign_credit

    def _inverse_foreign_balance(self):
        for line in self:
            line.foreign_debit = (
                abs(line.foreign_balance) if line.foreign_balance > 0 else 0.0
            )
            line.foreign_credit = (
                abs(line.foreign_balance) if line.foreign_balance < 0 else 0.0
            )

    def _prepare_analytic_distribution_line(
        self, distribution, account_id, distribution_on_each_plan
    ):
        """
        This method adds the foreign_amount in the foreign currency to the analytical account line
        """
        self.ensure_one()
        res = super()._prepare_analytic_distribution_line(
            distribution, account_id, distribution_on_each_plan
        )
        account_id = int(account_id)
        account = self.env["account.analytic.account"].browse(account_id)
        distribution_plan = (
            distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
        )
        decimal_precision = self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        )
        if (
            float_compare(distribution_plan, 100, precision_digits=decimal_precision)
            == 0
        ):
            foreign_amount = (
                -self.foreign_balance
                * (100 - distribution_on_each_plan.get(account.root_plan_id, 0))
                / 100.0
            )
        else:
            foreign_amount = -self.foreign_balance * distribution / 100.0

        res["foreign_amount"] = foreign_amount
        return res

    @api.model
    def _prepare_move_line_residual_amounts(
        self,
        aml_values,
        counterpart_currency,
        shadowed_aml_values=None,
        other_aml_values=None,
    ):
        """Prepare the available residual amounts for each currency.
        Robust handling of rates to avoid division by zero and to provide fallbacks.
        """
        def is_payment(aml):
            return aml.move_id.payment_id or aml.move_id.statement_line_id

        def get_odoo_rate(aml, other_aml, currency):
            if forced_rate := self._context.get("forced_rate_from_register_payment"):
                return forced_rate
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                if aml.move_id.payment_id:
                    # Use payment's foreign_inverse_rate if available, else fallback
                    rate = getattr(aml.move_id.payment_id, "foreign_inverse_rate", None)
                    if not rate or rate == 0:
                        rate = getattr(aml.move_id, "foreign_inverse_rate", None) or getattr(aml.move_id, "foreign_rate", None) or 1.0
                    return rate
                return get_accounting_rate(other_aml, currency)
            if aml.move_id.is_invoice(include_receipts=True):
                exchange_rate_date = aml.move_id.invoice_date
            else:
                exchange_rate_date = aml._get_reconciliation_aml_field_value(
                    "date", shadowed_aml_values
                )
            try:
                rate = currency._get_conversion_rate(
                    aml.company_currency_id, currency, aml.company_id, exchange_rate_date
                )
                if not rate or rate == 0:
                    rate = getattr(aml.move_id, "foreign_rate", None) or 1.0
                return rate
            except Exception:
                _logger.exception("Error getting odoo rate for aml %s", aml.id)
                return 1.0

        def get_accounting_rate(aml, currency):
            if forced_rate := self._context.get("forced_rate_from_register_payment"):
                return forced_rate
            balance = aml._get_reconciliation_aml_field_value(
                "balance", shadowed_aml_values
            )
            amount_currency = aml._get_reconciliation_aml_field_value(
                "amount_currency", shadowed_aml_values
            )
            if not aml.company_currency_id.is_zero(balance) and not currency.is_zero(
                amount_currency
            ):
                try:
                    rate = abs(amount_currency / balance)
                    if not rate or rate == 0:
                        return 1.0
                    return rate
                except Exception:
                    _logger.exception("Error computing accounting rate for aml %s", aml.id)
                    return 1.0

        aml = aml_values["aml"]
        other_aml = (other_aml_values or {}).get("aml")
        remaining_amount_curr = aml_values["amount_residual_currency"]
        remaining_amount = aml_values["amount_residual"]
        company_currency = aml.company_currency_id
        currency = aml._get_reconciliation_aml_field_value(
            "currency_id", shadowed_aml_values
        )
        account = aml._get_reconciliation_aml_field_value(
            "account_id", shadowed_aml_values
        )
        has_zero_residual = company_currency.is_zero(remaining_amount)
        has_zero_residual_currency = currency.is_zero(remaining_amount_curr)
        is_rec_pay_account = account.account_type in (
            "asset_receivable",
            "liability_payable",
        )

        available_residual_per_currency = {}

        if not has_zero_residual:
            available_residual_per_currency[company_currency] = {
                "residual": remaining_amount,
                "rate": 1,
            }
        if currency != company_currency and not has_zero_residual_currency:
            available_residual_per_currency[currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency) or 1.0,
            }

        if (
            currency == company_currency
            and is_rec_pay_account
            and not has_zero_residual
            and counterpart_currency != company_currency
        ):
            rate = get_odoo_rate(aml, other_aml, counterpart_currency) or 1.0
            residual_in_foreign_curr = counterpart_currency.round(
                remaining_amount * rate
            )
            if not counterpart_currency.is_zero(residual_in_foreign_curr):
                available_residual_per_currency[counterpart_currency] = {
                    "residual": residual_in_foreign_curr,
                    "rate": rate,
                }
        elif (
            currency == counterpart_currency
            and currency != company_currency
            and not has_zero_residual_currency
        ):
            available_residual_per_currency[counterpart_currency] = {
                "residual": remaining_amount_curr,
                "rate": get_accounting_rate(aml, currency) or 1.0,
            }
        return available_residual_per_currency

    @api.model
    def abs_amount_lines_ids_adjust(self):
        for line in self:
            line.write(
                {
                    "foreign_debit_adjustment": abs(line.foreign_debit_adjustment),
                    "foreign_credit_adjustment": abs(line.foreign_credit_adjustment),
                    "foreign_debit": abs(line.foreign_debit),
                    "foreign_credit": abs(line.foreign_credit),
                }
            )

    @api.depends(
        "foreign_inverse_rate",
        "foreign_currency_id",
        "foreign_rate",
        "foreign_price",
    )
    def _compute_all_tax(self):
        res = super(AccountMoveLine, self)._compute_all_tax()
        for line in self:
            try:
                sign = line.move_id.direction_sign

                if line.display_type == "product" and line.move_id.is_invoice(True):
                    amount_currency = sign * line.foreign_price * (1 - (line.discount or 0.0) / 100.0)
                    handle_price_include = True
                    quantity = line.quantity
                else:
                    # Use move foreign_inverse_rate as fallback if line.foreign_inverse_rate missing
                    fir = getattr(line.move_id, "foreign_inverse_rate", None) or 1.0
                    amount_currency = (line.amount_currency or 0.0) * fir
                    handle_price_include = False
                    quantity = 1

                compute_all_currency = line.tax_ids.compute_all(
                    amount_currency,
                    currency=line.foreign_currency_id,
                    quantity=quantity,
                    product=line.product_id,
                    partner=line.move_id.partner_id or line.partner_id,
                    is_refund=line.is_refund,
                    handle_price_include=handle_price_include,
                    include_caba_tags=line.move_id.always_tax_exigible,
                    fixed_multiplicator=sign,
                )

                for tax in compute_all_currency.get("taxes", []):
                    for key in list(line.compute_all_tax.keys()):
                        if not key.get("tax_repartition_line_id", False):
                            continue

                        if tax.get("tax_repartition_line_id") == key.get("tax_repartition_line_id"):
                            line.compute_all_tax[key]["foreign_balance"] = tax.get("amount", 0.0)
            except Exception:
                _logger.exception("Error in _compute_all_tax for line %s", line.id)
        return res

    @api.onchange("quantity")
    def _onchange_quantity(self):
        if self.quantity < 0:
            raise ValidationError(_("The quantity entered cannot be negative"))

    @api.onchange("price_unit")
    def _onchange_price_unit(self):
        if self.price_unit < 0:
            raise ValidationError(_("The price entered cannot be negative"))
