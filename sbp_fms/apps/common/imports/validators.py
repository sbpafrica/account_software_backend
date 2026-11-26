import datetime
from decimal import Decimal
from apps.common.models import ImportEntityType
from apps.ledger.models import Account, AccountType
from apps.assets.models import FixedAsset, AssetCategory
from apps.receivables.models import Client
from apps.payables.models import Supplier
from apps.invoicing.models import BillableItem, Invoice, InvoiceType


def validate_import_rows(*, entity_type: str, parsed_rows: list[dict], organization) -> tuple[list[dict], list[dict]]:
    """
    Validates parsed rows against business constraints and database foreign keys for the active organization.
    Returns:
    - valid_rows: list of row dicts that passed all validations
    - errors: list of { row: int, column: str, error: str, raw_value: Any }
    """
    errors = []
    valid_rows = []

    if entity_type == ImportEntityType.CHART_OF_ACCOUNTS:
        seen_codes = set()
        existing_codes = set(Account.objects.values_list('code', flat=True))

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            code = str(f.get("code", "")).strip()
            name = str(f.get("name", "")).strip()
            atype = str(f.get("account_type", "")).strip().upper()

            row_errors = []
            if not code:
                row_errors.append({"row": r_num, "column": "Account Code", "error": "Account Code is required."})
            elif code in seen_codes:
                row_errors.append({"row": r_num, "column": "Account Code", "error": f"Duplicate code '{code}' in upload."})
            elif code in existing_codes:
                row_errors.append({"row": r_num, "column": "Account Code", "error": f"Account '{code}' already exists in Chart of Accounts."})
            else:
                seen_codes.add(code)

            if not name:
                row_errors.append({"row": r_num, "column": "Account Name", "error": "Account Name is required."})

            if not atype or atype not in AccountType.values:
                valid_types = ", ".join(AccountType.values)
                row_errors.append({"row": r_num, "column": "Account Type", "error": f"Invalid type '{atype}'. Must be one of: {valid_types}."})

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    elif entity_type == ImportEntityType.FIXED_ASSET:
        seen_tags = set()
        existing_tags = set(FixedAsset.objects.filter(organization=organization).values_list('asset_tag', flat=True)) if organization else set()
        existing_categories = {c.code.upper(): c for c in AssetCategory.objects.all()}

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            tag = str(f.get("asset_tag", "")).strip()
            name = str(f.get("name", "")).strip()
            cat_code = str(f.get("category_code", "")).strip().upper()
            p_date = f.get("purchase_date")
            p_cost = f.get("purchase_cost")

            row_errors = []
            if not tag:
                row_errors.append({"row": r_num, "column": "Asset Tag", "error": "Asset Tag is required."})
            elif tag in seen_tags:
                row_errors.append({"row": r_num, "column": "Asset Tag", "error": f"Duplicate tag '{tag}' in upload."})
            elif tag in existing_tags:
                row_errors.append({"row": r_num, "column": "Asset Tag", "error": f"Asset tag '{tag}' already exists in your register."})
            else:
                seen_tags.add(tag)

            if not name:
                row_errors.append({"row": r_num, "column": "Asset Name", "error": "Asset Name is required."})

            if not cat_code:
                row_errors.append({"row": r_num, "column": "Category Code", "error": "Category Code is required."})
            elif cat_code not in existing_categories:
                avail = ", ".join(existing_categories.keys()) or "None"
                row_errors.append({"row": r_num, "column": "Category Code", "error": f"Category '{cat_code}' not found. Available categories: {avail}."})
            else:
                f["_category_obj"] = existing_categories[cat_code]

            if not p_date:
                row_errors.append({"row": r_num, "column": "Acquisition Date", "error": "Acquisition Date is required."})
            else:
                try:
                    datetime.date.fromisoformat(str(p_date))
                except (ValueError, TypeError):
                    row_errors.append({"row": r_num, "column": "Acquisition Date", "error": f"Invalid date '{p_date}'. Expected YYYY-MM-DD."})

            if p_cost is None or Decimal(str(p_cost)) <= Decimal('0.00'):
                row_errors.append({"row": r_num, "column": "Purchase Cost", "error": "Purchase Cost must be a positive number greater than 0."})

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    elif entity_type == ImportEntityType.JOURNAL_ENTRY:
        existing_accounts = {a.code: a for a in Account.objects.all()}
        grouped_by_entry = {}

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            p_date = f.get("posting_date")
            acct_code = str(f.get("account_code", "")).strip()
            debit = Decimal(str(f.get("debit") or 0.0))
            credit = Decimal(str(f.get("credit") or 0.0))
            entry_ref = str(f.get("entry_number", "")).strip() or f"BATCH-{p_date}"

            row_errors = []
            if not p_date:
                row_errors.append({"row": r_num, "column": "Posting Date", "error": "Posting Date is required."})
            else:
                try:
                    datetime.date.fromisoformat(str(p_date))
                except (ValueError, TypeError):
                    row_errors.append({"row": r_num, "column": "Posting Date", "error": f"Invalid date '{p_date}'. Expected YYYY-MM-DD."})

            if not acct_code:
                row_errors.append({"row": r_num, "column": "Account Code", "error": "Account Code is required."})
            elif acct_code not in existing_accounts:
                row_errors.append({"row": r_num, "column": "Account Code", "error": f"Account '{acct_code}' does not exist in Chart of Accounts."})
            else:
                f["_account_obj"] = existing_accounts[acct_code]

            if debit == 0 and credit == 0:
                row_errors.append({"row": r_num, "column": "Debit / Credit", "error": "Either Debit or Credit must be greater than 0."})
            elif debit > 0 and credit > 0:
                row_errors.append({"row": r_num, "column": "Debit / Credit", "error": "Cannot specify both Debit and Credit on the same line."})

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)
                grouped_by_entry.setdefault(entry_ref, []).append((r_num, debit, credit))

        # Validate that each journal entry batch balances: sum(debit) == sum(credit)
        for ref, lines in grouped_by_entry.items():
            tot_deb = sum(d for _, d, _ in lines)
            tot_crd = sum(c for _, _, c in lines)
            diff = abs(tot_deb - tot_crd)
            if diff > Decimal('0.005'):
                first_r = lines[0][0]
                errors.append({
                    "row": first_r,
                    "column": "Journal Balance",
                    "error": f"Entry '{ref}' is unbalanced: Total Debits ({tot_deb:.2f}) != Total Credits ({tot_crd:.2f}), diff: {diff:.2f}."
                })

    elif entity_type == ImportEntityType.CLIENT:
        seen_names = set()
        existing_names = set(Client.objects.filter(organization=organization).values_list('name', flat=True)) if organization else set()

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            name = str(f.get("name", "")).strip()

            row_errors = []
            if not name:
                row_errors.append({"row": r_num, "column": "Customer Name", "error": "Customer Name is required."})
            elif name in seen_names:
                row_errors.append({"row": r_num, "column": "Customer Name", "error": f"Duplicate customer '{name}' in upload."})
            elif name in existing_names:
                row_errors.append({"row": r_num, "column": "Customer Name", "error": f"Customer '{name}' already exists."})
            else:
                seen_names.add(name)

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    elif entity_type == ImportEntityType.SUPPLIER:
        seen_names = set()
        existing_names = set(Supplier.objects.filter(organization=organization).values_list('name', flat=True)) if organization else set()

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            name = str(f.get("name", "")).strip()

            row_errors = []
            if not name:
                row_errors.append({"row": r_num, "column": "Vendor Name", "error": "Vendor Name is required."})
            elif name in seen_names:
                row_errors.append({"row": r_num, "column": "Vendor Name", "error": f"Duplicate vendor '{name}' in upload."})
            elif name in existing_names:
                row_errors.append({"row": r_num, "column": "Vendor Name", "error": f"Vendor '{name}' already exists."})
            else:
                seen_names.add(name)

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    elif entity_type == ImportEntityType.BILLABLE_ITEM:
        seen_codes = set()
        existing_codes = set(BillableItem.objects.filter(organization=organization).values_list('code', flat=True)) if organization else set()

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            code = str(f.get("code", "")).strip()
            name = str(f.get("name", "")).strip()
            price = f.get("default_unit_price")

            row_errors = []
            if not code:
                row_errors.append({"row": r_num, "column": "Item Code", "error": "Item Code is required."})
            elif code in seen_codes:
                row_errors.append({"row": r_num, "column": "Item Code", "error": f"Duplicate item code '{code}' in upload."})
            elif code in existing_codes:
                row_errors.append({"row": r_num, "column": "Item Code", "error": f"Item code '{code}' already exists in catalog."})
            else:
                seen_codes.add(code)

            if not name:
                row_errors.append({"row": r_num, "column": "Item Name", "error": "Item Name is required."})

            if price is None or Decimal(str(price)) < Decimal('0.00'):
                row_errors.append({"row": r_num, "column": "Unit Price", "error": "Unit Price must be zero or a positive number."})

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    elif entity_type == ImportEntityType.INVOICE:
        VALID_LINE_TYPES = {"HR_COST", "SERVICE_FEE", "BUS_SHUTTLE", "OTHER"}
        clients_qs = Client.objects.filter(organization=organization) if organization else Client.objects.all()
        client_by_code = {" ".join(c.code.split()).lower(): c for c in clients_qs if c.code}
        client_by_name = {" ".join(c.name.split()).lower(): c for c in clients_qs if c.name}
        existing_inv_nums = set(
            Invoice.objects.filter(organization=organization).values_list('invoice_number', flat=True)
            if organization else Invoice.objects.values_list('invoice_number', flat=True)
        )

        for row in parsed_rows:
            r_num = row["row_number"]
            f = row["fields"]
            extra = row.get("extra_data") or {}

            inv_num = str(f.get("invoice_number") or "").strip()
            client_ref = " ".join(str(f.get("client_code") or "").split())
            issue_dt = f.get("issue_date")
            due_dt = f.get("due_date")
            inv_type = str(f.get("invoice_type") or "STANDARD").strip().upper()
            serial_no = str(extra.get("serial_number") or f.get("serial_number") or "").strip()

            hr_cost = Decimal(str(f.get("hr_cost") or 0))
            service_charge = Decimal(str(f.get("service_charge") or 0))
            unit_price = f.get("unit_price")
            line_desc = str(f.get("line_description") or "").strip()

            # Skip trailing blank/zero rows, monthly totals row, and SUMMARY block (VAT/LEVY/PAYE/WHT/TOTAL)
            if not serial_no and not client_ref and not issue_dt and not inv_num:
                continue

            is_wide_format = (hr_cost > Decimal('0') or service_charge > Decimal('0'))

            row_errors = []
            if inv_num and inv_num in existing_inv_nums:
                row_errors.append({"row": r_num, "column": "INVOICE NO", "error": f"Invoice '{inv_num}' already exists."})

            if not client_ref:
                row_errors.append({"row": r_num, "column": "CLIENT'S NAME", "error": "Client Name or Code is required."})
            elif client_ref.lower() not in client_by_code and client_ref.lower() not in client_by_name:
                row_errors.append({"row": r_num, "column": "CLIENT'S NAME", "error": f"Client '{client_ref}' not found in organization."})

            if not issue_dt:
                row_errors.append({"row": r_num, "column": "ISSUANCE DATE", "error": "Issuance Date is required (YYYY-MM-DD)."})
            if issue_dt and due_dt and due_dt < issue_dt:
                row_errors.append({"row": r_num, "column": "Due Date", "error": "Due Date cannot be earlier than Issue Date."})

            if inv_type not in InvoiceType.values:
                row_errors.append({"row": r_num, "column": "Invoice Type", "error": f"Invalid Invoice Type '{inv_type}'."})

            if is_wide_format:
                if hr_cost < Decimal('0'):
                    row_errors.append({"row": r_num, "column": "HR COST", "error": "HR COST must be 0 or greater."})
                if service_charge < Decimal('0'):
                    row_errors.append({"row": r_num, "column": "SERVICE CHARGE", "error": "SERVICE CHARGE must be 0 or greater."})
            else:
                # Normalized single-line format
                line_type = str(f.get("line_type") or "OTHER").strip().upper()
                qty = f.get("quantity")
                if line_type not in VALID_LINE_TYPES:
                    row_errors.append({
                        "row": r_num, "column": "Line Type",
                        "error": f"Invalid Line Type '{line_type}'. Must be one of: {', '.join(sorted(VALID_LINE_TYPES))}."
                    })
                if not line_desc:
                    row_errors.append({"row": r_num, "column": "Line Description", "error": "Line Description (or HR COST / SERVICE CHARGE) is required."})
                if qty is None or Decimal(str(qty)) <= Decimal('0'):
                    row_errors.append({"row": r_num, "column": "Quantity", "error": "Quantity must be greater than 0."})
                if unit_price is None or Decimal(str(unit_price)) < Decimal('0'):
                    row_errors.append({"row": r_num, "column": "Unit Price", "error": "Unit Price must be 0 or greater."})
                if line_type == "SERVICE_FEE" and unit_price is not None and Decimal(str(unit_price)) == Decimal('0'):
                    row_errors.append({
                        "row": r_num, "column": "Unit Price",
                        "error": "SERVICE_FEE line has zero Unit Price. The service charge amount is required for tax computation."
                    })

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(row)

    return valid_rows, errors
