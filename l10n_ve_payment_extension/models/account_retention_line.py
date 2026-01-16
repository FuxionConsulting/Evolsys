from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils_retention import load_retention_lines
from collections import defaultdict


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

    retention_id = fields.Many2one(
        "account.retention",
        string="Retention",
        required=True,
        ondelete="cascade",
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Document Number",
        required=True,
        ondelete="cascade",
        index=True,
    )

    date_invoice = fields.Date(string="Invoice Date")
    date_accounting = fields.Date(string="Accounting Date", compute="_compute_date_accounting", store=True)

    invoice_amount = fields.Float(
        string="Taxable income",
        digits="Tasa",
        store=True,
        readonly=False,
    )
    iva_amount = fields.Float(string="IVA", digits=(16, 2), store=True)
    retention_amount = fields.Float(digits="Tasa", store=True, readonly=False)

    invoice_total = fields.Float(string="Total invoiced", digits="Tasa", store=True)
    foreign_invoice_total = fields.Float(string="Foreign total invoiced", store=True)

    foreign_invoice_amount = fields.Float(
        string="Foreign taxable income", store=True, readonly=False
    )
    foreign_iva_amount = fields.Float(string="Foreign IVA", store=True)
    foreign_retention_amount = fields.Float(digits="Tasa", store=True, readonly=False)
    foreign_currency_rate = fields.Float(string="Rate", store=True)

    name = fields.Char(
        string="Description", compute="_compute_name", store=True, readonly=False
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        related="retention_id.company_currency_id", store=True
    )
    foreign_currency_id = fields.Many2one(
        related="retention_id.foreign_currency_id", store=True
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("emitted", "Emitted"),
            ("cancel", "Cancelled"),
        ],
        string="State",
        compute="_compute_state",
        store=True,
        readonly=True,
    )

    invoice_type = fields.Selection(
        selection=[
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
        ],
    )

    is_retention_client = fields.Boolean(default=True)

    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )
    code = fields.Char(related="payment_concept_id.line_payment_concept_ids.code", store=True)
    code_visible = fields.Boolean(related="company_id.code_visible", store=True)

    economic_activity_id = fields.Many2one(
        "economic.activity",
        ondelete="cascade",
        compute="_compute_economic_activity_id",
        readonly=False,
        store=True,
        index=True,
    )

    payment_id = fields.Many2one("account.payment", "Payment", index=True)
    payment_date = fields.Date(related="payment_id.date", store=True)
    payment_journal_id = fields.Many2one(
        "account.journal",
        "Payment journal",
        ondelete="cascade",
        index=True,
        related="payment_id.journal_id",
        store=True,
    )

    related_pay_from = fields.Float(
        string="Pays from", compute="_compute_related_fields", store=True
    )
    related_percentage_tax_base = fields.Float(
        string="% tax base", compute="_compute_related_fields", store=True, readonly=False
    )
    related_percentage_fees = fields.Float(
        string="% tariffs", compute="_compute_related_fields", store=True
    )
    related_amount_subtract_fees = fields.Float(
        string="Amount subtract tariffs", compute="_compute_related_fields", store=True
    )

    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    imp_ret = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits="Tasa")

    @api.depends("retention_id.state")
    def _compute_state(self):
        for rec in self:
            rec.state = rec.retention_id.state if rec.retention_id else False

    @api.depends("retention_id", "move_id")
    def _compute_name(self):
        for record in self:
            if record.name:
                continue
            names = {
                "islr": _("ISLR Retention"),
                "iva": _("IVA Retention"),
                "municipal": _("Municipal Retention"),
            }
            type_retention = "islr"
            if record.retention_id and record.retention_id.type_retention:
                type_retention = record.retention_id.type_retention
            elif record.move_id:
                if record in record.move_id.retention_iva_line_ids:
                    type_retention = "iva"
                elif record in record.move_id.retention_municipal_line_ids:
                    type_retention = "municipal"

            record.name = names.get(type_retention, _("Retention"))

    @api.depends("retention_id", "move_id")
    def _compute_economic_activity_id(self):
        for line in self:
            if line.economic_activity_id:
                continue
            if line.retention_id and line.retention_id.type_retention == "municipal":
                line.economic_activity_id = line.retention_id.partner_id.economic_activity_id
            if line.move_id and line.id in line.move_id.retention_municipal_line_ids.ids:
                line.economic_activity_id = line.move_id.partner_id.economic_activity_id

    @api.onchange("payment_concept_id")
    @api.depends("payment_concept_id", "move_id")
    def _compute_related_fields(self):
        lines_from_islr_retention = self.filtered(
            lambda l: l.payment_concept_id
            and (not l.retention_id or l.retention_id.type_retention == "islr")
        )
        for record in lines_from_islr_retention:
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if not record.move_id or not record.move_id.partner_id:
                    continue
                if record.move_id.partner_id.type_person_id.id == line.type_person_id.id:
                    tt = getattr(record.move_id, "tax_totals", {}) or {}
                    record.invoice_total = tt.get("amount_total", record.invoice_total)
                    record.foreign_invoice_total = tt.get("foreign_amount_total", record.foreign_invoice_total)
                    record.related_pay_from = line.pay_from
                    record.related_percentage_tax_base = line.percentage_tax_base
                    record.related_percentage_fees = line.tariff_id.percentage
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract
                    record.foreign_currency_rate = record.move_id.foreign_rate

                    if not record.retention_id or record.retention_id.type == "in_invoice":
                        record.invoice_amount = tt.get("amount_untaxed", record.invoice_amount)
                        record.foreign_invoice_amount = tt.get("foreign_amount_untaxed", record.foreign_invoice_amount)

    @api.onchange(
        "invoice_amount",
        "foreign_invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "foreign_currency_rate",
        "move_id",
    )
    def onchange_move_id(self):
        for line in self:
            if not line.move_id or not line.retention_id:
                continue

            parent_vals = {
                "partner_id": line.retention_id.partner_id.id,
                "type_retention": line.retention_id.type_retention,
                "type": line.retention_id.type,
                "date": line.retention_id.date,
                "company_id": line.retention_id.company_id.id,
                "company_currency_id": line.retention_id.company_currency_id.id,
                "foreign_currency_id": line.retention_id.foreign_currency_id.id,
            }
            temp_retention = self.env["account.retention"].new(parent_vals)

            invoices = line.move_id if hasattr(line.move_id, "id") else self.env["account.move"].browse(line.move_id.id)
            lines_data = load_retention_lines(invoices, temp_retention)

            if not lines_data:
                continue

            first = lines_data[0] if lines_data and isinstance(lines_data[0], (list, tuple)) and len(lines_data[0]) >= 3 else None
            vals = first[2] if first else {}

            line.date_invoice = line.move_id.invoice_date
            line.invoice_amount = vals.get("invoice_amount", line.invoice_amount)
            line.iva_amount = vals.get("iva_amount", line.iva_amount)
            line.retention_amount = vals.get("retention_amount", line.retention_amount)
            line.foreign_invoice_amount = vals.get("foreign_invoice_amount", line.foreign_invoice_amount)
            line.foreign_iva_amount = vals.get("foreign_iva_amount", line.foreign_iva_amount)
            line.foreign_retention_amount = vals.get("foreign_retention_amount", line.foreign_retention_amount)
            line.invoice_total = vals.get("invoice_total", line.invoice_total)
            line.foreign_invoice_total = vals.get("foreign_invoice_total", line.foreign_invoice_total)
            line.payment_concept_id = vals.get("payment_concept_id", line.payment_concept_id)
            line.economic_activity_id = vals.get("economic_activity_id", line.economic_activity_id)

            if line.move_id.move_type in ("in_refund", "out_refund"):
                line.invoice_amount *= -1
                line.iva_amount *= -1
                line.retention_amount *= -1
                line.foreign_invoice_amount *= -1
                line.foreign_iva_amount *= -1
                line.foreign_retention_amount *= -1

            line._compute_related_fields()
            line.onchange_economic_activity_id()
            line._compute_retention_amount()

    @api.depends("invoice_amount", "foreign_invoice_amount", "related_percentage_tax_base", "related_percentage_fees", "related_amount_subtract_fees", "foreign_currency_rate", "move_id")
    def _compute_retention_amount(self):
        base_currency_is_vef = self.env.company.currency_id == self.env.ref("base.VEF")

        islr_supplier_retention_lines = self.filtered(
            lambda l: (not l.retention_id and l.payment_concept_id)
            or (l.retention_id and l.retention_id.type_retention == "islr" and l.retention_id.type == "in_invoice")
        )
        for record in islr_supplier_retention_lines:
            foreign_rate = getattr(record.move_id, "foreign_rate", None) or 1
            foreign_inverse_rate = getattr(record.move_id, "foreign_inverse_rate", None) or (1 / foreign_rate if foreign_rate else 1)

            if not base_currency_is_vef:
                record.retention_amount = (
                    record.invoice_amount
                    * (record.related_percentage_tax_base / 100.0)
                    * (record.related_percentage_fees / 100.0)
                ) - (record.related_amount_subtract_fees / (foreign_rate or 1))
            else:
                record.retention_amount = (
                    record.invoice_amount
                    * (record.related_percentage_tax_base / 100.0)
                    * (record.related_percentage_fees / 100.0)
                ) - record.related_amount_subtract_fees

            rate_for_subtraction = foreign_inverse_rate or (1 / foreign_rate if foreign_rate else 1)
            record.foreign_retention_amount = (
                record.foreign_invoice_amount
                * (record.related_percentage_tax_base / 100.0)
                * (record.related_percentage_fees / 100.0)
            ) - (record.related_amount_subtract_fees * rate_for_subtraction)

    @api.onchange("economic_activity_id", "move_id")
    def onchange_economic_activity_id(self):
        municipal_retention_lines_with_economic_activity_and_invoice = self.filtered(
            lambda l: (not l.retention_id or (l.retention_id.type_retention == "municipal"))
            and l.economic_activity_id
            and l.move_id
        )

        for record in municipal_retention_lines_with_economic_activity_and_invoice:
            if not record.retention_id or record.retention_id.type == "in_invoice":
                tt = getattr(record.move_id, "tax_totals", {}) or {}
                record.invoice_amount = tt.get("amount_untaxed", record.invoice_amount)
                record.foreign_invoice_amount = tt.get("foreign_amount_untaxed", record.foreign_invoice_amount)

            tt = getattr(record.move_id, "tax_totals", {}) or {}
            record.invoice_total = tt.get("amount_total", record.invoice_total)
            record.foreign_invoice_total = tt.get("foreign_amount_total", record.foreign_invoice_total)
            record.foreign_currency_rate = getattr(record.move_id, "foreign_rate", record.foreign_currency_rate)

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100.0
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100.0

    @api.onchange("invoice_amount", "foreign_invoice_amount", "aliquot")
    def onchange_municipal_invoice_amount(self):
        for record in self.filtered(
            lambda l: (not l.retention_id and l.economic_activity_id)
            or (l.retention_id and l.retention_id.type_retention == "municipal")
        ):
            record.retention_amount = record.invoice_amount * record.aliquot / 100.0
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100.0

    @api.onchange("retention_amount", "invoice_amount")
    def onchange_retention_amount(self):
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(lambda l: not l.retention_id or l.retention_id.type == "out_invoice"):
            self.env.context = self.with_context(noonchange=True).env.context
            if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                line.update({"foreign_invoice_amount": line.invoice_amount * line.move_id.foreign_inverse_rate})
            line.update({"foreign_retention_amount": line.retention_amount * line.move_id.foreign_inverse_rate})

    @api.onchange("foreign_retention_amount", "foreign_invoice_amount")
    def onchange_foreign_retention_amount(self):
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(lambda l: not l.retention_id or l.retention_id.type == "out_invoice"):
            if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                line.update({"invoice_amount": line.foreign_invoice_amount * (1 / (line.move_id.foreign_rate or 1))})
            self.env.context = self.with_context(noonchange=True).env.context
            line.update({"retention_amount": line.foreign_retention_amount * (1 / (line.move_id.foreign_rate or 1))})

    @api.constrains(
        "retention_amount",
        "invoice_total",
        "foreign_retention_amount",
        "invoice_amount",
        "foreign_invoice_amount",
    )
    def _constraint_amounts(self):
        for record in self:
            if not record.retention_id:
                continue
            if record.retention_id.type == "in_invoice":
                if record.retention_amount <= 0 or record.foreign_retention_amount <= 0:
                    raise ValidationError(_("You can not create a retention with 0 amount."))
                if record.invoice_amount <= 0 or record.foreign_invoice_amount <= 0:
                    raise ValidationError(_("The invoice amounts must be greater than zero."))

    def unlink(self):
        for record in self:
            if record.payment_id:
                record.payment_id.unlink()
        return super().unlink()

    def get_invoice_paid_amount_not_related_with_retentions(self):
        lines_without_duplicate_invoices = self.env[self._name]
        for line in self.filtered(lambda l: l.retention_id and l.retention_id.type_retention == "islr"):
            if line.move_id in lines_without_duplicate_invoices.mapped("move_id"):
                continue
            lines_without_duplicate_invoices |= line

        for line in lines_without_duplicate_invoices:
            debit_line = line.move_id.line_ids.filtered(lambda l: l.account_id.account_type == "liability_payable" and l.credit > 0)
            if not debit_line:
                continue
            partials = self.env["account.partial.reconcile"].search(
                [("credit_move_id", "=", debit_line[0].id)]
            )
            retention_payments = self.env["account.payment"].search(
                [
                    ("move_id.line_ids", "in", partials.mapped("debit_move_id").ids),
                    ("is_retention", "=", True),
                ]
            )
            invoice_paid_amount_not_related_with_retentions = sum(
                partial.debit_amount_currency
                if partial.debit_currency_id == self.env.ref("base.VEF")
                else partial.debit_amount_currency * partial.debit_move_id.foreign_inverse_rate
                for partial in partials.filtered(
                    lambda p: p.debit_move_id not in retention_payments.mapped("move_id.line_ids")
                )
            )
            return invoice_paid_amount_not_related_with_retentions
