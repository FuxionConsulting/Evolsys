from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    company_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de la compañía",
        related="order_id.company_id.currency_id",
        readonly=True,
        store=True,
    )

    price_unit_company_currency = fields.Monetary(
        string="PU Convertido",
        currency_field="company_currency_id",
        compute="_compute_price_unit_company_currency",
        store=True,
    )

    @api.depends(
        "price_unit",
        "order_id.currency_id",
        "order_id.company_id.currency_id",
        "order_id.date_order",
    )
    def _compute_price_unit_company_currency(self):
        Rate = self.env["res.currency.rate"]
        Currency = self.env["res.currency"]
        # Prebuscar monedas USD y VES activas para preferencia
        usd = Currency.search([("active", "=", True), ("name", "in", ["USD", "US$", "US Dollar"])], limit=1)
        ves = Currency.search([("active", "=", True), ("name", "in", ["VES", "VEF", "Bs", "Bs.S"])], limit=1)

        for line in self:
            order = line.order_id
            # Preferir moneda de la línea si existe
            src = line.currency_id or order.currency_id
            tgt = line.company_currency_id
            date = order.date_order or fields.Date.today()

            # 1) Conversión directa si src existe y es distinta de la moneda de la compañía
            if src and tgt and src != tgt:
                try:
                    rate = src._get_conversion_rate(src, tgt, order.company_id, date) or 0.0
                except Exception:
                    rate = 0.0

                if rate:
                    line.price_unit_company_currency = line.price_unit * float(rate)
                    continue

            # 2) Si no hay conversión directa o src == tgt, buscar moneda secundaria
            # Preferencia: si la compañía es USD usar VES; si la compañía es VES usar USD; si no, preferir USD
            secondary = False
            if tgt and tgt == usd:
                secondary = ves or usd
            elif tgt and tgt == ves:
                secondary = usd or ves
            else:
                # preferir USD, luego VES, luego primera activa distinta de la compañía
                secondary = usd or ves
            if not secondary:
                secondary = Currency.search([("active", "=", True), ("id", "!=", tgt.id)], limit=1)

            # 3) Si no hay moneda secundaria, fallback
            if not secondary:
                line.price_unit_company_currency = line.price_unit
                continue

            # 4) Buscar rate record para la moneda secundaria hacia la moneda de la compañía
            sec_rate = 0.0
            try:
                rate_rec = Rate.search(
                    [
                        ("currency_id", "=", secondary.id),
                        ("company_id", "=", order.company_id.id),
                        ("name", "<=", date),
                    ],
                    order="name desc",
                    limit=1,
                )
            except Exception:
                rate_rec = False

            if rate_rec:
                comp_rate = getattr(rate_rec, "company_rate", False)
                inv_comp = getattr(rate_rec, "inverse_company_rate", False)
                if comp_rate:
                    sec_rate = float(comp_rate)
                elif inv_comp:
                    try:
                        inv = float(inv_comp)
                        if inv:
                            sec_rate = 1.0 / inv
                    except Exception:
                        sec_rate = 0.0

            # 5) Si no hay sec_rate, intentar buscar en la moneda destino su inverse_company_rate
            if not sec_rate and tgt:
                try:
                    rate_rec_tgt = Rate.search(
                        [
                            ("currency_id", "=", tgt.id),
                            ("company_id", "=", order.company_id.id),
                            ("name", "<=", date),
                        ],
                        order="name desc",
                        limit=1,
                    )
                except Exception:
                    rate_rec_tgt = False

                if rate_rec_tgt:
                    inv_comp = getattr(rate_rec_tgt, "inverse_company_rate", False)
                    comp_rate = getattr(rate_rec_tgt, "company_rate", False)
                    if inv_comp:
                        try:
                            inv = float(inv_comp)
                            if inv:
                                sec_rate = 1.0 / inv
                        except Exception:
                            sec_rate = 0.0
                    elif comp_rate:
                        try:
                            r = float(comp_rate)
                            if r:
                                sec_rate = 1.0 / r
                        except Exception:
                            sec_rate = 0.0

            # 6) Aplicar si hay tasa válida, sino fallback
            if sec_rate:
                line.price_unit_company_currency = line.price_unit * sec_rate
            else:
                line.price_unit_company_currency = line.price_unit
