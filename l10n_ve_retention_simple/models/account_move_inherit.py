# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from psycopg2 import IntegrityError as Psycopg2IntegrityError

_logger = logging.getLogger(__name__)


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    retention_simple_ids = fields.One2many(
        "account.retention.line.simple",
        "move_id",
        string="Retention Lines",
        readonly=True,
        copy=False,
    )

    def _get_fiscal_position_from_company(self, company):
        """Obtener posición fiscal desde la compañía (si existe)."""
        if not company:
            return False
        for attr in ("property_account_position_id", "fiscal_position_id", "fiscal_position"):
            pos = getattr(company, attr, False)
            if pos:
                return pos
        return False

    def _fiscal_position_is_special(self, move):
        """
        Determina si la posición fiscal aplicable es 'Especial'.
        - Para ventas: usa la posición del partner.
        - Para compras: usa la posición configurada en la compañía.
        """
        if not move:
            return False

        is_sale = move.move_type in ("out_invoice", "out_refund")
        is_purchase = move.move_type in ("in_invoice", "in_refund")

        pos = False
        if is_sale:
            partner = move.partner_id
            if partner:
                pos = getattr(partner, "property_account_position_id", False) or getattr(partner, "fiscal_position_id", False)
        elif is_purchase:
            pos = self._get_fiscal_position_from_company(move.company_id)

        # Fallback: intentar partner si no se encontró nada
        if not pos and move.partner_id:
            pos = getattr(move.partner_id, "property_account_position_id", False) or getattr(move.partner_id, "fiscal_position_id", False)

        if not pos:
            return False

        return (pos.name or "").strip().lower() == "especial"

    def _validate_company_withholding_settings(self, company):
        """
        Comprueba que la compañía tenga los campos necesarios para retenciones en compras:
        - taxpayer_type
        - condition_withholding_id
        Devuelve (True, None) si OK, o (False, mensaje) si falta algo.
        """
        if not company:
            return False, _("Compañía no encontrada.")
        missing = []
        if not getattr(company, "taxpayer_type", False):
            missing.append("taxpayer_type")
        if not getattr(company, "condition_withholding_id", False):
            missing.append("condition_withholding_id")
        if missing:
            return False, _("Faltan en la compañía los campos: %s") % (", ".join(missing))
        return True, None

    def _validate_partner_withholding_settings(self, partner):
        """
        Comprueba que el partner tenga los campos necesarios para retenciones en ventas:
        - property_account_position_id (o fiscal_position_id)
        - retention_iva_rate
        Devuelve (True, None) si OK, o (False, mensaje) si falta algo.
        """
        if not partner:
            return False, _("Partner no encontrado.")
        missing = []
        if not getattr(partner, "property_account_position_id", False) and not getattr(partner, "fiscal_position_id", False):
            missing.append("property_account_position_id")
        if not getattr(partner, "retention_iva_rate", False):
            missing.append("retention_iva_rate")
        if missing:
            return False, _("Faltan en el partner los campos: %s") % (", ".join(missing))
        return True, None

    def _create_simple_retention_if_applicable(self, move):
        """
        Crea una retención simple (IVA) para un move si aplica.
        - Compras: valida campos en la compañía (taxpayer_type, condition_withholding_id).
        - Ventas: valida campos en el partner (property_account_position_id, retention_iva_rate)
                 y que la posición fiscal aplicable sea 'Especial'.
        """
        if not move:
            return False

        # Procesar solo facturas (incluye recibos) y notas de crédito
        if not move.is_invoice(include_receipts=True):
            return False

        # Evitar procesar tipos que no sean invoice/refund
        if move.move_type not in ("in_invoice", "in_refund", "out_invoice", "out_refund"):
            return False

        # Evitar duplicados: si ya hay líneas de retención, no crear de nuevo
        if move.retention_simple_ids:
            _logger.debug(
                "Invoice %s already has retention lines: %s",
                move.id,
                move.retention_simple_ids.ids,
            )
            return False

        partner = move.partner_id
        if not partner:
            _logger.debug("Move %s has no partner; skipping retention", move.id)
            return False

        # Validaciones específicas según tipo
        if move.move_type in ("in_invoice", "in_refund"):
            # Compras: validar campos en la compañía
            ok, msg = self._validate_company_withholding_settings(move.company_id)
            if not ok:
                _logger.warning("Skipping retention for purchase move %s: %s", move.id, msg)
                return False
        else:
            # Ventas: validar campos en el partner
            ok, msg = self._validate_partner_withholding_settings(partner)
            if not ok:
                _logger.warning("Skipping retention for sale move %s: %s", move.id, msg)
                return False

            # Además, comprobar que la posición fiscal aplicable sea 'Especial'
            if not self._fiscal_position_is_special(move):
                _logger.debug("Fiscal position not 'Especial' for sale move %s (partner %s)", move.id, partner.id)
                return False

        # Obtener porcentaje de retención:
        if move.move_type in ("out_invoice", "out_refund"):
            wt = getattr(partner, "retention_iva_rate", False)
        else:
            # Para compras: preferir valor en compañía si existe, si no fallback al partner
            wt = getattr(move.company_id, "retention_iva_rate", False) or getattr(partner, "retention_iva_rate", False)

        if not wt:
            _logger.warning("No retention_iva_rate found for move %s (type=%s)", move.id, move.move_type)
            return False

        try:
            retention_pct = float(wt)
        except Exception:
            _logger.exception("Invalid retention_iva_rate for move %s: %s", move.id, wt)
            return False

        # Forzar cálculo de tax_totals si está disponible para agrupar correctamente
        try:
            if hasattr(move, "_compute_tax_totals"):
                move._compute_tax_totals()
        except Exception:
            _logger.debug("No se pudo forzar cálculo tax_totals para move %s", move.id)

        # Construir grupos de impuestos desde tax_totals si existe, fallback por líneas
        tax_groups = []
        tt = getattr(move, "tax_totals", None)
        if tt:
            try:
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
                elif isinstance(tt, list):
                    tax_groups.extend(tt)
            except Exception:
                _logger.exception("Error parsing tax_totals for invoice %s", move.id)
                tax_groups = []

        if not tax_groups:
            groups = {}
            for line in move.invoice_line_ids:
                for tax in line.tax_ids:
                    key = tax.name or "IVA"
                    g = groups.setdefault(
                        key,
                        {
                            "tax_group_name": key,
                            "tax_group_base_amount": 0.0,
                            "tax_group_amount": 0.0,
                        },
                    )
                    base = getattr(line, "price_subtotal", 0.0) or 0.0
                    total = getattr(line, "price_total", base) or base
                    g["tax_group_base_amount"] += base
                    g["tax_group_amount"] += (total - base)
            tax_groups = list(groups.values())

        retention_vals = []
        for tg in tax_groups:
            iva_amount = tg.get("tax_group_amount", 0.0) or 0.0
            base_amount = tg.get("tax_group_base_amount", 0.0) or 0.0
            retention_amount = iva_amount * (retention_pct / 100.0)
            # Solo crear líneas si hay monto positivo de retención
            if retention_amount and retention_amount > 0:
                retention_vals.append(
                    {
                        "move_id": move.id,
                        "invoice_amount": base_amount,
                        "iva_amount": iva_amount,
                        "retention_amount": retention_amount,
                    }
                )

        if not retention_vals:
            _logger.debug("No retention lines computed for invoice %s", move.id)
            return False

        # Crear el registro de retención y sus líneas
        try:
            # Evitar crear duplicados por carrera concurrente: comprobar antes si existe
            existing = self.env["account.retention.simple"].search(
                [("partner_id", "=", partner.id), ("move_id", "=", move.id)], limit=1
            )
            if existing:
                _logger.info("Retention already exists (%s) for move %s", existing.id, move.id)
                return existing

            retention = self.env["account.retention.simple"].create(
                {
                    "partner_id": partner.id,
                    "type_retention": "iva",
                    "date": move.invoice_date or fields.Date.context_today(self),
                    "company_id": move.company_id.id,
                    "name": _("Retention for %s") % (move.name or ""),
                    "move_id": move.id,
                }
            )
            created_lines = []
            for vals in retention_vals:
                vals.update({"retention_id": retention.id})
                line = self.env["account.retention.line.simple"].create(vals)
                created_lines.append(line.id)

            if created_lines:
                # Vincular líneas a la factura (One2many inverso)
                move.write({"retention_simple_ids": [(4, lid) for lid in created_lines]})
                _logger.info(
                    "Created retention %s for invoice %s with lines %s",
                    retention.id,
                    move.id,
                    created_lines,
                )
                return retention

        except Psycopg2IntegrityError as e:
            msg = str(e).lower()
            if (
                "account_move_unique_name" in msg
                or "duplicate key value" in msg
                or "unique constraint" in msg
            ):
                raise ValidationError(
                    _(
                        "No se pudo crear la retención porque existe un conflicto de nombre de asiento. "
                        "Revisa duplicados en la factura o la secuencia del diario."
                    )
                )
            raise

        except Exception:
            _logger.exception(
                "Unexpected error creating retention for invoice %s", move.id
            )
            raise ValidationError(
                _("Ocurrió un error al crear la retención. Revisa los logs para más detalles.")
            )

        return False

    def action_post(self):
        """Override posting to auto-create simple retentions when applicable."""
        res = super().action_post()
        # After posting, create retentions for each posted move if applicable
        for move in self:
            try:
                # Llamar solo para facturas publicadas
                if move.state == 'posted' and move.is_invoice(include_receipts=True):
                    self._create_simple_retention_if_applicable(move)
            except ValidationError:
                # Re-raise validation errors so the UI shows a friendly message
                raise
            except Exception:
                _logger.exception("Error creating simple retention for invoice %s", move.id)
        return res
