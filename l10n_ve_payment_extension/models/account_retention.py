from odoo import api, models, fields, Command, _
from datetime import datetime
import re
from odoo.exceptions import UserError, ValidationError
from ..utils.utils_retention import load_retention_lines, search_invoices_with_taxes
from collections import defaultdict
import json
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _check_company_auto = True

    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_foreign_id.id,
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF"),
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Type retention",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        help="Social reason",
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Voucher Date",
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Accounting Date",
        help=(
            "Date of arrival of the document and date to be used to make the accounting record."
            " Keep blank to use current date."
        ),
    )
    allowed_lines_move_ids = fields.Many2many(
        "account.move",
        compute="_compute_allowed_lines_move_ids",
        help=(
            "Technical field to store the allowed move types for the ISLR retention lines. This is"
            " used to filter the moves that can be selected in the ISLR retention lines."
        ),
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        help="Retentions",
    )
    
    code_visible = fields.Boolean(related="company_id.code_visible")
    
    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
    )

    total_invoice_amount = fields.Float(
        string="Taxable Income (Local)",
        compute="_compute_totals",
        help="Taxable Income Total in company currency",
        store=True,
    )
    total_iva_amount = fields.Float(
        string="Total IVA (Local)",
        compute="_compute_totals",
        store=True,
    )
    total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )

    foreign_total_invoice_amount = fields.Float(
        string="Taxable Income (Foreign)",
        compute="_compute_totals",
        help="Taxable Income Total in invoice foreign currency",
        store=True,
    )
    foreign_total_iva_amount = fields.Float(
        string="Total IVA (Foreign)",
        compute="_compute_totals",
        store=True,
    )
    foreign_total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )
    original_lines_per_invoice_counter = fields.Char(
        help=(
            "Technical field to store the quantity of retention lines per invoice before the user"
            " changes them. This is used to know if the user has deleted the retention lines when"
            " the invoice is changed, in order to delete all the other lines of the same invoice"
            " that the one that just has been deleted."
        )
    )

    @api.depends("type", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund")
                if retention.type == "in_invoice"
                else ("out_invoice", "out_refund")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("partner_id", "=", retention.partner_id.id),
                ("move_type", "in", allowed_types),
            ]
            
            retention.allowed_lines_move_ids = self.env["account.move"].search(domain)

    @api.depends(
        "retention_line_ids.invoice_amount",
        "retention_line_ids.iva_amount",
        "retention_line_ids.retention_amount",
        "retention_line_ids.foreign_invoice_amount",
        "retention_line_ids.foreign_iva_amount",
        "retention_line_ids.foreign_retention_amount",
    )
    def _compute_totals(self):
        for retention in self:
            retention.total_invoice_amount = 0
            retention.total_iva_amount = 0
            retention.total_retention_amount = 0
            retention.foreign_total_invoice_amount = 0
            retention.foreign_total_iva_amount = 0
            retention.foreign_total_retention_amount = 0

            for line in retention.retention_line_ids:
                if line.move_id.move_type in ("in_refund", "out_refund"):
                    retention.total_invoice_amount -= float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount -= float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount -= float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount -= float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount -= float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount -= float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                else:
                    retention.total_invoice_amount += float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount += float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount += float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount += float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount += float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount += float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes for IVA retentions
        that are not posted.
        """
        self._validate_retention_journals()
        for retention in self.filtered(
            lambda r: (r.state, r.type_retention) == ("draft", "iva") and r.partner_id
        ):
            if retention.type == "in_invoice":
                result = retention._load_retention_lines_for_iva_supplier_retention()
            else:
                result = retention._load_retention_lines_for_iva_customer_retention()
            return result

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        self.date_accounting = fields.Date.today()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_refund", "in_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted"))
            )
        )

        _logger.info("Retention supplier: invoice_count=%s partner=%s company=%s",
                     len(invoices_with_taxes), getattr(self.partner_id, 'id', None), getattr(self.company_id, 'id', None))

        if not invoices_with_taxes:
            _logger.warning("No invoices with taxes found for supplier retention (partner=%s).", getattr(self.partner_id, 'id', None))
            return {
                "warning": {
                    "title": _("No invoices with taxes"),
                    "message": _(
                        "No invoices with taxes to be retained for the supplier. "
                        "No retention lines were generated automatically."
                    ),
                },
                "value": {},
            }

        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self)

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter),
            }
        }

    def _load_retention_lines_for_iva_customer_retention(self):
        self.ensure_one()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_refund", "out_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted"))
            )
        )

        _logger.info("Retention customer: invoice_count=%s partner=%s company=%s",
                     len(invoices_with_taxes), getattr(self.partner_id, 'id', None), getattr(self.company_id, 'id', None))

        if not invoices_with_taxes:
            _logger.warning("No invoices with taxes found for customer retention (partner=%s).", getattr(self.partner_id, 'id', None))
            return {
                "warning": {
                    "title": _("No invoices with taxes"),
                    "message": _(
                        "No invoices with taxes to be retained for the customer. "
                        "No retention lines were generated automatically."
                    ),
                },
                "value": {},
            }

        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self)

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter),
            }
        }
    
    def compute_retention_lines_data(self, invoice):
        """
        Calcula y devuelve los diccionarios de valores para crear las líneas de retención de IVA
        basándose en los tax_totals de la factura. Maneja varios formatos de tax_totals y hace
        fallback a agrupar por tax.name desde invoice.line_ids si no hay tax_totals.
        """
        retention_lines_data = []

        _logger.debug(
            "compute_retention_lines_data: invoice=%s company=%s currency=%s tax_totals=%s",
            getattr(invoice, "id", False),
            getattr(invoice.company_id, "id", False),
            getattr(invoice.currency_id, "name", False),
            getattr(invoice, "tax_totals", None),
        )

        tax_groups = []
        if getattr(invoice, "tax_totals", None):
            try:
                tt = invoice.tax_totals
                gbs = None
                if isinstance(tt, dict):
                    gbs = tt.get("groups_by_subtotal") or tt.get("groups_by_tax")
                if gbs:
                    if isinstance(gbs, dict):
                        for v in gbs.values():
                            if isinstance(v, list):
                                tax_groups.extend(v)
                            elif isinstance(v, dict):
                                tax_groups.append(v)
                    elif isinstance(gbs, list):
                        tax_groups.extend(gbs)
                if not tax_groups and isinstance(tt, list):
                    tax_groups.extend(tt)
            except Exception:
                _logger.debug("Unexpected structure in invoice.tax_totals for invoice %s", getattr(invoice, "id", False), exc_info=True)

        if not tax_groups:
            groups = {}
            for line in invoice.line_ids:
                for tax in line.tax_ids:
                    key = tax.name or "IVA"
                    g = groups.setdefault(key, {"tax_group_name": key, "tax_group_base_amount": 0.0, "tax_group_amount": 0.0})
                    base = getattr(line, "price_subtotal", 0.0) or 0.0
                    total = getattr(line, "price_total", base) or base
                    g["tax_group_base_amount"] += base
                    g["tax_group_amount"] += (total - base)
            tax_groups = list(groups.values())

        for tax_group in tax_groups:
            tax_group_name = tax_group.get("tax_group_name", "") if isinstance(tax_group, dict) else ""
            tax_ids = self.env["account.tax"].search([("name", "=", tax_group_name), ("company_id", "=", invoice.company_id.id)])
            iva_tax = tax_ids.filtered(lambda t: getattr(t, "iva_tax", False) and t.type_tax_use == "purchase")
            if not iva_tax:
                iva_tax = tax_ids.filtered(lambda t: getattr(t, "amount", 0) and float(t.amount) > 0 and t.type_tax_use == "purchase")
            if iva_tax:
                base_amount = tax_group.get("tax_group_base_amount", 0.0)
                iva_amount = tax_group.get("tax_group_amount", 0.0)
                retention_percentage = 0.0
                if self.partner_id and getattr(self.partner_id, "withholding_type_id", False):
                    retention_percentage = self.partner_id.withholding_type_id.percentage_ret or 0.0
                retention_amount = iva_amount * retention_percentage / 100.0
                foreign_iva_amount = 0.0
                foreign_retention_amount = 0.0
                if invoice.currency_id != invoice.company_id.currency_id:
                    rate = invoice.foreign_rate if getattr(invoice, "foreign_rate", False) else 1.0 / (getattr(invoice, "foreign_inverse_rate", 1) or 1)
                    foreign_iva_amount = iva_amount / (rate if rate else 1)
                    foreign_retention_amount = retention_amount / (rate if rate else 1)
                vals = {
                    "move_id": invoice.id,
                    "date_invoice": getattr(invoice, "invoice_date", False),
                    "invoice_amount": base_amount,
                    "iva_amount": iva_amount,
                    "retention_amount": retention_amount,
                    "invoice_total": getattr(invoice, "amount_total", 0.0),
                    "foreign_invoice_amount": getattr(invoice, "amount_untaxed_signed", 0.0),
                    "foreign_iva_amount": foreign_iva_amount,
                    "foreign_retention_amount": foreign_retention_amount,
                    "foreign_invoice_total": getattr(invoice, "amount_total_signed", 0.0),
                    "retention_rate": retention_percentage,
                    "invoice_type": getattr(invoice, "move_type", False),
                    "is_retention_client": True,
                }
                retention_lines_data.append(vals)
            else:
                _logger.debug("No IVA tax found for tax_group '%s' on invoice %s (company %s)", tax_group_name, getattr(invoice, "id", False), getattr(invoice.company_id, "id", False))

        return retention_lines_data

    def _validate_retention_journals(self):
        """
        Validate that the company has the journals configured for the retention type.
        """
        for retention in self:
            # IVA
            if (retention.type_retention, retention.type) == (
                "iva",
                "in_invoice",
            ) and not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _("The company must have a supplier IVA retention journal configured.")
                )
            if (retention.type_retention, retention.type) == (
                "iva",
                "out_invoice",
            ) and not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _("The company must have a customer IVA retention journal configured.")
                )
            # ISLR
            if (retention.type_retention, retention.type) == (
                "islr",
                "in_invoice",
            ) and not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _("The company must have a supplier ISLR retention journal configured.")
                )
            if (retention.type_retention, retention.type) == (
                "islr",
                "out_invoice",
            ) and not self.env.company.islr_customer_retention_journal_id:
                raise UserError(
                    _("The company must have a customer ISLR retention journal configured.")
                )
            # Municipal
            if (retention.type_retention, retention.type) == (
                "municipal",
                "in_invoice",
            ) and not self.env.company.municipal_supplier_retention_journal_id:
                raise UserError(
                    _("The company must have a supplier municipal retention journal configured.")
                )
            if (retention.type_retention, retention.type) == (
                "municipal",
                "out_invoice",
            ) and not self.env.company.municipal_customer_retention_journal_id:
                raise UserError(
                    _("The company must have a customer municipal retention journal configured.")
                )

    def clear_retention(self):
        """
        Clear retention lines and payments.
        """
        self.ensure_one()
        self.update(
            {
                "retention_line_ids": (
                    Command.clear()
                    if any(isinstance(id, models.NewId) for id in self.retention_line_ids.ids)
                    else False
                ),
            }
        )

    @api.onchange("retention_line_ids")
    def onchange_retention_line_ids(self):
        """
        On the IVA supplier retention when a line is deleted, delete all the others lines that have
        the same invoice.
        """
        for retention in self.filtered(
            lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id
        ):
            original_lines_per_invoice_counter = json.loads(
                retention.original_lines_per_invoice_counter
            )
            lines_per_invoice_counter = defaultdict(int)
            for line in retention.retention_line_ids:
                lines_per_invoice_counter[str(line.move_id.id)] += 1

            for line in retention.retention_line_ids:
                original_count = original_lines_per_invoice_counter.get(str(line.move_id.id), 0)
                current_count = lines_per_invoice_counter[str(line.move_id.id)]

                if (
                    line.move_id.id
                    and current_count < original_count
                ):
                    retention.retention_line_ids -= line

            return {
                "value": {
                    "original_lines_per_invoice_counter": json.dumps(lines_per_invoice_counter)
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._create_payments_from_retention_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("retention_line_ids", False):
            self._create_payments_from_retention_lines()
        return res
    
    def unlink(self):
        for record in self:
            if record.state == "emitted":
                raise ValidationError(_("You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"))
        return super().unlink()

    def _create_payments_from_retention_lines(self):
        """
        Create the payments from the retention lines for an IVA retention.

        When there are retention lines without payments, this method will create a payment for each
        set of retention lines that have the same invoice.
        """
        for retention in self:
            if any(retention.payment_ids) or retention.type_retention != "iva":
                continue
            payment_vals = {
                "retention_id": retention.id,
                "partner_id": retention.partner_id.id,
                "payment_type_retention": "iva",
                "is_retention": True,
                "currency_id": self.env.user.company_id.currency_id.id,
            }

            def account_retention_line_empty_recordset():
                return self.env["account.retention.line"]

            if retention.type == "in_invoice":
                self._create_payments_for_iva_supplier(
                    payment_vals, account_retention_line_empty_recordset
                )
            if retention.type == "out_invoice":
                self._create_payments_for_iva_customer(
                    payment_vals, account_retention_line_empty_recordset
                )

    def _create_payments_for_iva_supplier(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "supplier"
        payment_vals["journal_id"] = self.env.company.iva_supplier_retention_journal_id.id
        in_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_refund"
        )
        in_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_invoice"
        )

        in_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        in_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in in_refund_lines:
            in_refunds_dict[line.move_id] += line
        for line in in_invoice_lines:
            in_invoices_dict[line.move_id] += line

        for lines in in_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)}
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in in_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)}
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def _create_payments_for_iva_customer(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "customer"
        payment_vals["journal_id"] = self.env.company.iva_customer_retention_journal_id.id
        out_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_refund"
        )
        out_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_invoice"
        )

        out_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        out_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in out_refund_lines:
            out_refunds_dict[line.move_id] += line
        for line in out_invoice_lines:
            out_invoices_dict[line.move_id] += line

        for lines in out_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)}
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in out_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {"foreign_inverse_rate": Rate.compute_inverse_rate(payment.foreign_rate)}
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def action_draft(self):
        self.write({"state": "draft"})

    def action_post(self):
        today = datetime.now()
        for retention in self:
            if (
                retention.type in ["out_invoice", "out_refund", "out_debit"]
                and not retention.number
            ):
                raise UserError(_("Insert a number for the retention"))
            if not retention.date_accounting:
                retention.date_accounting = today
            if not retention.date:
                retention.date = today

            move_ids = retention.mapped("retention_line_ids.move_id")
            self.set_voucher_number_in_invoice(move_ids, retention)
            
            if not retention.payment_ids:
                payments = retention.create_payment_from_retention_form()
                retention.payment_ids = payments.ids

            if retention.type in ["in_invoice", "in_refund", "in_debit"]:
                retention._set_sequence()
                self.set_voucher_number_in_invoice(move_ids, retention)

        self.payment_ids.write({"date": self.date_accounting})
        self._reconcile_all_payments()
        self.write({"state": "emitted"})

    def action_cancel(self):
        """
        Cancel the retention.
        This method is referenced from the view as action_cancel.
        It marks the retention as cancelled and performs minimal checks.
        Extend this logic if you need to reverse accounting entries or unlink payments.
        """
        for retention in self:
            if retention.state != "emitted":
                raise ValidationError(_("Only emitted retentions can be cancelled."))
            retention.write({"state": "cancel"})
        return True

    def set_voucher_number_in_invoice(self, move, retention):
        if retention.type_retention == "iva":
            move.write({"iva_voucher_number": retention.number})
        elif retention.type_retention == "islr":
            move.write({"islr_voucher_number": retention.number})
        elif retention.type_retention == "municipal":
            move.write({"municipal_voucher_number": retention.number})

    def action_print_municipal_retention_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/get_xlsx_municipal_retention?&retention_id={self.id}",
            "target": "self",
        }

    def _set_sequence(self):
        for retention in self.filtered(lambda r: not r.number):
            sequence_number = ""
            if retention.type_retention == "iva":
                sequence_number = retention.get_sequence_iva_retention().next_by_id()
            elif retention.type_retention == "islr":
                sequence_number = retention.get_sequence_islr_retention().next_by_id()
            else:
                sequence_number = retention.get_sequence_municipal_retention().next_by_id()
            correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
            retention.name = correlative
            retention.number = correlative

    @api.model
    def get_sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.iva.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones IVA",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                }
            )

        return sequence
    
        
    def _reconcile_all_payments(self):
       
        for retention in self:
            try:
                _logger.info("Retention %s: starting reconciliation; payments=%s, retention_lines=%s",
                             retention.id, len(retention.payment_ids), len(retention.retention_line_ids))

                if not retention.payment_ids:
                    _logger.debug("Retention %s: no payments to reconcile", retention.id)
                    continue

                company_currency = retention.company_id.currency_id
                # Tolerancia: 2 unidades de la precisión de la moneda de la compañía (ej. 0.02)
                tolerance = (10 ** -company_currency.decimal_places) * 2

                # Pre-calc: map invoice move -> its candidate lines (unreconciled payable/receivable)
                invoice_lines_map = {}
                for rline in retention.retention_line_ids:
                    inv = rline.move_id
                    if not inv:
                        continue
                    cand = inv.line_ids.filtered(
                        lambda l: l.account_id.account_type in ('liability_payable', 'asset_receivable') and not l.reconciled
                    )
                    if cand:
                        invoice_lines_map.setdefault(inv.id, cand)

                # For each payment, try to reconcile with invoice(s) that belong to this retention
                for payment in retention.payment_ids:
                    if not payment.move_id:
                        _logger.debug("Payment %s has no move_id, skipping", payment.id)
                        continue

                    # Candidate payment lines: payable/receivable lines not reconciled
                    pay_lines = payment.move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type in ('liability_payable', 'asset_receivable') and not l.reconciled
                    )
                    if not pay_lines:
                        _logger.debug("Payment move %s: no candidate lines to reconcile", payment.move_id.id)
                        continue

                    # Sum payment lines in company currency
                    pay_total = sum(pay_lines.mapped('balance'))  # balance is company currency
                    _logger.debug("Payment %s: candidate lines=%s total_balance=%s", payment.id, len(pay_lines), pay_total)

                    # Try to match with each invoice in the retention
                    for inv_id, inv_lines in list(invoice_lines_map.items()):
                        # recalc invoice total (company currency)
                        inv_total = sum(inv_lines.mapped('balance'))
                        _logger.debug("Comparing payment %s (total=%s) with invoice %s (total=%s)",
                                      payment.id, pay_total, inv_id, inv_total)

                        # If signs are opposite and absolute sums match within tolerance, reconcile union
                        if abs(abs(pay_total) - abs(inv_total)) <= tolerance:
                            # Build union of lines to reconcile
                            lines_to_reconcile = (pay_lines | inv_lines)
                            try:
                                lines_to_reconcile.reconcile()
                                _logger.info("Retention %s: reconciled payment %s with invoice %s (amount=%s)",
                                             retention.id, payment.id, inv_id, inv_total)
                                # Remove invoice from map (already reconciled)
                                invoice_lines_map.pop(inv_id, None)
                                # Payment lines may be reconciled now; break to next payment
                                break
                            except Exception as e:
                                _logger.exception("Retention %s: error reconciling payment %s with invoice %s: %s",
                                                  retention.id, payment.id, inv_id, e)
                                # continue trying other invoices

                    else:
                        # No exact match found: try pairwise partial reconciliations
                        # Strategy: try to reconcile individual invoice lines with payment lines
                        for inv_id, inv_lines in list(invoice_lines_map.items()):
                            for il in inv_lines:
                                # For each invoice line, try to find payment line with opposite sign and similar amount
                                for pl in pay_lines:
                                    if pl.reconciled or il.reconciled:
                                        continue
                                    # Compare absolute balances
                                    if abs(abs(pl.balance) - abs(il.balance)) <= tolerance:
                                        try:
                                            (pl | il).reconcile()
                                            _logger.info("Retention %s: partially reconciled payment line %s with invoice line %s (amount=%s)",
                                                         retention.id, pl.id, il.id, il.balance)
                                        except Exception:
                                            _logger.exception("Retention %s: error partial reconciling lines %s & %s",
                                                              retention.id, pl.id, il.id)
                            # After attempting partials, remove fully reconciled invoice lines
                            remaining = inv_lines.filtered(lambda l: not l.reconciled)
                            if not remaining:
                                invoice_lines_map.pop(inv_id, None)

                # After processing all payments, log any invoices still unreconciled
                if invoice_lines_map:
                    for inv_id, inv_lines in invoice_lines_map.items():
                        remaining_amount = sum(inv_lines.mapped('balance'))
                        _logger.warning("Retention %s: invoice %s still has unreconciled lines count=%s remaining_amount=%s",
                                        retention.id, inv_id, len(inv_lines), remaining_amount)

            except Exception as e:
                _logger.exception("Error in _reconcile_all_payments for retention %s: %s", retention.id, e)
        return True

