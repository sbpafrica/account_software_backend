import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings

from apps.common.models import (
    ImportTemplate, ImportJob, ImportEntityType, ImportJobStatus, AuditLog
)
from apps.common.cache import CacheManager
from apps.common.imports.defaults import DEFAULT_IMPORT_SCHEMAS, get_default_schema_for_entity
from apps.common.imports.excel_generator import generate_excel_template_workbook
from apps.common.imports.excel_parser import parse_spreadsheet_data
from apps.common.imports.validators import validate_import_rows

from apps.ledger.models import Account, AccountType, JournalEntry, JournalLine, JournalEntryStatus
from apps.assets.models import FixedAsset, AssetCategory, AssetStatus, DepreciationMethod
from apps.receivables.models import Client
from apps.payables.models import Supplier
from apps.invoicing.models import BillableItem, InvoiceType
from apps.invoicing.services import InvoicingService


class ImportService:
    @staticmethod
    def get_or_create_default_template(*, organization, entity_type: str) -> ImportTemplate:
        """Retrieves the active tenant template or initializes it from the default schema."""
        template = ImportTemplate.objects.filter(
            organization=organization,
            entity_type=entity_type,
            is_default=True
        ).first()

        if not template:
            template = ImportTemplate.objects.filter(
                organization=organization,
                entity_type=entity_type
            ).first()

        if not template:
            default_schema = get_default_schema_for_entity(entity_type)
            name = f"Default {dict(ImportEntityType.choices).get(entity_type, entity_type)} Template"
            template = ImportTemplate.objects.create(
                organization=organization,
                name=name,
                entity_type=entity_type,
                description=f"Standard system layout for {entity_type}",
                columns_schema=default_schema,
                is_default=True
            )
        return template

    @staticmethod
    def template_create(
        *,
        organization,
        user,
        name: str,
        entity_type: str,
        columns_schema: list[dict],
        description: str = "",
        is_default: bool = False
    ) -> ImportTemplate:
        """Creates a custom import template with user-defined column names and custom fields."""
        if not name or not name.strip():
            raise ValidationError("Template name is required.")
        if entity_type not in ImportEntityType.values:
            raise ValidationError(f"Invalid entity type '{entity_type}'.")
        if not columns_schema or not isinstance(columns_schema, list):
            raise ValidationError("columns_schema must be a non-empty list of column definitions.")

        # Ensure required system fields are present
        req_system_fields = {
            col["system_field"]
            for col in DEFAULT_IMPORT_SCHEMAS.get(entity_type, [])
            if col.get("is_required") and col.get("system_field")
        }
        provided_system_fields = {
            col.get("system_field")
            for col in columns_schema
            if col.get("system_field")
        }
        missing_req = req_system_fields - provided_system_fields
        if missing_req:
            # Check if default_values are provided for missing required fields
            unhandled = []
            for m in missing_req:
                has_default = any(c.get("field_key") == m and c.get("default_value") not in ("", None) for c in columns_schema)
                if not has_default:
                    unhandled.append(m)
            if unhandled:
                raise ValidationError(f"Missing mandatory fields for {entity_type}: {', '.join(unhandled)}")

        if is_default and organization:
            ImportTemplate.objects.filter(organization=organization, entity_type=entity_type).update(is_default=False)

        template = ImportTemplate.objects.create(
            organization=organization,
            created_by=user,
            name=name.strip(),
            entity_type=entity_type,
            description=description.strip(),
            columns_schema=columns_schema,
            is_default=is_default
        )
        return template

    @staticmethod
    def template_update(
        *,
        template_id,
        organization,
        name: str = None,
        columns_schema: list[dict] = None,
        description: str = None,
        is_default: bool = None
    ) -> ImportTemplate:
        """Updates an existing template (renaming columns, adding custom columns, deleting columns)."""
        qs = ImportTemplate.objects.all()
        if organization:
            qs = qs.filter(organization=organization)
        template = qs.filter(id=template_id).first()
        if not template:
            raise ValidationError(f"Import template '{template_id}' not found.")

        if name is not None:
            template.name = name.strip()
        if description is not None:
            template.description = description.strip()
        if is_default is not None:
            if is_default and organization:
                ImportTemplate.objects.filter(
                    organization=organization,
                    entity_type=template.entity_type
                ).exclude(id=template.id).update(is_default=False)
            template.is_default = is_default

        if columns_schema is not None:
            if not isinstance(columns_schema, list) or len(columns_schema) == 0:
                raise ValidationError("columns_schema must be a non-empty list.")
            template.columns_schema = columns_schema

        template.save()
        return template

    @staticmethod
    def template_delete(*, template_id, organization) -> bool:
        qs = ImportTemplate.objects.all()
        if organization:
            qs = qs.filter(organization=organization)
        template = qs.filter(id=template_id).first()
        if not template:
            raise ValidationError(f"Import template '{template_id}' not found.")
        template.delete()
        return True

    @staticmethod
    def template_reset_default(*, organization, entity_type: str) -> ImportTemplate:
        """Resets the tenant's template for an entity type to the official standard layout."""
        default_schema = get_default_schema_for_entity(entity_type)
        template = ImportTemplate.objects.filter(
            organization=organization,
            entity_type=entity_type,
            is_default=True
        ).first()

        if template:
            template.columns_schema = default_schema
            template.save()
        else:
            name = f"Standard {dict(ImportEntityType.choices).get(entity_type, entity_type)} Template"
            template = ImportTemplate.objects.create(
                organization=organization,
                name=name,
                entity_type=entity_type,
                columns_schema=default_schema,
                is_default=True
            )
        return template

    @staticmethod
    def download_template_workbook(*, template_id=None, entity_type: str = None, organization=None):
        """Generates an in-memory .xlsx workbook for the requested template or entity type."""
        template = None
        if template_id:
            qs = ImportTemplate.objects.all()
            if organization:
                qs = qs.filter(organization=organization)
            template = qs.filter(id=template_id).first()

        if not template and entity_type:
            template = ImportService.get_or_create_default_template(
                organization=organization,
                entity_type=entity_type
            )

        if not template:
            raise ValidationError("Either valid template_id or entity_type must be specified.")

        return generate_excel_template_workbook(
            template_name=template.name,
            entity_type=template.entity_type,
            columns_schema=template.columns_schema
        ), template

    @staticmethod
    def preview_import_file(
        *,
        organization,
        user,
        file_obj,
        template_id=None,
        entity_type: str = None
    ) -> dict:
        """
        Executes a safe, non-mutating validation dry-run of an uploaded Excel or CSV file.
        Matches headers against the template's customized column schema.
        Returns parsed rows, validation status, and row-by-row error diagnostics.
        """
        if not organization and user and hasattr(user, 'organization_memberships'):
            membership = user.organization_memberships.filter(is_default=True).first() or user.organization_memberships.first()
            if membership:
                organization = membership.organization

        template = None
        if template_id:
            template = ImportTemplate.objects.filter(id=template_id).first()
            if template:
                entity_type = template.entity_type

        if not template and entity_type:
            template = ImportService.get_or_create_default_template(
                organization=organization,
                entity_type=entity_type
            )

        if not template:
            raise ValidationError("Could not resolve template for preview.")

        # Read file
        content = file_obj.read()
        file_size = len(content)
        filename = getattr(file_obj, 'name', 'import.xlsx')

        # Parse
        parsed_rows, unmapped_headers = parse_spreadsheet_data(
            file_content=content,
            filename=filename,
            columns_schema=template.columns_schema
        )

        # Validate
        valid_rows, errors = validate_import_rows(
            entity_type=template.entity_type,
            parsed_rows=parsed_rows,
            organization=organization
        )

        can_import = len(errors) == 0 and len(valid_rows) > 0

        # Create or update ImportJob for tracking
        job = ImportJob.objects.create(
            organization=organization,
            template=template,
            entity_type=template.entity_type,
            file_name=filename,
            file_size_bytes=file_size,
            total_rows=len(parsed_rows),
            successful_rows=len(valid_rows) if can_import else 0,
            failed_rows=len(errors),
            status=ImportJobStatus.PREVIEWED,
            error_summary=errors[:50],  # Keep first 50 errors in log
            executed_by=user
        )

        return {
            "job_id": str(job.id),
            "template_id": str(template.id),
            "template_name": template.name,
            "entity_type": template.entity_type,
            "file_name": filename,
            "total_rows": len(parsed_rows),
            "valid_rows_count": len(valid_rows),
            "error_rows_count": len(errors),
            "can_import": can_import,
            "errors": errors,
            "unmapped_headers": unmapped_headers,
            "preview_rows": [
                {
                    "row_number": r["row_number"],
                    "fields": {
                        k: str(v) if isinstance(v, (Decimal, datetime.date, datetime.datetime)) else v
                        for k, v in r["fields"].items()
                        if not k.startswith('_')
                    },
                    "extra_data": r["extra_data"],
                    "is_valid": r in valid_rows
                }
                for r in parsed_rows[:30]
            ],
            # Pass validated payload for fast commit
            "_validated_data": [
                {
                    "row_number": r["row_number"],
                    "fields": {
                        k: str(v) if isinstance(v, (Decimal, datetime.date, datetime.datetime)) else v
                        for k, v in r["fields"].items()
                        if not k.startswith('_')
                    },
                    "extra_data": r["extra_data"]
                }
                for r in valid_rows
            ] if can_import else []
        }

    @staticmethod
    @transaction.atomic
    def commit_import_job(
        *,
        job_id,
        organization,
        user,
        validated_rows: list[dict] = None
    ) -> dict:
        """
        Executes an atomic batch import of validated rows into domain models.
        Assigns the active tenant organization, generates AuditLog, flushes tenant caches.
        """
        job = ImportJob.objects.filter(id=job_id).first()
        if not job:
            raise ValidationError(f"Import job '{job_id}' not found.")
        if job.status == ImportJobStatus.COMPLETED:
            raise ValidationError(f"Import job '{job_id}' has already been committed.")

        if not organization and job.organization:
            organization = job.organization
        if not organization and user and hasattr(user, 'organization_memberships'):
            membership = user.organization_memberships.filter(is_default=True).first() or user.organization_memberships.first()
            if membership:
                organization = membership.organization

        entity_type = job.entity_type
        imported_count = 0

        # If validated rows not passed in body, re-parse from file if cached, or require rows
        if not validated_rows:
            raise ValidationError("Validated rows payload required for commit confirmation.")

        if entity_type == ImportEntityType.CHART_OF_ACCOUNTS:
            accounts_to_create = []
            for r in validated_rows:
                f = r["fields"]
                code = str(f.get("code")).strip()
                name = str(f.get("name")).strip()
                atype = str(f.get("account_type")).strip().upper()
                curr = str(f.get("currency") or "GHS").strip().upper()
                op_bal = Decimal(str(f.get("opening_balance") or 0.0))
                desc = str(f.get("description") or "").strip()

                # Add extra columns into description if present
                if r.get("extra_data"):
                    extra_str = "; ".join(f"{k}: {v}" for k, v in r["extra_data"].items() if v)
                    desc = f"{desc} | {extra_str}".strip(" |")

                accounts_to_create.append(Account(
                    code=code,
                    name=name,
                    account_type=atype,
                    subtype=str(f.get("subtype") or "").strip(),
                    currency=curr,
                    opening_balance=op_bal,
                    description=desc,
                    is_active=True
                ))
            Account.objects.bulk_create(accounts_to_create)
            imported_count = len(accounts_to_create)
            CacheManager.delete_pattern("fms:ledger:*")

        elif entity_type == ImportEntityType.FIXED_ASSET:
            categories_map = {c.code.upper(): c for c in AssetCategory.objects.all()}
            for r in validated_rows:
                f = r["fields"]
                tag = str(f.get("asset_tag")).strip()
                name = str(f.get("name")).strip()
                cat_code = str(f.get("category_code")).strip().upper()
                cat = categories_map.get(cat_code)
                p_date = f.get("purchase_date")
                p_cost = Decimal(str(f.get("purchase_cost") or 0.0))
                s_val = Decimal(str(f.get("salvage_value") or 0.0))
                life = int(f.get("useful_life_years") or 5)
                method = str(f.get("depreciation_method") or DepreciationMethod.STRAIGHT_LINE).upper()
                accum_depr = Decimal(str(f.get("accumulated_depreciation") or 0.0))
                nbv = max(p_cost - accum_depr, Decimal('0.0000'))
                desc = str(f.get("description") or "").strip()

                if r.get("extra_data"):
                    extra_str = "; ".join(f"{k}: {v}" for k, v in r["extra_data"].items() if v)
                    desc = f"{desc} | {extra_str}".strip(" |")

                rate = (Decimal('100.0000') / Decimal(str(life))) if life > 0 else Decimal('0.0000')

                FixedAsset.objects.create(
                    organization=organization,
                    asset_tag=tag,
                    name=name,
                    category=cat,
                    purchase_date=p_date,
                    purchase_cost=p_cost,
                    salvage_value=s_val,
                    useful_life_years=life,
                    depreciation_method=method,
                    depreciation_rate_pct=rate,
                    accumulated_depreciation=accum_depr,
                    net_book_value=nbv,
                    status=AssetStatus.ACTIVE,
                    department=str(f.get("department") or "").strip(),
                    location=str(f.get("location") or "").strip(),
                    description=desc,
                    country_code=getattr(organization, 'country_code', 'GH')
                )
                imported_count += 1
            CacheManager.delete_pattern("fms:assets:*")

        elif entity_type == ImportEntityType.JOURNAL_ENTRY:
            # Group lines by entry reference
            grouped = {}
            for r in validated_rows:
                f = r["fields"]
                ref = str(f.get("entry_number") or f"MIG-{f.get('posting_date')}").strip()
                grouped.setdefault(ref, []).append(r)

            accounts_map = {a.code: a for a in Account.objects.all()}

            for ref, lines in grouped.items():
                first_f = lines[0]["fields"]
                p_date = first_f.get("posting_date")
                entry = JournalEntry.objects.create(
                    organization=organization,
                    entry_number=ref,
                    posting_date=p_date,
                    description=f"Bulk Import Migration - {ref}",
                    status=JournalEntryStatus.POSTED,
                    source_module="IMPORT",
                    created_by=user,
                    approved_by=user
                )
                for l in lines:
                    lf = l["fields"]
                    acct = accounts_map.get(str(lf.get("account_code")).strip())
                    deb = Decimal(str(lf.get("debit") or 0.0))
                    crd = Decimal(str(lf.get("credit") or 0.0))
                    JournalLine.objects.create(
                        entry=entry,
                        account=acct,
                        debit=deb,
                        credit=crd
                    )
                imported_count += 1
            CacheManager.delete_pattern("fms:ledger:*")

        elif entity_type == ImportEntityType.CLIENT:
            for r in validated_rows:
                f = r["fields"]
                name = str(f.get("name")).strip()
                code = str(f.get("code") or "").strip() or None
                email = str(f.get("email") or "").strip()
                phone = str(f.get("telephone") or "").strip()
                tax_id = str(f.get("tax_id") or "").strip()
                addr = str(f.get("billing_address") or "").strip()
                limit = Decimal(str(f.get("credit_limit") or 0.0))
                terms = int(f.get("payment_terms_days") or 30)
                op_bal = Decimal(str(f.get("opening_balance") or 0.0))

                Client.objects.create(
                    organization=organization,
                    name=name,
                    code=code,
                    email=email,
                    telephone=phone,
                    tax_id=tax_id,
                    billing_address=addr,
                    credit_limit=limit,
                    payment_terms_days=terms,
                    opening_balance=op_bal,
                    country_code=getattr(organization, 'country_code', 'GH'),
                    is_active=True
                )
                imported_count += 1
            CacheManager.delete_pattern("fms:receivables:*")

        elif entity_type == ImportEntityType.SUPPLIER:
            for r in validated_rows:
                f = r["fields"]
                name = str(f.get("name")).strip()
                email = str(f.get("email") or "").strip()
                phone = str(f.get("telephone") or "").strip()
                tax_id = str(f.get("tax_id") or "").strip()
                addr = str(f.get("address") or "").strip()
                bank_name = str(f.get("bank_name") or "").strip()
                bank_acc = str(f.get("bank_account_number") or "").strip()
                terms = int(f.get("payment_terms_days") or 30)
                op_bal = Decimal(str(f.get("opening_balance") or 0.0))

                Supplier.objects.create(
                    organization=organization,
                    name=name,
                    email=email,
                    telephone=phone,
                    tax_id=tax_id,
                    address=addr,
                    bank_name=bank_name,
                    bank_account_number=bank_acc,
                    payment_terms_days=terms,
                    opening_balance=op_bal,
                    country_code=getattr(organization, 'country_code', 'GH'),
                    is_active=True
                )
                imported_count += 1
            CacheManager.delete_pattern("fms:payables:*")

        elif entity_type == ImportEntityType.BILLABLE_ITEM:
            accounts_map = {a.code: a for a in Account.objects.all()}
            for r in validated_rows:
                f = r["fields"]
                code = str(f.get("code")).strip()
                name = str(f.get("name")).strip()
                desc = str(f.get("description") or "").strip()
                price = Decimal(str(f.get("default_unit_price") or 0.0))
                unit = str(f.get("default_unit") or "UNIT").strip().upper()
                income_code = str(f.get("income_account_code") or "").strip()
                inc_acct = accounts_map.get(income_code)

                BillableItem.objects.create(
                    organization=organization,
                    code=code,
                    name=name,
                    description=desc,
                    default_unit_price=price,
                    default_unit=unit,
                    income_account=inc_acct,
                    is_active=True
                )
                imported_count += 1
            CacheManager.delete_pattern("fms:invoicing:*")

        elif entity_type == ImportEntityType.INVOICE:
            clients_qs = Client.objects.filter(organization=organization) if organization else Client.objects.all()
            client_by_code = {c.code.strip().lower(): c for c in clients_qs if c.code}
            client_by_name = {c.name.strip().lower(): c for c in clients_qs if c.name}

            # LINE TYPE → TAX CODE rules (matches INCOME_2025.xlsx logic)
            # HR_COST lines: manpower pass-through → EXEMPT (no Ghana indirect tax on the HR cost itself)
            # SERVICE_FEE lines: management/service charge → VAT_STANDARD (NHIL+GETFund+COVID+VAT cascade)
            # BUS_SHUTTLE lines: transport revenue → VAT_STANDARD, posted to 4020-SHUTTLE-REVENUE-GH
            # OTHER: honour the row's Tax Code column directly
            LINE_TYPE_TAX_CODE = {
                "HR_COST": "EXEMPT",
                "SERVICE_FEE": "VAT_STANDARD",
                "BUS_SHUTTLE": "VAT_STANDARD",
            }
            # Revenue GL account overrides by line type
            LINE_TYPE_REVENUE_ACCOUNT = {
                "BUS_SHUTTLE": "4020-SHUTTLE-REVENUE-GH",
            }

            # Group rows sharing an invoice_number into multi-line invoices;
            # rows without an invoice_number become individual invoices.
            grouped_invoices = []
            by_number = {}
            for r in validated_rows:
                f = r["fields"]
                inv_num = str(f.get("invoice_number") or "").strip()
                if inv_num:
                    if inv_num not in by_number:
                        by_number[inv_num] = []
                        grouped_invoices.append((inv_num, by_number[inv_num]))
                    by_number[inv_num].append(r)
                else:
                    grouped_invoices.append((None, [r]))

            for inv_num, group_rows in grouped_invoices:
                head = group_rows[0]["fields"]
                client_ref = str(head.get("client_code") or "").strip().lower()
                client = client_by_code.get(client_ref) or client_by_name.get(client_ref)
                issue_dt = head.get("issue_date")
                due_dt = head.get("due_date")
                if isinstance(issue_dt, str):
                    issue_dt = datetime.date.fromisoformat(issue_dt)
                if isinstance(due_dt, str):
                    due_dt = datetime.date.fromisoformat(due_dt)

                inv_type = str(head.get("invoice_type") or InvoiceType.STANDARD).strip().upper()
                currency = str(head.get("currency") or "GHS").strip().upper()
                ref_num = str(head.get("reference_number") or "").strip()
                notes = str(head.get("notes") or "").strip()
                header_custom = group_rows[0].get("extra_data") or {}

                lines_payload = []
                for gr in group_rows:
                    gf = gr["fields"]

                    # Resolve line_type (from INCOME_2025 column layout)
                    line_type = str(gf.get("line_type") or "OTHER").strip().upper()

                    # Tax code: LINE_TYPE takes priority, then explicit Tax Code column
                    if line_type in LINE_TYPE_TAX_CODE:
                        tax_code = LINE_TYPE_TAX_CODE[line_type]
                    else:
                        tax_code = str(gf.get("tax_code") or "VAT_STANDARD").strip().upper()
                        if tax_code not in ("VAT_STANDARD", "EXEMPT", "ZERO"):
                            tax_code = "VAT_STANDARD"

                    tax_rate = Decimal("0.1500") if tax_code == "VAT_STANDARD" else Decimal("0.0000")

                    # Build custom_fields: merge no_of_employees + any extra_data columns
                    # Store _line_type so the GL posting (invoice_approve) can split revenue accounts
                    line_cf = dict(gr.get("extra_data") or {})
                    line_cf["_line_type"] = line_type
                    no_of_ee = gf.get("no_of_employees")
                    if no_of_ee is not None and str(no_of_ee).strip() not in ("", "0", "None"):
                        line_cf["no_of_employees"] = int(Decimal(str(no_of_ee)))

                    # Revenue account override for special line types (e.g. Bus Shuttle)
                    revenue_account_code = LINE_TYPE_REVENUE_ACCOUNT.get(line_type)

                    line_entry = {
                        "description": str(gf.get("line_description") or "").strip(),
                        "quantity": Decimal(str(gf.get("quantity") or 1)),
                        "unit_of_measurement": str(gf.get("unit_of_measurement") or "Month").strip(),
                        "unit_price": Decimal(str(gf.get("unit_price") or 0)),
                        "discount_amount": Decimal(str(gf.get("discount_amount") or 0)),
                        "tax_code": tax_code,
                        "tax_rate": tax_rate,
                        "custom_fields": line_cf,
                    }
                    if revenue_account_code:
                        line_entry["revenue_account_code"] = revenue_account_code

                    lines_payload.append(line_entry)

                InvoicingService.invoice_create(
                    client_id=str(client.id),
                    issue_date=issue_dt,
                    due_date=due_dt,
                    invoice_type=inv_type,
                    currency=currency,
                    reference_number=ref_num,
                    invoice_number=inv_num or None,
                    lines=lines_payload,
                    custom_fields=header_custom,
                    notes=notes,
                    auto_calculate_tax=True,
                    user=user,
                )
                imported_count += 1
            CacheManager.invalidate_invoicing()

        # Mark job completed
        job.status = ImportJobStatus.COMPLETED
        job.successful_rows = imported_count
        job.save()

        # Audit Log
        AuditLog.objects.create(
            organization=organization,
            actor_user=user,
            action="BULK_IMPORT",
            module=entity_type.lower(),
            resource_type=entity_type,
            resource_id=str(job.id),
            changes={"imported_records_count": imported_count, "file_name": job.file_name}
        )

        return {
            "job_id": str(job.id),
            "status": "COMPLETED",
            "entity_type": entity_type,
            "imported_count": imported_count,
            "message": f"Successfully imported {imported_count} {entity_type} records."
        }
