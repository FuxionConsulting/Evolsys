from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    company_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de la compañía",
        related="order_id.company_id.currency_id",
        readonly=True,
        store=True,
    )

    price_unit_company_currency = fields.Monetary(
        string="Precio unitario en moneda de compañía",
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
        for line in self:
            if line.order_id.currency_id and line.order_id.currency_id != line.company_currency_id:
                rate = line.order_id.currency_id._get_conversion_rate(
                    line.order_id.currency_id,
                    line.company_currency_id,
                    line.order_id.company_id,
                    line.order_id.date_order or fields.Date.today(),
                )
                line.price_unit_company_currency = line.price_unit * rate
            else:
                line.price_unit_company_currency = line.price_unit
