from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    company_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda de la compañía",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    amount_untaxed_converted = fields.Monetary(
        string="Subtotal convertido",
        currency_field="company_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )
    amount_tax_converted = fields.Monetary(
        string="Impuestos convertidos",
        currency_field="company_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )
    amount_total_converted = fields.Monetary(
        string="Total convertido",
        currency_field="company_currency_id",
        compute="_compute_amounts_converted",
        store=True,
    )

    @api.depends(
        "order_line.price_unit_company_currency",
        "order_line.product_uom_qty",   # 👈 IMPORTANTE: en ventas es product_uom_qty
        "order_line.tax_ids",
        "order_line.discount",
        "order_line.price_unit",
        "order_line.price_subtotal",
        "order_line.price_total",
        "order_line.price_tax",
        "order_line.product_id",
        "partner_id",
        "company_id",
        "date_order",
    )
    def _compute_amounts_converted(self):
        for order in self:
            subtotal_conv = 0.0
            tax_conv = 0.0
            date = order.date_order or fields.Date.today()

            for line in order.order_line:
                pu_conv = line.price_unit_company_currency if line.price_unit_company_currency else line.price_unit
                qty = line.product_uom_qty or 0.0   # 👈 también product_uom_qty aquí

                line_sub_conv = float(pu_conv) * float(qty)
                subtotal_conv += line_sub_conv

                if line.tax_ids:
                    taxes = line.tax_ids.compute_all(
                        pu_conv,
                        order.company_id.currency_id,
                        qty,
                        product=line.product_id,
                        partner=order.partner_id,
                    )
                else:
                    taxes = {
                        "taxes": [],
                        "total_excluded": line_sub_conv,
                        "total_included": line_sub_conv,
                    }

                tax_amounts = sum([t.get("amount", 0.0) for t in taxes.get("taxes", [])])
                tax_conv += float(tax_amounts)

            total_conv = subtotal_conv + tax_conv

            order.amount_untaxed_converted = subtotal_conv
            order.amount_tax_converted = tax_conv
            order.amount_total_converted = total_conv
