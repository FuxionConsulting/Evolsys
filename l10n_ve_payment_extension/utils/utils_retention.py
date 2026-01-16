# user/l10n_ve_payment_extension/utils/utils_retention.py
from odoo import Command, _
import logging

_logger = logging.getLogger(__name__)


def search_invoices_with_taxes(AccountMove, domain):
    """
    Search for invoices with taxes for the given domain.

    More robust: consider any tax on any line with amount > 0 or taxes flagged as IVA.
    """
    invoices = AccountMove.search(domain)
    def invoice_has_positive_tax(inv):
        for line in inv.line_ids:
            for tax in line.tax_ids:
                # accept if tax amount > 0 OR tax explicitly marked as iva_tax OR tax type is purchase/sale
                if (getattr(tax, "amount", 0) and float(tax.amount) > 0) or getattr(tax, "iva_tax", False) or tax.type_tax_use in ("purchase", "sale"):
                    return True
        return False

    return invoices.filtered(lambda i: invoice_has_positive_tax(i))


def load_retention_lines(invoices, Retention):
    """
    Load retention lines for the given invoices.

    invoices: recordset of account.move
    Retention: either a retention record (self) or the model recordset (self.env['account.retention'])
    Returns a list of odoo Command.create(...) entries for One2many assignment.
    """
    if not invoices:
        return []

    retention_lines_data = []

    # Detect if Retention is a record (has id) or the model (no id)
    is_model = not bool(getattr(Retention, "id", False))
    retention_record = None if is_model else Retention

    for inv in invoices:
        try:
            if retention_record:
                # Preferred: call the instance method on the actual retention record (self)
                data = retention_record.compute_retention_lines_data(inv)
            else:
                # Fallback: build a temp retention with sensible parent values so compute has context
                parent_vals = {
                    "partner_id": getattr(inv, "partner_id", False) and inv.partner_id.id or False,
                    "type_retention": "iva",  # default; caller may override if needed
                    "type": inv.move_type or "in_invoice",
                    "date": getattr(inv, "invoice_date", False) or getattr(inv, "date", False),
                    "company_id": getattr(inv, "company_id", False) and inv.company_id.id or False,
                    "company_currency_id": getattr(inv.company_id, "currency_id", False) and inv.company_id.currency_id.id or False,
                    "foreign_currency_id": getattr(inv, "currency_id", False) and inv.currency_id.id or False,
                }
                temp_ret = Retention.new(parent_vals)
                data = temp_ret.compute_retention_lines_data(inv)

            if data:
                retention_lines_data.append(data)
            else:
                _logger.debug("load_retention_lines: compute_retention_lines_data returned empty for invoice %s", getattr(inv, "id", inv))
        except Exception as e:
            _logger.exception(
                "Error computing retention lines for invoice %s: %s", getattr(inv, "id", inv), e
            )
            raise

    # Convert to commands for One2many (Command.create)
    # data is expected to be a list of dicts; flatten and create commands
    return [Command.create(line) for lines in retention_lines_data for line in lines]

def get_current_date_format(date):
    """
    Computes a date format consisting of the name of the month plus the year.

    Params
    ------
    date: datetime.date or fields.Date value

    Returns
    -------
    string
        The month and the year in the desired format, translated.
    """
    months = (
        _("January"),
        _("February"),
        _("March"),
        _("April"),
        _("May"),
        _("June"),
        _("July"),
        _("August"),
        _("September"),
        _("October"),
        _("November"),
        _("December"),
    )
    # If 'date' is a string (e.g., '2026-01-12'), try to parse year/month
    try:
        month = date.month
        year = date.year
    except Exception:
        # fallback: try to split string YYYY-MM-DD
        try:
            parts = str(date).split("-")
            year = int(parts[0])
            month = int(parts[1])
        except Exception:
            # if all fails, return empty string
            return ""

    month_name = months[month - 1] if 1 <= month <= 12 else ""
    return "{} {}".format(month_name, year)
