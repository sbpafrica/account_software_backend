import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def generate_excel_template_workbook(*, template_name: str, entity_type: str, columns_schema: list[dict]) -> io.BytesIO:
    """
    Generates a pre-formatted, professional Excel (.xlsx) template workbook.
    Headers use the tenant's customized header_name list in the exact order requested.
    Includes a highlighted sample row to guide data entry.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{entity_type[:25]} Import"

    # Styling constants
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Navy Blue
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    sample_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")  # Slate 100
    sample_font = Font(name="Arial", size=10, italic=True, color="475569")
    thin_border = Border(
        left=Side(style='thin', color="CBD5E1"),
        right=Side(style='thin', color="CBD5E1"),
        top=Side(style='thin', color="CBD5E1"),
        bottom=Side(style='thin', color="CBD5E1")
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center")

    # 1. Header Row
    ws.row_dimensions[1].height = 28
    for col_idx, col in enumerate(columns_schema, start=1):
        header_text = col.get("header_name") or col.get("field_key")
        if col.get("is_required"):
            header_text += " *"  # Asterisk marks mandatory columns

        cell = ws.cell(row=1, column=col_idx, value=header_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    # 2. Sample Data Row (Row 2)
    ws.row_dimensions[2].height = 22
    for col_idx, col in enumerate(columns_schema, start=1):
        sample_val = col.get("sample_value")
        if sample_val is None:
            # Fallback based on data_type
            dtype = col.get("data_type", "string")
            if dtype == "number":
                sample_val = 100.00
            elif dtype == "date":
                sample_val = "2026-01-01"
            elif dtype == "choice" and col.get("choices"):
                sample_val = col["choices"][0]
            else:
                sample_val = f"Example {col.get('header_name')}"

        cell = ws.cell(row=2, column=col_idx, value=sample_val)
        cell.fill = sample_fill
        cell.font = sample_font
        cell.alignment = left_align
        cell.border = thin_border

    # 3. Auto-fit column widths with padding
    for col_idx, col in enumerate(columns_schema, start=1):
        header_name = col.get("header_name", "")
        col_letter = get_column_letter(col_idx)
        max_len = max(len(str(header_name)) + 4, 16)
        ws.column_dimensions[col_letter].width = min(max_len, 40)

    # 4. Instructions Sheet
    info_ws = wb.create_sheet(title="Instructions")
    info_ws.column_dimensions["A"].width = 24
    info_ws.column_dimensions["B"].width = 60

    info_headers = ["Column Header", "Field Description", "Required?", "Type / Allowed Values"]
    for idx, h in enumerate(info_headers, start=1):
        c = info_ws.cell(row=1, column=idx, value=h)
        c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        c.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")

    for r_idx, col in enumerate(columns_schema, start=2):
        info_ws.cell(row=r_idx, column=1, value=col.get("header_name"))
        info_ws.cell(row=r_idx, column=2, value=col.get("description", ""))
        info_ws.cell(row=r_idx, column=3, value="Yes (Required)" if col.get("is_required") else "Optional")
        dtype_str = col.get("data_type", "string")
        if col.get("choices"):
            dtype_str += f" ({', '.join(col['choices'])})"
        info_ws.cell(row=r_idx, column=4, value=dtype_str)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
