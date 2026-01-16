# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLineSimple(models.Model):
    _name = "account.retention.line.simple"
    _description = "Retention Line Simple"
    _order = "id desc"

    retention_id = fields.Many2one(
        "account.retention.simple",
        string="Retention Voucher",
        required=True,
        ondelete="cascade",
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
        index=True,
    )
    invoice_amount = fields.Monetary(
        string="Taxable Base",
        currency_field="company_currency_id",
    )
    iva_amount = fields.Monetary(
        string="IVA Amount",
        currency_field="company_currency_id",
    )
    retention_amount = fields.Monetary(
        string="Retention Amount",
        currency_field="company_currency_id",
    )

    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        related="retention_id.company_currency_id",
        store=True,
        readonly=True,
    )

    related_percentage_tax_base = fields.Char(
        string="Retention %",
        compute="_compute_related_percentage_tax_base",
        store=True,
    )

    _sql_constraints = [
        ("uniq_retention_move", "UNIQUE(retention_id, move_id)", "A retention line for this invoice already exists."),
        ("check_positive_amounts", "CHECK (invoice_amount >= 0 AND iva_amount >= 0 AND retention_amount >= 0)", "Amounts must be non-negative."),
    ]

    @api.depends('retention_amount', 'iva_amount', 'retention_id.partner_id', 'retention_id')
    def _compute_related_percentage_tax_base(self):
        for rec in self:
            pct_text = ''
            try:
                partner = rec.retention_id.partner_id if rec.retention_id else False
                if partner and getattr(partner, 'retention_iva_rate', False):
                    pct = str(partner.retention_iva_rate)
                    pct_text = pct + '%'
                else:
                    iva = float(rec.iva_amount or 0.0)
                    ret = float(rec.retention_amount or 0.0)
                    if iva and ret:
                        pct_val = (ret / iva) * 100.0
                        pct_text = "{:.2f}%".format(pct_val)
                    else:
                        pct_text = ''
            except Exception:
                _logger.exception("Error computing related_percentage_tax_base for retention line %s", rec.id)
                pct_text = ''
            rec.related_percentage_tax_base = pct_text

    @api.constrains('retention_amount', 'iva_amount', 'invoice_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.retention_amount < 0 or rec.iva_amount < 0 or rec.invoice_amount < 0:
                raise ValidationError(_("Los montos no pueden ser negativos."))
            if rec.iva_amount and rec.retention_amount > rec.iva_amount + (rec.company_currency_id.rounding if rec.company_currency_id else 0.0):
                raise ValidationError(_("El monto de retención no puede ser mayor que el IVA correspondiente."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('retention_id') and not vals.get('company_currency_id'):
                retention = self.env['account.retention.simple'].browse(vals['retention_id'])
                if retention and retention.company_currency_id:
                    vals['company_currency_id'] = retention.company_currency_id.id
            if vals.get('company_currency_id'):
                currency = self.env['res.currency'].browse(vals['company_currency_id'])
                rounding = currency.rounding if currency else None
                if rounding:
                    for key in ('invoice_amount', 'iva_amount', 'retention_amount'):
                        if key in vals and vals[key] is not None:
                            vals[key] = float_round(float(vals[key] or 0.0), precision_rounding=rounding)
        records = super().create(vals_list)
        for rec in records:
            rec._post_create_checks()
        return records

    def write(self, vals):
        if any(k in vals for k in ('invoice_amount', 'iva_amount', 'retention_amount')):
            currency = None
            if self and self[0].company_currency_id:
                currency = self[0].company_currency_id
            rounding = currency.rounding if currency else None
            if rounding:
                for key in ('invoice_amount', 'iva_amount', 'retention_amount'):
                    if key in vals and vals[key] is not None:
                        vals[key] = float_round(float(vals[key] or 0.0), precision_rounding=rounding)
        res = super().write(vals)
        for rec in self:
            rec._post_create_checks()
        return res

    def _post_create_checks(self):
        for rec in self:
            if rec.move_id and rec.retention_id and rec.move_id.company_id != rec.retention_id.company_id:
                _logger.warning("Retention line %s: move.company_id != retention.company_id; prefer retention company", rec.id)
            if rec.move_id and rec.move_id.state not in ('posted', 'draft'):
                _logger.debug("Retention line %s: invoice %s in state %s", rec.id, rec.move_id.id, rec.move_id.state)

    @api.onchange('iva_amount', 'retention_amount')
    def _onchange_compute_pct(self):
        for rec in self:
            try:
                iva = float(rec.iva_amount or 0.0)
                ret = float(rec.retention_amount or 0.0)
                if iva and ret:
                    pct_val = (ret / iva) * 100.0
                    rec.related_percentage_tax_base = "{:.2f}%".format(pct_val)
                else:
                    rec.related_percentage_tax_base = ''
            except Exception:
                rec.related_percentage_tax_base = ''

    @api.model
    def get_lines_for_move(self, move_id):
        return self.search([('move_id', '=', move_id)])
