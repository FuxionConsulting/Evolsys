# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from psycopg2 import IntegrityError as Psycopg2IntegrityError

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention.simple"
    _inherit = ["mail.thread"]
    _description = "Retention Simple"
    _order = "id desc"

    name = fields.Char("Description")
    number = fields.Char("Voucher Number", copy=False)
    retention_id = fields.Char("Retention Ref", copy=False, readonly=True, index=True)
    # Link to invoice (used by the move logic)
    move_id = fields.Many2one(
        "account.move",
        string="Factura Asociada",
        index=True,
        help="Factura asociada a esta retención (si aplica).",
    )
    invoice_vendor_bill_id = fields.Many2one("account.move", "Invoice Reference", readonly=True)
    partner_id = fields.Many2one("res.partner", "Partner", required=True)
    date = fields.Date("Date", default=fields.Date.context_today)
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        default="draft",
        string="State",
        required=True,
        tracking=True,
    )
    type_retention = fields.Selection(
        [("iva", "IVA"), ("islr", "ISLR"), ("municipal", "Municipal")],
        string="Type",
        required=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    # store company currency for faster access and rounding
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True, store=True)
    retention_line_ids = fields.One2many("account.retention.line.simple", "retention_id", "Retention Lines")

    total_retention = fields.Monetary(
        string="Total Retention",
        compute="_compute_totals",
        store=True,
        currency_field="company_currency_id",
    )

    # Track payments created by this retention for audit
    payment_ids = fields.Many2many(
        "account.payment",
        "retention_payment_rel",
        "retention_id",
        "payment_id",
        string="Payments",
        readonly=True,
    )

    # Mostrar únicamente la referencia interna en la columna de descripción
    display_name = fields.Char("Display", compute="_compute_display_name", store=True)

    @api.depends('retention_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.retention_id or ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("retention_id"):
                try:
                    seq = self.env["ir.sequence"].next_by_code("retention.ref")
                except Exception:
                    seq = None
                if seq:
                    vals["retention_id"] = str(seq).zfill(5)
            if vals.get("number") and not vals.get("state"):
                vals["state"] = "emitted"
        try:
            return super().create(vals_list)
        except Psycopg2IntegrityError as e:
            msg = str(e).lower()
            if "unique" in msg or "duplicate key value" in msg:
                raise ValidationError(
                    _("No se pudo crear el voucher por un conflicto de integridad. Revisa duplicados o la secuencia del diario.")
                )
            raise

    def write(self, vals):
        # Prevent manual change of retention_id
        if "retention_id" in vals:
            vals.pop("retention_id")
        # If number assigned, set state to emitted unless explicitly set
        if "number" in vals:
            for rec in self:
                new_number = vals.get("number")
                if (not rec.number) and new_number:
                    if not vals.get("state"):
                        res = super().write(vals)
                        for r in self:
                            if r.number and r.state != "emitted":
                                r.state = "emitted"
                        return res
        try:
            return super().write(vals)
        except Psycopg2IntegrityError as e:
            msg = str(e).lower()
            if "unique" in msg or "duplicate key value" in msg:
                raise ValidationError(
                    _("No se pudo actualizar el voucher por un conflicto de integridad. Revisa duplicados o la secuencia del diario.")
                )
            raise

    def action_emit(self):
        """Emit retention, create payments per related invoice (net of retention) and attempt reconciliation."""
        for rec in self:
            if not rec.retention_line_ids:
                raise UserError(_("No retention lines to emit"))

            # Ensure voucher number (user-editable) exists if desired
            if not rec.number:
                try:
                    rec.number = self.env["ir.sequence"].next_by_code("retention.simple") or False
                except Exception:
                    rec.number = False

            # Ensure internal retention reference
            if not rec.retention_id:
                try:
                    seq = self.env['ir.sequence'].next_by_code('retention.ref')
                except Exception:
                    seq = None
                if seq:
                    rec.retention_id = str(seq).zfill(5)

            # Mark as emitted
            if rec.number and rec.state != "emitted":
                rec.state = "emitted"

            # Group retention lines by invoice (move_id)
            lines_by_invoice = {}
            for line in rec.retention_line_ids:
                if not line.move_id:
                    _logger.warning("Retention %s: retention line %s has no move_id, skipping line.", rec.id, line.id)
                    continue
                lines_by_invoice.setdefault(line.move_id.id, []).append(line)

            # Process each invoice separately
            for move_id, lines in lines_by_invoice.items():
                invoice = self.env['account.move'].browse(move_id)
                if not invoice:
                    _logger.warning("Retention %s: invoice %s not found, skipping.", rec.id, move_id)
                    continue

                retention_for_invoice = sum([float(l.retention_amount or 0.0) for l in lines])

                # Ensure invoice amounts are up-to-date
                try:
                    if hasattr(invoice, '_compute_amount'):
                        invoice._compute_amount()
                except Exception:
                    pass

                residual = float(invoice.amount_residual or 0.0)

                if residual <= 0 and retention_for_invoice <= 0:
                    _logger.info("Retention %s: invoice %s has no residual and retention is zero, skipping.", rec.id, invoice.name)
                    continue

                pay_amount = residual - retention_for_invoice

                if pay_amount <= 0:
                    _logger.info(
                        "Retention %s: invoice %s pay_amount <= 0 (residual=%s retention=%s). No se crea pago.",
                        rec.id, invoice.name, residual, retention_for_invoice
                    )
                    continue

                # Find a suitable journal (bank/cash) for the company
                journal = self.env['account.journal'].search([
                    ('company_id', '=', rec.company_id.id),
                    ('type', 'in', ('bank', 'cash'))
                ], limit=1)
                if not journal:
                    journal = invoice.journal_id or self.env['account.journal'].search([('company_id', '=', rec.company_id.id)], limit=1)
                if not journal:
                    _logger.error("Retention %s: no journal found for company %s. Payment not created for invoice %s.", rec.id, rec.company_id.id, invoice.name)
                    continue

                # Determine payment_type and partner_type based on invoice type
                if invoice.move_type in ('in_invoice', 'in_refund'):
                    partner_type = 'supplier'
                    payment_type = 'outbound'
                else:
                    partner_type = 'customer'
                    payment_type = 'inbound'

                payment_method = self.env['account.payment.method'].search([('code', '=', 'manual')], limit=1)

                payment_vals = {
                    'payment_type': payment_type,
                    'partner_type': partner_type,
                    'partner_id': invoice.partner_id.id,
                    'amount': pay_amount,
                    'currency_id': invoice.currency_id.id or rec.company_currency_id.id,
                    'journal_id': journal.id,
                    'payment_method_id': payment_method.id if payment_method else False,
                    'communication': _("Payment for invoice %s (retention %s)") % (invoice.name or '', rec.retention_id or ''),
                    'company_id': rec.company_id.id,
                }

                try:
                    payment = self.env['account.payment'].create(payment_vals)
                    payment.action_post()
                    rec.payment_ids = [(4, payment.id)]
                    _logger.info("Retention %s: created payment %s amount %s for invoice %s", rec.id, payment.name, pay_amount, invoice.name)
                except Exception as e:
                    _logger.exception("Retention %s: error creating/posting payment for invoice %s: %s", rec.id, invoice.name, e)
                    continue

                # Attempt automatic reconciliation between payment and invoice
                try:
                    invoice_lines = invoice.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable') and not l.reconciled)
                    if not invoice_lines:
                        _logger.warning("Retention %s: invoice %s has no receivable/payable lines to reconcile.", rec.id, invoice.name)
                        continue
                    account = invoice_lines[0].account_id

                    payment_move = payment.move_id
                    payment_lines = payment_move.line_ids.filtered(lambda l: l.account_id == account and l.partner_id == invoice.partner_id and not l.reconciled)

                    invoice_unreconciled = invoice_lines.filtered(lambda l: not l.reconciled)
                    lines_to_reconcile = (payment_lines | invoice_unreconciled).filtered(lambda l: not l.reconciled)

                    total_balance = sum(lines_to_reconcile.mapped('balance'))
                    rounding = invoice.company_id.currency_id.rounding if invoice.company_id and invoice.company_id.currency_id else 0.0

                    if abs(total_balance) <= (rounding or 0.0):
                        try:
                            lines_to_reconcile.reconcile()
                            _logger.info("Retention %s: reconciled payment %s with invoice %s", rec.id, payment.name, invoice.name)
                        except Exception as e:
                            _logger.exception("Retention %s: reconciliation failed for invoice %s: %s", rec.id, invoice.name, e)
                    else:
                        try:
                            lines_to_reconcile.reconcile()
                            _logger.info("Retention %s: attempted reconciliation (non-zero diff) for invoice %s, check manual adjustments.", rec.id, invoice.name)
                        except Exception:
                            _logger.warning(
                                "Retention %s: could not reconcile payment %s with invoice %s automatically (difference=%s). Manual review required.",
                                rec.id, payment.name, invoice.name, total_balance
                            )
                except Exception as e:
                    _logger.exception("Retention %s: error during reconciliation for invoice %s: %s", rec.id, invoice.name, e)

    def action_cancel(self):
        for rec in self:
            rec.state = "cancel"

    @api.depends("retention_line_ids.retention_amount")
    def _compute_totals(self):
        for rec in self:
            rec.total_retention = sum(rec.retention_line_ids.mapped("retention_amount"))
