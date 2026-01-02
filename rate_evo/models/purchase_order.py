from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # Moneda destino (siempre la opuesta)
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

    @api.depends("currency_id")
    def _compute_converted_currency(self):
        Currency = self.env["res.currency"]
        usd = Currency.search([("name", "in", ["USD", "US$", "US Dollar"])], limit=1)
        ves = Currency.search([("name", "in", ["VES", "VEF", "Bs", "Bs.S"])], limit=1)

        for line in self:
            src = line.currency_id or line.order_id.currency_id
            if src == usd:
                line.converted_currency_id = ves
            else:
                line.converted_currency_id = usd

    @api.depends("price_unit", "currency_id", "order_id.date_order")
    def _compute_price_unit_company_currency(self):
        Rate = self.env["res.currency.rate"]

        for line in self:
            order = line.order_id
            src = line.currency_id or order.currency_id
            tgt = line.converted_currency_id
            date = order.date_order or fields.Date.today()

            if not src or not tgt:
                line.price_unit_company_currency = line.price_unit
                continue

            # Intento directo
            try:
                rate = src._get_conversion_rate(src, tgt, order.company_id, date)
            except Exception:
                rate = 0.0

            if rate:
                line.price_unit_company_currency = line.price_unit * rate
            else:
                line.price_unit_company_currency = line.price_unit


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # ✅ NUEVO: Flag para mostrar el botón solo cuando hace falta
    needs_conversion_update = fields.Boolean(
        string="Requiere actualización de conversión",
        default=False,
        store=True,
    )

    converted_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_converted_currency",
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

        for order in self:
            src = order.currency_id
            if src == usd:
                order.converted_currency_id = ves
            else:
                order.converted_currency_id = usd

    # ✅ NUEVO: Cuando cambias la moneda y ya hay líneas → mostrar botón
    @api.onchange("currency_id")
    def _onchange_currency_id_set_update_flag(self):
        for order in self:
            if order.order_line:
                order.needs_conversion_update = True

    @api.depends(
        "order_line.price_unit_company_currency",
        "order_line.product_qty",
        "order_line.tax_ids",
        "order_line.price_unit",
        "order_line.price_subtotal",
        "order_line.price_total",
        "order_line.price_tax",
        "order_line.product_id",
        "partner_id",
        "currency_id",
        "date_order",
    )
    def _compute_amounts_converted(self):
        for order in self:
            subtotal = 0.0
            taxes_total = 0.0

            for line in order.order_line:
                pu = line.price_unit_company_currency or line.price_unit
                qty = line.product_qty or 0.0

                line_sub = pu * qty
                subtotal += line_sub

                if line.tax_ids:
                    taxes = line.tax_ids.compute_all(
                        pu,
                        order.converted_currency_id,
                        qty,
                        product=line.product_id,
                        partner=order.partner_id,
                    )
                    taxes_total += sum(t["amount"] for t in taxes.get("taxes", []))
                else:
                    taxes_total += 0.0

            order.amount_untaxed_converted = subtotal
            order.amount_tax_converted = taxes_total
            order.amount_total_converted = subtotal + taxes_total

    def action_update_converted_prices(self):
        for order in self:
            order.order_line._compute_price_unit_company_currency()
            order._compute_amounts_converted()
            order.needs_conversion_update = False  # ✅ Ocultar botón después de actualizar
