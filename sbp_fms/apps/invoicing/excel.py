import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def _resolve_invoice_cell_value(inv, line, col: dict):
    """Maps a schema column definition to the corresponding invoice/line or custom field value."""
    key = col.get("system_field") or col.get("field_key") or ""
    field_key = col.get("field_key") or key

    if key == "invoice_number":
        return inv.invoice_number
    if key == "client_code":
        return inv.client.code if getattr(inv.client, "code", None) else inv.client.name
    if key == "client_name":
        return inv.client.name
    if key == "issue_date":
        return inv.issue_date.isoformat() if inv.issue_date else ""
    if key == "due_date":
        return inv.due_date.isoformat() if inv.due_date else ""
    if key == "invoice_type":
        return inv.invoice_type
    if key == "status":
        return inv.status
    if key == "currency":
        return inv.currency
    if key == "reference_number":
        return inv.reference_number or ""
    if key == "notes":
        return inv.notes or ""
    if key == "subtotal":
        return float(inv.subtotal)
    if key == "tax_amount":
        return float(inv.tax_amount)
    if key == "total_amount":
        return float(inv.total_amount)
    if key == "amount_paid":
        return float(inv.amount_paid)
    if key == "balance_due":
        return float(inv.balance_due)

    if line is not None:
        if key == "line_description":
            return line.description
        if key == "quantity":
            return float(line.quantity)
        if key == "unit_of_measurement":
            return line.unit_of_measurement
        if key == "unit_price":
            return float(line.unit_price)
        if key == "discount_amount":
            return float(line.discount_amount)
        if key == "tax_code":
            return line.tax_code
        if key == "line_total":
            return float(line.line_total)
        if isinstance(line.custom_fields, dict) and field_key in line.custom_fields:
            return line.custom_fields[field_key]

    if isinstance(inv.custom_fields, dict) and field_key in inv.custom_fields:
        return inv.custom_fields[field_key]

    return col.get("default_value", "")


def generate_invoices_excel_export(*, invoices, columns_schema: list[dict]) -> io.BytesIO:
    """
    Exports existing invoices to a formatted .xlsx workbook using the tenant's
    customized Excel header setup (columns_schema).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoices Export"

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center")

    # 1. Header Row
    ws.row_dimensions[1].height = 28
    for col_idx, col in enumerate(columns_schema, start=1):
        header_text = col.get("header_name") or col.get("field_key")
        cell = ws.cell(row=1, column=col_idx, value=header_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    # 2. Data Rows
    row_idx = 2
    for inv in invoices:
        lines = list(inv.lines.all())
        if not lines:
            lines = [None]
        for line in lines:
            ws.row_dimensions[row_idx].height = 20
            for col_idx, col in enumerate(columns_schema, start=1):
                val = _resolve_invoice_cell_value(inv, line, col)
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.alignment = left_align
                cell.border = thin_border
            row_idx += 1

    # 3. Auto-fit column widths
    for col_idx, col in enumerate(columns_schema, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(col.get("header_name") or ""))
        for r in range(2, row_idx):
            val = ws.cell(row=r, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 45)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
