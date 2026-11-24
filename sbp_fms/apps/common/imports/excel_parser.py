import io
import csv
import re
import datetime
from decimal import Decimal, InvalidOperation
import openpyxl


def _normalize_header(header: str) -> str:
    """Strips whitespace, punctuation, and mandatory asterisks from column header."""
    if not header:
        return ""
    h = str(header).strip()
    h = re.sub(r'[\*\:\(\)]', '', h)
    return ' '.join(h.split()).lower()


def _parse_date_cell(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if not s:
        return None

    # Try common formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # Return as string; validator will flag if invalid


def _parse_number_cell(value, default_val: float = 0.0) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return Decimal(str(default_val))
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = str(value).strip()
    # Strip currency symbols, commas, spaces, quotes
    cleaned = re.sub(r'[^\d\.\-\+]', '', s)
    if not cleaned or cleaned in ('-', '+', '.'):
        return Decimal(str(default_val))
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_spreadsheet_data(*, file_content: bytes, filename: str, columns_schema: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Parses spreadsheet content (.xlsx, .xls, or .csv) matching headers against columns_schema.
    Returns:
    - rows: list of parsed dicts containing {row_number, fields, extra_data, raw_row}
    - unmapped_headers: list of headers from file that did not match any column in schema
    """
    is_csv = filename.lower().endswith('.csv')
    raw_rows = []

    if is_csv:
        # Decode CSV
        text = file_content.decode('utf-8-sig', errors='replace')
        reader = csv.reader(io.StringIO(text))
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
    else:
        # Load OpenPyXL workbook
        wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() != "" for cell in row):
                raw_rows.append([cell if cell is not None else "" for cell in row])

    if not raw_rows:
        return [], []

    header_row = raw_rows[0]
    data_rows = raw_rows[1:]

    # Build mapping from normalized file headers to schema columns
    schema_by_norm_header = {}
    schema_by_norm_key = {}
    for col in columns_schema:
        norm_h = _normalize_header(col.get("header_name", ""))
        norm_k = _normalize_header(col.get("field_key", ""))
        if norm_h:
            schema_by_norm_header[norm_h] = col
        if norm_k:
            schema_by_norm_key[norm_k] = col

    col_index_to_schema = {}
    unmapped_headers = []

    for idx, header in enumerate(header_row):
        norm = _normalize_header(header)
        if not norm:
            continue
        matched_col = schema_by_norm_header.get(norm) or schema_by_norm_key.get(norm)
        if matched_col:
            col_index_to_schema[idx] = matched_col
        else:
            unmapped_headers.append(str(header).strip())

    parsed_rows = []
    for row_idx, row in enumerate(data_rows, start=2):  # 1-based index (Excel row number)
        fields = {}
        extra_data = {}
        raw_row_dict = {}

        # Fill default values from schema first
        for col in columns_schema:
            fkey = col.get("field_key")
            dval = col.get("default_value")
            dtype = col.get("data_type", "string")
            if dtype == "number":
                fields[fkey] = Decimal(str(dval)) if dval != "" and dval is not None else Decimal('0.0000')
            else:
                fields[fkey] = dval if dval is not None else ""

        # Map actual values from file
        for cell_idx, col_spec in col_index_to_schema.items():
            if cell_idx < len(row):
                cell_value = row[cell_idx]
            else:
                cell_value = None

            header_name = col_spec.get("header_name")
            raw_row_dict[header_name] = str(cell_value) if cell_value is not None else ""

            field_key = col_spec.get("field_key")
            dtype = col_spec.get("data_type", "string")
            is_custom = col_spec.get("is_custom", False)

            if cell_value is not None and str(cell_value).strip() != "":
                if dtype == "number":
                    parsed_num = _parse_number_cell(cell_value, default_val=col_spec.get("default_value") or 0.0)
                    val = parsed_num
                elif dtype == "date":
                    val = _parse_date_cell(cell_value)
                elif dtype == "choice":
                    val = str(cell_value).strip().upper()
                else:
                    val = str(cell_value).strip()
            else:
                val = fields.get(field_key)

            if is_custom:
                extra_data[field_key] = val
                extra_data[header_name] = val
            else:
                fields[field_key] = val

        parsed_rows.append({
            "row_number": row_idx,
            "fields": fields,
            "extra_data": extra_data,
            "raw_row": raw_row_dict,
        })

    return parsed_rows, unmapped_headers
