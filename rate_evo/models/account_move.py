from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = "account.move"

    exchange_rate = fields.Float(
        string="Tasa de cambio",
        digits=(16, 6),
        compute="_compute_exchange_rate",
        store=True,
        readonly=True,
    )

    @api.depends("currency_id", "date")
    def _compute_exchange_rate(self):
        for move in self:
            if move.currency_id and move.currency_id != move.company_id.currency_id:
                rate = move.currency_id._get_conversion_rate(
                    move.currency_id,
                    move.company_id.currency_id,
                    move.company_id,
                    move.date or fields.Date.today(),
                )
                move.exchange_rate = rate
            else:
                move.exchange_rate = 1.0

    # ⭐ AHORA PERSISTENTE Y ACTUALIZABLE
    previous_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda anterior",
        store=True,
    )

    converted_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_converted_currency",
        store=True,
    )

    needs_conversion_update = fields.Boolean(
        string="Requiere actualización de conversión",
        default=False,
        store=True,
    )

    amount_untaxed_converted = fields.Monetary(
        string="Subtotal convertido",
        currency_field="converted_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )
    amount_tax_converted = fields.Monetary(
        string="Impuestos convertidos",
        currency_field="converted_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )
    amount_total_converted = fields.Monetary(
        string="Total convertido",
        currency_field="converted_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )

    @api.depends("currency_id")
    def _compute_converted_currency(self):
        Currency = self.env["res.currency"]
        usd = Currency.search([("name", "in", ["USD", "US$", "US Dollar"])], limit=1)
        ves = Currency.search([("name", "in", ["VES", "VEF", "Bs", "Bs.S"])], limit=1)

        for move in self:
            src = move.currency_id or move.company_id.currency_id
            move.converted_currency_id = ves if src == usd else usd

    @api.onchange("currency_id")
    def _onchange_currency_id_set_update_flag(self):
        for move in self:
            if move.invoice_line_ids:
                move.needs_conversion_update = True
                move.previous_currency_id = move.currency_id._origin

    # ⭐ GARANTIZA QUE previous_currency_id SE ACTUALICE EN BD
    @api.model
    def create(self, vals):
        if "currency_id" in vals:
            vals["previous_currency_id"] = vals["currency_id"]
        return super().create(vals)

    def write(self, vals):
        if "currency_id" in vals:
            for move in self:
                if move.currency_id and move.currency_id.id != vals["currency_id"]:
                    vals["previous_currency_id"] = move.currency_id.id
        return super().write(vals)

    @api.depends(
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "currency_id",
        "converted_currency_id",
        "date",
        "invoice_line_ids.price_unit",
        "invoice_line_ids.price_unit_company_currency",
    )
    def _compute_amounts_converted(self):
        for move in self:
            if not move.converted_currency_id:
                move.amount_untaxed_converted = move.amount_untaxed
                move.amount_tax_converted = move.amount_tax
                move.amount_total_converted = move.amount_total
                continue

            src = move.currency_id or move.company_id.currency_id
            tgt = move.converted_currency_id
            date = move.date or fields.Date.today()

            move.amount_untaxed_converted = src._convert(
                move.amount_untaxed, tgt, move.company_id, date
            )
            move.amount_tax_converted = src._convert(
                move.amount_tax, tgt, move.company_id, date
            )
            move.amount_total_converted = src._convert(
                move.amount_total, tgt, move.company_id, date
            )

    def action_update_converted_prices(self):
        for move in self:

            old_currency = move.previous_currency_id
            new_currency = move.currency_id
            company = move.company_id
            date = move.date or fields.Date.today()

            # ⭐ RECONVERSIÓN REAL DEL PRICE_UNIT
            if old_currency and new_currency and old_currency != new_currency:

                for line in move.line_ids:

                    if line.display_type in ("line_section", "line_note"):
                        continue

                    original_amount = line.price_unit

                    new_amount = old_currency._convert(
                        original_amount,
                        new_currency,
                        company,
                        date,
                    )

                    line.price_unit = new_amount

            # ⭐ Recalcular impuestos, totales y líneas contables (universal)
            move.write({})

            move.line_ids._compute_converted_currency()
            move.line_ids._compute_price_unit_company_currency()

            move._compute_amounts_converted()

            move.needs_conversion_update = False
