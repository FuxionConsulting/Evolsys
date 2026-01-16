from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
from ..utils.utils_retention import load_retention_lines

import logging
_logger = logging.getLogger(__name__)


class AccountMoveRetention(models.Model):
    _inherit = "account.move"

    base_currency_is_vef = fields.Boolean(
        compute="_compute_currency_fields",
    )

    apply_islr_retention = fields.Boolean(
        string="Apply ISLR Retention?",
        default=False,
    )

    islr_voucher_number = fields.Char(copy=False)

    iva_voucher_number = fields.Char(copy=False)

    municipal_voucher_number = fields.Char(copy=False)

    retention_islr_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="ISLR Retention Lines",
        domain=[
            "|",
            ("payment_concept_id", "!=", False),
            ("retention_id.type_retention", "=", "islr"),
        ],
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="IVA Retention Lines",
        domain=[("retention_id.type_retention", "=", "iva")],
    )

    retention_municipal_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="Municipal Retention Lines",
        domain=[
            "|",
            ("economic_activity_id", "!=", False),
            ("retention_id.type_retention", "=", "municipal"),
        ],
    )

    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?",
        default=False,
    )

    def _compute_currency_fields(self):
        for retention in self:
            retention.base_currency_is_vef = self.env.company.currency_id == self.env.ref(
                "base.VEF"
            )

    def action_post(self):
        """
        Override the action_post method to create the retentions payment.
        """
        res = super().action_post()
        for move in self:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue

            if move.retention_islr_line_ids and not move.islr_voucher_number:
                move._validate_islr_retention()
                retention = move._create_supplier_retention("islr")
                retention.action_post()
                move.islr_voucher_number = retention.number

            if move.retention_municipal_line_ids:
                move._validate_municipal_retention()
                retention = move._create_supplier_retention("municipal")
                retention.action_post()

            # The IVA retention will not be generated if the invoice already has a retention that
            # is not cancelled
            if (
                move.generate_iva_retention
                and not move.retention_iva_line_ids.filtered(lambda l: l.state != "cancel")
            ):
                move._validate_iva_retention()
                retention = move._create_supplier_retention("iva")
                retention.action_post()
                move.iva_voucher_number = retention.number
        return res

    def _validate_islr_retention(self):
        """
        Validate that the company has a journal for ISLR supplier retention, the partner a type of
        person and that the amount of the retention is greater than zero, in order for the ISLR
        retention to be created.
        """
        self.ensure_one()
        if not self.env.company.islr_supplier_retention_journal_id:
            raise UserError(_("The company must have a journal for ISLR supplier retention."))
        islr_retention = self.retention_islr_line_ids
        sum_invoice_amount = sum(
            islr_retention.filtered(lambda rl: rl.state != "cancel").mapped("invoice_amount")
        )
        if sum_invoice_amount > self.tax_totals["amount_untaxed"]:
            raise UserError(
                _("The amount of the retention is greater than the total amount of the invoice.")
            )
        if not self.partner_id.type_person_id:
            raise UserError(_("The partner must have a type of person"))
        if sum_invoice_amount <= 0:
            raise UserError(_("The amount of the retention must be greater than zero."))

    def _validate_iva_retention(self):
        """
        Validate that the company has a journal for IVA supplier retention and that the invoice has
        at least one tax, in order for the IVA retention to be created.
        """
        self.ensure_one()
        if not self.env.company.iva_supplier_retention_journal_id:
            raise UserError(_("The company must have a journal for IVA supplier retention."))
        if not any(self.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0)):
            raise UserError(_("The invoice has no tax."))

    def _validate_municipal_retention(self):
        """
        Validate that the company has a journal for municipal supplier retention in order for the
        municipal retention to be created.
        """
        self.ensure_one()
        if not self.env.company.municipal_supplier_retention_journal_id:
            raise UserError(_("The company must have a journal for municipal supplier retention."))
        
    @api.model
    def _create_supplier_retention(self, type_retention):
        """
        Calls the method to create the payment for the retention of the type specified in the
        type_retention parameter and then creates the retention itself.
        """
        self.ensure_one()
        if type_retention == "iva" and not self.partner_id.withholding_type_id:
            raise UserError(_("The partner has no withholding type."))

        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
    
        # --- 1. PREPARACIÓN ---
        payment_type = "outbound"
        if self.move_type == "in_refund":
            payment_type = "inbound"

        journals = {
            "iva": self.env.company.iva_supplier_retention_journal_id,
            "islr": self.env.company.islr_supplier_retention_journal_id,
            "municipal": self.env.company.municipal_supplier_retention_journal_id,
        }
    
        # Inicialización de payment_vals
        payment_vals = {
            "payment_type": payment_type,
            "partner_type": "supplier",
            "partner_id": self.partner_id.id,
            "journal_id": journals[type_retention].id,
            "payment_type_retention": type_retention,
            "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
            "is_retention": True,
            "foreign_rate": self.foreign_rate,
            "foreign_inverse_rate": self.foreign_inverse_rate,
            "currency_id": self.env.user.company_id.currency_id.id,
            "amount": 0.0, # Se llenará más tarde con el monto total de la retención
        }
    
        # --- 2. CREACIÓN DEL PAGO ---
        payment = Payment.create(payment_vals)

        # --- 3. INICIALIZACIÓN DE RETENTION_VALS (SOLUCIONA UnboundLocalError) ---
        retention_vals = {
            "payment_ids": [Command.link(payment.id)],
            "date_accounting": self.date,
            "date": self.date if self.move_type == "in_invoice" else fields.Date.today(),
            #"date_retention": fields.Date.today(),
            "type_retention": type_retention,
            "type": "in_invoice", # Asumiendo que es para proveedores
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "company_currency_id": self.currency_id.id, # Moneda de la factura
            #"foreign_currency_rate": self.foreign_rate,
        }

        # --- 4. ASIGNACIÓN DE LÍNEAS DE RETENCIÓN (SOLUCIONA LÍNEAS EN CERO PARA ISLR/MUNICIPAL) ---
        if type_retention == "iva":
            invoices_to_retain = self
            temp_retention = Retention.new(retention_vals)
            # Asegúrate de que load_retention_lines está importado de ...utils.utils_retention
            retention_lines_data = load_retention_lines(invoices_to_retain, temp_retention)
            retention_vals["retention_line_ids"] = [
                Command.create(line) for line in retention_lines_data
            ]
        
        elif type_retention == "islr":
            # Usar Command.link (Odoo 17) para reasignar las líneas ya existentes de la factura
            retention_vals["retention_line_ids"] = [
                Command.link(rl.id) 
                for rl in self.retention_islr_line_ids.filtered(lambda rl: rl.state != "cancel")
            ]
        
        elif type_retention == "municipal":
            # Usar Command.link (Odoo 17) para reasignar las líneas ya existentes de la factura
            retention_vals["retention_line_ids"] = [
                Command.link(rl.id) 
                for rl in self.retention_municipal_line_ids.filtered(lambda rl: rl.state != "cancel")
            ]
        
        # --- 5. CREACIÓN FINAL Y CÁLCULO ---
        retention = Retention.create(retention_vals)
    
        # Calcular el monto total de la retención y actualizar el pago
        # Esto también actualiza el 'amount' del pago que se había creado con 0.0
        payment.compute_retention_amount_from_retention_lines()
    
        return retention
        

    @api.depends("move_type", "line_ids.amount_residual")
    def _compute_payments_widget_reconciled_info(self):
        res = super()._compute_payments_widget_reconciled_info()
        for record in self:
            if not record.invoice_payments_widget:
                continue

            for payment in record.invoice_payments_widget.get("content"):
                if not payment.get("account_payment_id", False):
                    payment["is_retention"] = False
                    continue
                payment_id = self.env["account.payment"].browse(payment["account_payment_id"])
                payment["is_retention"] = payment_id.is_retention

        return res

    @api.model
    def validate_payment(self, payment):
        """This function is used to not add withholding in the calculation of the last payment date"""
        if payment.get("is_retention", False):
            return False
        return True
    
    @api.model
    def _compute_rate_for_documents(self, documents, is_sale):
        res = super()._compute_rate_for_documents(documents, is_sale)
        for move in documents:
            # Only override if payment exists and payment is retention and payment.foreign_rate is truthy
            try:
                if move.payment_id and getattr(move.payment_id, "is_retention", False):
                    pay_fr = getattr(move.payment_id, "foreign_rate", None)
                    pay_fir = getattr(move.payment_id, "foreign_inverse_rate", None)
                    if pay_fr:
                        # set foreign_rate only if payment provides it
                        move.foreign_rate = pay_fr
                    # set foreign_inverse_rate using payment.foreign_inverse_rate if present,
                    # otherwise compute inverse of foreign_rate safely
                    if pay_fir:
                        move.foreign_inverse_rate = pay_fir
                    else:
                        # compute inverse safely
                        fr = getattr(move, "foreign_rate", None) or pay_fr or 1.0
                        move.foreign_inverse_rate = (1.0 / fr) if fr else 1.0
            except Exception:
                _logger.exception("Error computing rate for move %s from payment %s", move.id, getattr(move, "payment_id", False) and move.payment_id.id or None)
        return res
