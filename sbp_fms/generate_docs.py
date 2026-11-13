import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="{color}"/>
            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="1B45CC"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/>
            <w:insideV w:val="none"/>
            <w:left w:val="none"/>
            <w:right w:val="none"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)

def build_docx(output_path):
    doc = docx.Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x33, 0x41, 0x55) # Slate 700

    # Header / Title Block
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_sub = title_p.add_run("SBP AFRICA ACCOUNTING PLATFORM (SBP-FMS)\n")
    run_sub.font.size = Pt(11)
    run_sub.font.bold = True
    run_sub.font.color.rgb = RGBColor(0x2D, 0x5B, 0xE3)

    run_title = title_p.add_run("Comprehensive Frontend UI/UX Design System & Specification")
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

    meta_p = doc.add_paragraph()
    meta_p.paragraph_format.space_after = Pt(20)
    r_meta = meta_p.add_run("Document Version: 2.0 (Production Blueprint) | Target Platforms: Web SPA (Next.js / React) & Mobile Responsive")
    r_meta.font.size = Pt(9.5)
    r_meta.font.italic = True
    r_meta.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    def add_heading_1(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(18)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1B, 0x45, 0xCC)
        return h

    def add_heading_2(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.size = Pt(12.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
        return h

    def add_heading_3(text):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(3)
        h.paragraph_format.keep_with_next = True
        r = h.add_run(text)
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x2D, 0x5B, 0xE3)
        return h

    def add_callout(text, title="NOTE / ARCHITECTURE PRINCIPLE"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Inches(6.9)
        set_cell_background(cell, "F0F4FD")
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r_head = p.add_run(f"[{title}]\n")
        r_head.bold = True
        r_head.font.size = Pt(9.5)
        r_head.font.color.rgb = RGBColor(0x1B, 0x45, 0xCC)
        r_body = p.add_run(text)
        r_body.font.size = Pt(9.5)
        r_body.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(0)
        p_space.paragraph_format.space_after = Pt(6)

    def format_table(headers, data, col_widths=None):
        tbl = doc.add_table(rows=len(data) + 1, cols=len(headers))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(tbl)

        # Header Row
        hdr_row = tbl.rows[0]
        for idx, text in enumerate(headers):
            cell = hdr_row.cells[idx]
            set_cell_background(cell, "1B45CC")
            set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(text)
            run.font.bold = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        # Data Rows
        for r_idx, row_data in enumerate(data):
            row = tbl.rows[r_idx + 1]
            bg_color = "FFFFFF" if r_idx % 2 == 0 else "F8FAFC"
            for c_idx, val in enumerate(row_data):
                cell = row.cells[c_idx]
                set_cell_background(cell, bg_color)
                set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(str(val))
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

        if col_widths:
            for row in tbl.rows:
                for c_idx, w in enumerate(col_widths):
                    row.cells[c_idx].width = Inches(w)

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(0)
        p_after.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE OVERVIEW & DESIGN SYSTEM TOKENS
    # -------------------------------------------------------------
    add_heading_1("1. Executive Overview & Design System Tokens")
    p1 = doc.add_paragraph(
        "This specification establishes the standard frontend architecture, page layouts, component interactions, "
        "and data schemas for SBP Africa's cloud-native Financial Management System (SBP-FMS). Designed for enterprise multi-tenancy, "
        "the interface combines dense financial utility with modern B2B SaaS elegance (reminiscent of Stripe, Linear, and Modern Treasury). "
        "Every page and modal incorporates strict idempotency guards, role-based authorization gates, real-time caching feedback, "
        "and multi-currency financial validation."
    )

    add_heading_2("1.1 Core Design Tokens & Color Palette")
    headers_color = ["Token / Variable", "HEX Value", "Visual Purpose", "Usage Context"]
    data_color = [
        ["--color-primary-600", "#1B45CC", "Brand Primary Navy", "Primary buttons, active sidebar links, key headers, focus rings"],
        ["--color-primary-500", "#2D5BE3", "Vibrant Brand Blue", "Links, secondary highlights, tab indicators, active states"],
        ["--color-primary-50", "#F0F4FD", "Tint Background", "Badge backgrounds, callouts, active row highlights"],
        ["--color-success-600", "#08874C", "Financial Emerald", "Balanced reconciliations, paid invoices, approved vouchers, profit"],
        ["--color-success-50", "#EDFBF4", "Success Soft Tint", "Positive transaction chips, auto-match badges"],
        ["--color-warning-500", "#F39C12", "Operational Amber", "Pending approvals, draft vouchers, expiring trial banners, warnings"],
        ["--color-danger-500", "#E74C3C", "Audit Crimson", "Imbalanced journals, overdue bills, failed syncs, delete/void actions"],
        ["--color-surface-bg", "#F8FAFC", "Canvas Light Slate", "Global app background, container canvas"],
        ["--color-surface-card", "#FFFFFF", "White Surface", "Cards, modals, data tables, side drawers"],
        ["--color-border", "#E2E8F0", "Neutral Hairline", "Table borders, input outlines, panel dividers"],
        ["--color-text-primary", "#0F172A", "Deep Slate 900", "Headings, numbers, primary table values, modal titles"],
        ["--color-text-secondary", "#475569", "Medium Slate 600", "Form labels, secondary column data, table headers"],
        ["--color-text-muted", "#94A3B8", "Muted Slate 400", "Timestamps, placeholder text, disabled actions, helper notes"],
    ]
    format_table(headers_color, data_color, [1.4, 0.9, 1.6, 3.0])

    add_heading_2("1.2 Typography & Numerical Formatting Standards")
    p_typo = doc.add_paragraph(
        "Typography uses Inter for UI chrome, headings, and descriptive labels. All financial numerical values "
        "(general ledger balances, debits, credits, exchange rates, voucher amounts) must use tabular numbers "
        "('font-variant-numeric: tabular-nums' or JetBrains Mono) aligned strictly to the right. "
        "Monetary values are always presented with two decimal places (e.g. GHS 12,500.00), while foreign exchange rates "
        "render with up to 6 decimal places (e.g. 15.650000)."
    )

    # -------------------------------------------------------------
    # SECTION 2: GLOBAL APP SHELL & MULTI-TENANT NAVIGATION
    # -------------------------------------------------------------
    add_heading_1("2. Global App Shell & Navigation Hierarchy")
    p_shell = doc.add_paragraph(
        "The application uses an enterprise three-tier shell: a collapsible vertical navigation sidebar on the left, "
        "a persistent high-utility header bar at the top, and a dynamic main content viewport with fluid responsive max-width."
    )

    add_callout(
        "Every authenticated request automatically carries the active tenant context. The top-left organization badge acts as a "
        "tenant switcher allowing outsourced CFOs and group controllers to toggle between subsidiary entities instantly without re-authenticating.",
        "MULTI-TENANT SWITCHER ARCHITECTURE"
    )

    headers_shell = ["Navigation Section", "Sub-Routes & Views", "User Roles Required", "Primary Functions"]
    data_shell = [
        ["1. Dashboard", "/dashboard", "All Tenant Roles", "Consolidated cash positions, revenue/expense trend charts, urgent approval queue"],
        ["2. General Ledger", "/ledger/coa, /ledger/journals, /ledger/reports", "Accountant, Finance Mgr, Admin", "Chart of accounts tree, multi-line journal postings, real-time trial balance"],
        ["3. Treasury & Banking", "/treasury/accounts, /treasury/cashbook, /treasury/reconcile", "Cashier, Accountant, Admin", "Bank account cards, live Mono Open Banking feeds, 2-way bank reconciliation"],
        ["4. Sales & Receivables", "/receivables/clients, /receivables/invoices, /receivables/receipts", "Sales, Billing Clerk, Accountant", "Customer invoicing, tax calculation, receipt allocations, aging debtor reports"],
        ["5. Payables & Expenses", "/payables/suppliers, /payables/bills, /payables/vouchers, /payables/claims", "Purchasing, Employee, Finance Mgr", "Supplier bills, 3-way matching, payment vouchers, petty cash claims"],
        ["6. Fixed Assets", "/assets/register, /assets/categories, /assets/depreciation", "Accountant, Asset Controller", "Asset register, straight-line & reducing balance schedules, disposals"],
        ["7. Consolidation & FX", "/consolidation/rates, /consolidation/revaluation, /consolidation/trial-balance", "Finance Manager, Superadmin", "Live Groq AI exchange rates, multi-entity rollups, unrealized FX revaluations"],
        ["8. Payroll & Escrow", "/payroll/batches, /payroll/salaries, /payroll/pension", "HR, Payroll Mgr, Auditor", "Salary payroll batches, PAYE tax & SSNIT pension liabilities, disbursal registers"],
        ["9. Budgeting & Planning", "/budgeting/budgets, /budgeting/variance", "Department Head, CFO", "Cost center budgets, actual-vs-budget variance monitoring, encumbrances"],
        ["10. Contracts & Compliance", "/contracts/register, /contracts/expiring", "Legal, Procurement, Admin", "Vendor & customer contract repository, milestones, automated expiration alerts"],
        ["11. Taxation & Withholding", "/taxation/rules, /taxation/returns, /taxation/wht-certificates", "Tax Accountant, Finance Mgr", "VAT/NHIL/GETFund rules, Withholding tax (WHT) deductions & filing schedules"],
        ["12. Platform Admin & Billing", "/settings/organization, /settings/users, /settings/billing", "Tenant Owner, Platform Superadmin", "Dynamic subscription plan upgrades via Paystack, user roles & fine permissions"],
    ]
    format_table(headers_shell, data_shell, [1.3, 1.8, 1.4, 2.4])

    # -------------------------------------------------------------
    # SECTION 3: DETAILED SCREEN SPECIFICATIONS & DATA SCHEMAS
    # -------------------------------------------------------------
    add_heading_1("3. Detailed Screen Specifications, Fields & Workflows")

    # 3.1 Organization & Billing
    add_heading_2("3.1 Organization Onboarding, Billing & Paystack Checkout")
    doc.add_paragraph(
        "Allows self-service B2B customer onboarding, dynamic plan configuration by platform Superadmins, "
        "and instant subscription checkout via Paystack with strict idempotency protection against double-billing."
    )
    headers_reg = ["Screen / Modal", "Field Name", "Field Type", "Validation / Constraints", "Behavior & API Binding"]
    data_reg = [
        ["Registration Form (/register)", "organization_name", "Text Input", "Required, 3-200 chars", "Legal company name; auto-generates tenant slug"],
        ["Registration Form (/register)", "subdomain", "Slug Text", "Optional, alphanumeric & hyphens", "Dedicated tenant workspace domain prefix (e.g. acme)"],
        ["Registration Form (/register)", "email", "Email Input", "Required, valid corporate email", "Account login; checked for platform uniqueness"],
        ["Registration Form (/register)", "password", "Password", "Required, min 8 chars, strength meter", "Encrypted via Argon2/PBKDF2"],
        ["Registration Form (/register)", "first_name / last_name", "Text Input", "Required, max 150 chars", "Full name of the company administrator"],
        ["Registration Form (/register)", "country_code", "Select Dropdown", "Required, ISO 2-letter (GH, NG, KE, ZA)", "Initializes national tax rules and local statutory presets"],
        ["Registration Form (/register)", "base_currency", "Select Dropdown", "Required, 3-letter (GHS, USD, NGN, KES)", "Platform-wide functional currency for general ledger"],
        ["Registration Form (/register)", "plan", "Hidden / Radio", "Default 'TRIAL'", "Selected dynamic subscription plan code"],
        ["Pricing Card (/settings/billing)", "plan_id", "UUID Selection", "Required upon checkout click", "Linked SubscriptionPlan entity"],
        ["Pricing Card (/settings/billing)", "callback_url", "URL String", "Required for checkout redirect", "Frontend route returned upon Paystack gateway completion"],
        ["Pricing Card (/settings/billing)", "Idempotency-Key", "HTTP Header", "UUID v4 generated by browser", "Attached to POST /api/v1/organizations/billing/initialize/"],
    ]
    format_table(headers_reg, data_reg, [1.3, 1.2, 1.1, 1.5, 1.8])

    # 3.2 Roles & Delegation
    add_heading_2("3.2 User Management, Functional Delegation & Permission Matrix")
    doc.add_paragraph(
        "Superadmins and Tenant Administrators (Owners, Finance Managers) can assign standard tenant roles "
        "and delegate specific functional capabilities across organizational teams."
    )
    headers_perm = ["Target Entity", "Role / Permission Code", "Delegation Authority", "Operational Scope"]
    data_perm = [
        ["Tenant Role", "OWNER", "Platform Superadmin / Existing Owner", "Full control: billing, organization settings, financial destruction, user deletion"],
        ["Tenant Role", "ADMIN", "Owner, Admin", "User invitations, subsidiary profile management, company branding, team permissions"],
        ["Tenant Role", "ACCOUNTANT", "Owner, Admin, Finance Manager", "Journal creation, chart of accounts modification, trial balance inspection"],
        ["Tenant Role", "CLERK", "Owner, Admin, Accountant", "Data entry: creating invoices, entering bills, drafting expense claims"],
        ["Tenant Role", "AUDITOR", "Owner, Admin", "Strictly read-only access to general ledgers, trial balance, tax schedules, logs"],
        ["Permission Code", "users:write", "CanManageUsers Permission", "Grants ability to invite users, assign tenant roles, deactivate accounts"],
        ["Permission Code", "roles:write", "CanManageRoles Permission", "Grants ability to grant/revoke fine-grained domain permission codes"],
        ["Permission Code", "ledger:post", "Finance Manager, Chief Accountant", "Authorizes direct posting of balancing journals to general ledger"],
        ["Permission Code", "payables:voucher_approve", "Segregation of Duties Check", "Prevents voucher creators from self-approving payment vouchers"],
        ["Permission Code", "treasury:reconcile", "Treasury Accountant", "Access to match bank statement lines and finalize reconciliation runs"],
    ]
    format_table(headers_perm, data_perm, [1.1, 1.5, 1.5, 2.8])

    # 3.3 Treasury & Open Banking
    add_heading_2("3.3 Treasury, Bank Accounts & Mono Open Banking Feed")
    doc.add_paragraph(
        "Multi-tenant bank account management connecting customer bank accounts (Ecobank, Stanbic, Zenith, Access, Standard Chartered) "
        "directly into SBP-FMS via Mono's Open Banking API, supplemented by 2-way automated bank reconciliation."
    )
    headers_bank = ["View / Component", "Field Name", "Data Type", "Constraint / Source", "UI/UX Behavior & Interaction"]
    data_bank = [
        ["Bank Account Card", "bank_name", "Text Display", "e.g. 'Ecobank Ghana'", "Displays bank branding logo and country flag"],
        ["Bank Account Card", "account_number", "Masked String", "e.g. '****5678'", "Masked for operational privacy, full number in edit modal"],
        ["Bank Account Card", "gl_account", "Account Dropdown", "Asset Cash Account (e.g. 1020)", "Links bank transactions to balancing general ledger account"],
        ["Bank Account Card", "currency", "Currency Badge", "e.g. GHS, USD, EUR", "Defines statement currency and payment settlement currency"],
        ["Bank Account Card", "status", "Status Badge", "CONNECTED / DISCONNECTED / ERROR", "Color-coded dot showing live aggregator heartbeat"],
        ["Connect Modal", "mono_public_key", "SDK Param", "Settings provided by backend", "Passed to 'MonoConnect.setup({ key })' on button click"],
        ["Connect Modal", "code", "Auth Code", "Returned by Mono widget", "Sent in POST /api/v1/treasury/admin/accounts/{id}/feed-exchange/"],
        ["Reconciliation Split", "statement_lines", "Left Data Grid", "BankStatementLine records", "Date, reference, description, debit (inflow), credit (outflow)"],
        ["Reconciliation Split", "journal_lines", "Right Data Grid", "JournalLine records", "Date, JE number, description, GL cashbook debit/credit"],
        ["Reconciliation Summary", "statement_ending_balance", "Money Display", "Real-time bank statement balance", "Extracted from bank feed or manual statement import"],
        ["Reconciliation Summary", "reconciled_difference", "Money Display", "Computed delta", "Highlights Emerald Green when 0.00; Crimson Red if variance"],
    ]
    format_table(headers_bank, data_bank, [1.3, 1.3, 1.1, 1.4, 1.8])

    # 3.4 Live Groq AI Exchange Rates
    add_heading_2("3.4 Multi-Currency Engine & Live Groq AI Exchange Rates")
    doc.add_paragraph(
        "Eliminates stale manual currency entry by querying Groq AI (LPU inference engine) referencing XE.com "
        "and global interbank feeds in real time, backed by a 10-minute short-lived cache with instant force-refresh."
    )
    headers_fx = ["Component", "Field / Parameter", "Type", "Source / Logic", "Operational Effect"]
    data_fx = [
        ["Top Currency Pill", "active_currency", "Dropdown Selector", "e.g. USD, EUR, GHS", "Switches global display and conversion perspective"],
        ["Live Spot Calculator", "from_currency", "Currency Select", "e.g. USD", "Base currency to convert from"],
        ["Live Spot Calculator", "to_currency", "Currency Select", "e.g. GHS", "Target reporting currency to convert into"],
        ["Live Spot Calculator", "rate", "Decimal (6 places)", "Groq AI / XE.com quote", "e.g. 15.650000; applies to trial balance & revaluations"],
        ["Live Spot Calculator", "is_cached", "Boolean Badge", "CacheManager check", "Displays '⚡ Cached (10m TTL)' or '🟢 Live Groq Query'"],
        ["Live Spot Calculator", "force_refresh", "Boolean Toggle", "Query Param (?force_refresh=true)", "Bypasses Redis/memory cache to pull instant fresh market quote"],
        ["Audit Historical Table", "rate_type", "Enum Badge", "SPOT, CLOSING, AVERAGE", "Permanent audit log stored in ExchangeRate model table"],
    ]
    format_table(headers_fx, data_fx, [1.3, 1.2, 1.1, 1.4, 1.9])

    # 3.5 Sales & Receivables
    add_heading_2("3.5 Sales, Invoicing & Receivables (AR)")
    doc.add_paragraph(
        "Full client customer lifecycle: client registries, automated sales tax computation (VAT, NHIL, GETFund), "
        "invoice issuance, partial/full payment receipt allocations, and aged debtor analysis."
    )
    headers_ar = ["Screen / Form", "Field Name", "Type & Rules", "Required?", "Accounting & Tax Workflow"]
    data_ar = [
        ["Client Registry", "name / legal_name", "Text Input", "Required", "Customer trading identity and legal entity name"],
        ["Client Registry", "tax_identification_number", "Text (TIN)", "Optional", "Customer national tax number printed on tax invoices"],
        ["Client Registry", "credit_limit / payment_terms", "Money / Integer (Days)", "Optional", "Enforces credit limits and net payment due dates (e.g. Net 30)"],
        ["Invoice Creator", "invoice_number", "Alphanumeric", "Auto-generated", "Unique fiscal invoice serial (e.g. INV-2026-0089)"],
        ["Invoice Creator", "issue_date / due_date", "Date Pickers", "Required", "Determines revenue recognition date and aging bucket"],
        ["Invoice Lines Table", "description", "Text Input", "Required", "Line item product or professional service narrative"],
        ["Invoice Lines Table", "quantity * unit_price", "Decimal * Money", "Required", "Computes subtotal line amount automatically"],
        ["Invoice Lines Table", "tax_rule_id", "Select Dropdown", "Required", "Applies standard VAT/NHIL/GETFund tax rules to line item"],
        ["Invoice Lines Table", "revenue_account_id", "Select (GL Income)", "Required", "Directs credit entry to general ledger Revenue (4000)"],
        ["Payment Receipt Modal", "receipt_amount", "Money Input", "Required", "Total cash/cheque collected from customer"],
        ["Payment Receipt Modal", "allocations", "Table Checkboxes", "Required", "Allocates payment against one or more outstanding invoices"],
    ]
    format_table(headers_ar, data_ar, [1.3, 1.3, 1.1, 0.8, 2.4])

    # 3.6 Payables, Expenses & Vouchers
    add_heading_2("3.6 Payables (AP), 3-Way Matching, Expense Claims & Payment Vouchers")
    doc.add_paragraph(
        "Strict corporate governance covering vendor onboarding, Purchase Order -> GRN -> Supplier Bill 3-way matching, "
        "employee expense claims, and multi-tier payment voucher approval workflows."
    )
    headers_ap = ["Workflow Step", "Input / Display Field", "Type & Source", "Validation Rule", "Internal Control & Audit Rule"]
    data_ap = [
        ["Supplier Onboarding", "company_name / tin", "Text Input", "Required", "Vendor identification and withholding tax status"],
        ["Supplier Onboarding", "bank_account_details", "JSON Object", "Required", "Routing for automated wire/mobile money remittances"],
        ["3-Way Match Audit", "match_status", "Badge (UNMATCHED / PARTIAL / MATCHED)", "System Computed", "Compares PO quantities, GRN warehouse receipts, and Bill prices"],
        ["Expense Claim Drawer", "claim_type", "Enum (TRAVEL, MEALS, FUEL, OFFICE, MILEAGE)", "Required", "Determines allowable corporate tax deductible category"],
        ["Expense Claim Drawer", "receipt_attachment", "File Upload (PDF/JPG)", "Required for claims > $25", "Stores digital expense proof in media repository"],
        ["Payment Voucher", "voucher_number", "System Serial", "Auto-generated", "Unique financial disbursement tag (e.g. PV-2026-0145)"],
        ["Payment Voucher", "payment_method", "Select (BANK_TRANSFER, MOBILE_MONEY, CHEQUE)", "Required", "Directs disbursement channel and banking batch routing"],
        ["Payment Voucher", "approval_hierarchy", "Step Indicator", "Multi-stage", "Requires Finance Manager approval before treasury release"],
        ["Payment Voucher", "Segregation of Duties", "Backend Rule", "Enforced automatically", "Voucher preparer is blocked from clicking 'Approve Voucher'"],
    ]
    format_table(headers_ap, data_ap, [1.3, 1.3, 1.2, 1.2, 1.9])

    # 3.7 Fixed Assets
    add_heading_2("3.7 Fixed Assets Register & Automated Depreciation")
    doc.add_paragraph(
        "Tracks tangible capital assets, useful economic life, salvage values, automated straight-line and "
        "reducing balance depreciation schedules, and derecognition gain/loss posting."
    )
    headers_asset = ["Feature / View", "Field Name", "Type", "Required?", "Financial Accounting Workflow"]
    data_asset = [
        ["Asset Creation Drawer", "asset_number", "Unique Code", "Required", "Physical barcode or asset tag number (e.g. FA-EQP-0012)"],
        ["Asset Creation Drawer", "name", "Text Input", "Required", "Description of equipment or vehicle (e.g. Dell PowerEdge Server)"],
        ["Asset Creation Drawer", "category_id", "Dropdown", "Required", "Selects Asset Category (IT, Motor Vehicle, Plant, Buildings)"],
        ["Asset Creation Drawer", "purchase_date", "Date Picker", "Required", "Capitalization date for depreciation commencement"],
        ["Asset Creation Drawer", "purchase_cost", "Money Input", "Required", "Gross historical acquisition cost debited to GL Asset"],
        ["Asset Creation Drawer", "salvage_value", "Money Input", "Optional", "Residual value excluded from depreciable base"],
        ["Asset Creation Drawer", "useful_life_years", "Integer", "Required", "Expected operating lifespan (e.g. 3, 5, 10, 20 years)"],
        ["Asset Creation Drawer", "depreciation_method", "Select Enum", "Required", "STRAIGHT_LINE or REDUCING_BALANCE"],
        ["Depreciation Run", "period_ending", "Date Picker", "Required", "Generates batch depreciation journal: Dr Depr Exp / Cr Acc Depr"],
        ["Asset Disposal Modal", "disposal_proceeds", "Money Input", "Required", "Cash proceeds received from asset sale to calculate gain/loss"],
    ]
    format_table(headers_asset, data_asset, [1.3, 1.2, 1.0, 0.8, 2.6])

    # 3.8 Budgeting, Payroll, Contracts & Tax
    add_heading_2("3.8 Budgeting, Payroll Escrow, Contracts & Tax Filing")
    doc.add_paragraph(
        "Supplemental enterprise modules covering department cost center budgets, payroll tax withholdings, "
        "vendor contract expiration tracking, and national tax return schedules."
    )
    headers_sup = ["Module", "Screen Name", "Key Data Fields", "Automated System Action"]
    data_sup = [
        ["Budgeting", "Cost Center Budget (/budgeting/budgets)", "Fiscal year, department, GL expense account, budgeted monthly caps", "Computes real-time variance and displays warnings when invoices exceed budget"],
        ["Payroll Escrow", "Salary Batch (/payroll/batches)", "Pay period, gross salary total, PAYE tax liability, employee pension total", "Creates balancing journal debiting Wage Expense and crediting Tax/Pension Liabilities"],
        ["Contracts", "Contract Registry (/contracts/register)", "Title, vendor/client, contract value, start/end dates, milestone reminders", "Celery periodic task monitors upcoming terminations and sends 30-day email alerts"],
        ["Taxation", "Tax Returns (/taxation/returns)", "Filing period, output VAT collected, input VAT claimable, net tax payable", "Aggregates AR and AP transactions into national standard VAT return filing draft"],
    ]
    format_table(headers_sup, data_sup, [1.1, 1.5, 2.0, 2.3])

    # -------------------------------------------------------------
    # SECTION 4: USER EXPERIENCE, FEEDBACK & ERROR RESILIENCE
    # -------------------------------------------------------------
    add_heading_1("4. User Experience, Feedback States & Error Resilience")
    doc.add_paragraph(
        "Enterprise financial applications require bulletproof feedback loops to eliminate user uncertainty during long-running "
        "operations or momentary network dropouts."
    )

    add_heading_2("4.1 Idempotency Key Generation & Double-Click Guards")
    p_idemp = doc.add_paragraph(
        "For all mutation endpoints (initiating payments, creating journal entries, approving vouchers, and syncing feeds), "
        "the frontend client generates a unique UUID v4 before submitting the request. This key is transmitted in the "
        "'Idempotency-Key' HTTP header. The submit button immediately enters a disabled loading state. If the user clicks multiple times "
        "or if the network drops, the backend replays the exact completed response without re-executing charges or duplicating ledger lines."
    )

    add_heading_2("4.2 Global HTTP Error Interception Matrix")
    headers_err = ["HTTP Status Code", "Backend Error Code", "Frontend User Experience & Remediation"]
    data_err = [
        ["400 Bad Request", "VALIDATION_ERROR", "Inline field validation errors highlight in red with exact backend helper messages"],
        ["401 Unauthorized", "TOKEN_EXPIRED", "Transparently calls /api/v1/users/auth/token/refresh/ and retries original request; redirects to /login on failure"],
        ["403 Forbidden", "PERMISSION_DENIED", "Toast notification explaining required permission code (e.g. 'Permission treasury:manage required')"],
        ["409 Conflict", "IDEMPOTENT_OPERATION_IN_PROGRESS", "Banner notification: 'Operation currently processing. Auto-retrying in 2 seconds...'"],
        ["500 Internal Error", "SERVER_ERROR", "Actionable dialog with reference code and instant 'Report to Support' link without app crash"],
    ]
    format_table(headers_err, data_err, [1.2, 1.8, 3.9])

    # Save document
    doc.save(output_path)
    print(f"Document successfully created at {output_path}")

if __name__ == "__main__":
    out = "/home/khelly/Documents/SBP AFRICA/Accounting/sbp_fms_django_backend/sbp_fms/frontend_design_specification.docx"
    build_docx(out)
