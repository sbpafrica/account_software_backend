"""
Pre-Built Industry Invoice Presets for SBP Africa Group.
Provides 1-click professional templates tailored for:
1. Outsourced Workforce & Timesheet Staffing
2. Standard Corporate & Business Services
3. Executive Recruitment & Talent Placement
4. HR Advisory, Compliance & Management Consulting
"""

INVOICE_PRESETS = [
    {
        "preset_code": "STAFFING_WORKFORCE",
        "template_name": "Outsourced Workforce & Timesheet Billing",
        "description": "Tailored for mining, logistics, manufacturing, and staffing clients requiring employee itemization, roles, days worked, and site locations.",
        "layout_style": "DETAILED_STAFFING",
        "primary_color": "#102a43",
        "secondary_color": "#243b53",
        "accent_color": "#0ea5e9",
        "font_family": "Inter, sans-serif",
        "invoice_title": "TAX INVOICE - OUTSOURCED WORKFORCE & PAYROLL SERVICES",
        "show_logo": True,
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": False,
        "show_unit_of_measure": True,
        "header_custom_fields": [
            {
                "key": "po_number",
                "label": "Purchase Order (PO) Number",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. PO-GH-2026-001"
            },
            {
                "key": "service_period",
                "label": "Billing / Payroll Period",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. October 2026"
            },
            {
                "key": "site_location",
                "label": "Work Site / Concession Location",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Tarkwa Gold Concession"
            },
            {
                "key": "client_cost_center",
                "label": "Client Cost Center / Dept",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. CC-MINING-OPS"
            },
            {
                "key": "timesheet_approver",
                "label": "Approved By (Client Authorizer)",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Site General Manager"
            }
        ],
        "line_custom_fields": [
            {
                "key": "staff_name",
                "label": "Staff Name / Personnel ID",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Kofi Mensah (ID: SBP-091)"
            },
            {
                "key": "role_designation",
                "label": "Role / Trade Designation",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Heavy Duty Machine Operator"
            },
            {
                "key": "days_worked",
                "label": "Days / Hours Worked",
                "type": "number",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. 26"
            },
            {
                "key": "department",
                "label": "Department / Shift Crew",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Processing Plant Crew A"
            }
        ],
        "default_notes": "All outsourced personnel are fully compliant with statutory SSNIT, PAYE, and Workmen's Compensation under Ghana Labor Act 651.",
        "default_terms": "Payment due within agreed payment terms. Remittance details provided below. Please quote invoice number on transfer.",
        "footer_text": "SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg"
    },
    {
        "preset_code": "STANDARD_CORPORATE",
        "template_name": "Standard Corporate & Business Services",
        "description": "Standard corporate billing template with clean PO reference, billing period, and comprehensive tax breakdown.",
        "layout_style": "CORPORATE",
        "primary_color": "#0f172a",
        "secondary_color": "#1e293b",
        "accent_color": "#3b82f6",
        "font_family": "Inter, sans-serif",
        "invoice_title": "TAX INVOICE",
        "show_logo": True,
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": True,
        "show_unit_of_measure": True,
        "header_custom_fields": [
            {
                "key": "po_number",
                "label": "Purchase Order (PO) Number",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. PO-2026-0042"
            },
            {
                "key": "service_period",
                "label": "Service Period",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. October 2026"
            },
            {
                "key": "contract_reference",
                "label": "Contract / Agreement Ref",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. MSA-SBP-2025-V2"
            },
            {
                "key": "attention_to",
                "label": "Attention (Finance / Accounts)",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Finance Director"
            }
        ],
        "line_custom_fields": [
            {
                "key": "service_code",
                "label": "Service Code",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. HR-SRV-01"
            }
        ],
        "default_notes": "Thank you for partnering with SBP Africa Group.",
        "default_terms": "Payment due within 30 days. Accounts subject to late statutory interest on overdue balances.",
        "footer_text": "SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg"
    },
    {
        "preset_code": "RECRUITMENT_PLACEMENTS",
        "template_name": "Executive Recruitment & Talent Placement",
        "description": "Tailored for headhunting and permanent placement fees based on candidate packages and placement fee percentages.",
        "layout_style": "MODERN",
        "primary_color": "#1e1b4b",
        "secondary_color": "#312e81",
        "accent_color": "#6366f1",
        "font_family": "Inter, sans-serif",
        "invoice_title": "TAX INVOICE - RECRUITMENT & TALENT PLACEMENT",
        "show_logo": True,
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": False,
        "show_unit_of_measure": False,
        "header_custom_fields": [
            {
                "key": "requisition_no",
                "label": "Job Requisition No.",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. REQ-ENG-2026-09"
            },
            {
                "key": "hiring_department",
                "label": "Hiring Department",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Engineering & Technology"
            },
            {
                "key": "placement_date",
                "label": "Candidate Start Date",
                "type": "date",
                "required": False,
                "default_value": "",
                "placeholder": "YYYY-MM-DD"
            }
        ],
        "line_custom_fields": [
            {
                "key": "candidate_name",
                "label": "Candidate Placed",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. John K. Mensah"
            },
            {
                "key": "job_title",
                "label": "Placed Position / Title",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. Chief Operating Officer"
            },
            {
                "key": "annual_gross_salary",
                "label": "Annual Base Package (GHS)",
                "type": "number",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. 450000.00"
            },
            {
                "key": "placement_fee_percentage",
                "label": "Agreed Fee %",
                "type": "number",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. 15.0"
            }
        ],
        "default_notes": "Placement backed by SBP Africa 90-day candidate replacement guarantee as per talent acquisition service contract.",
        "default_terms": "Invoice payable immediately upon candidate acceptance and start date.",
        "footer_text": "SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg"
    },
    {
        "preset_code": "CONSULTING_MANAGEMENT",
        "template_name": "HR Advisory & Management Consulting",
        "description": "Tailored for professional advisory, labor law compliance audits, organizational development, and milestone billing.",
        "layout_style": "CLASSIC",
        "primary_color": "#14532d",
        "secondary_color": "#166534",
        "accent_color": "#10b981",
        "font_family": "Merriweather, serif",
        "invoice_title": "PROFESSIONAL SERVICES INVOICE",
        "show_logo": True,
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": True,
        "show_unit_of_measure": False,
        "header_custom_fields": [
            {
                "key": "engagement_code",
                "label": "Engagement / Project Code",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. AUDIT-GH-2026"
            },
            {
                "key": "deliverable_milestone",
                "label": "Milestone / Deliverable Phase",
                "type": "text",
                "required": True,
                "default_value": "",
                "placeholder": "e.g. Milestone 2: Labor Law Audit Report"
            },
            {
                "key": "service_period",
                "label": "Consulting Period",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. 1st Oct - 31st Oct 2026"
            }
        ],
        "line_custom_fields": [
            {
                "key": "lead_consultant",
                "label": "Lead Consultant / Expert",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. Senior HR Legal Partner"
            },
            {
                "key": "deliverable_ref",
                "label": "Deliverable Ref Document",
                "type": "text",
                "required": False,
                "default_value": "",
                "placeholder": "e.g. SBP-DEL-04"
            }
        ],
        "default_notes": "Services rendered in accordance with SBP Africa Professional Consulting Agreement.",
        "default_terms": "Payment due within 15 days of invoice date.",
        "footer_text": "SBP Africa Group • Accra • Nairobi • Lagos • Johannesburg"
    }
]


def get_preset_by_code(code: str) -> dict | None:
    code_upper = code.strip().upper() if code else ""
    for preset in INVOICE_PRESETS:
        if preset["preset_code"] == code_upper:
            return preset
    return None
