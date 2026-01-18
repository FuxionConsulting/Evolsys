from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Moneda destino (siempre opuesta a la moneda de la línea / factura)
    converted_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_converted_currency",
        store=True,
    )

    price_unit_company_currency = fields.Monetary(
        string="PU convertido",
        currency_field="converted_currency_id",
        compute="_compute_price_unit_company_currency",
        store=True,
    )

    @api.depends("currency_id", "move_id.currency_id")
    def _compute_converted_currency(self):
        Currency = self.env["res.currency"]
        usd = Currency.search([("name", "in", ["USD", "US$", "US Dollar"])], limit=1)
        ves = Currency.search([("name", "in", ["VES", "VEF", "Bs", "Bs.S"])], limit=1)

        for line in self:
            src = line.currency_id or line.move_id.currency_id
            if not src:
                line.converted_currency_id = False
                continue

            line.converted_currency_id = ves if src == usd else usd

    @api.depends(
        "price_unit",
        "currency_id",
        "move_id.currency_id",
        "move_id.date",
    )
    def _compute_price_unit_company_currency(self):
        for line in self:

            # Ignorar líneas de sección o nota
            if line.display_type in ("line_section", "line_note"):
                line.price_unit_company_currency = 0.0
                continue

            move = line.move_id
            src = line.currency_id or move.currency_id
            tgt = line.converted_currency_id
            date = move.date or fields.Date.today()

            if not src or not tgt:
                line.price_unit_company_currency = line.price_unit
                continue

            # Conversión correcta usando convert()
            converted = src._convert(
                line.price_unit,
                tgt,
                move.company_id,
                date,
            )

            line.price_unit_company_currency = converted
