from typing import Dict, Any, List

DEFAULT_INVOICE_CATEGORIES = [
    {
        "code": "WORKFORCE_OUTSOURCING",
        "name": "Workforce & Staffing Outsourcing",
        "description": "On-site and off-site outsourced workforce, labor hire, and operational personnel.",
        "is_system": True,
    },
    {
        "code": "PAYROLL_ADMINISTRATION",
        "name": "Payroll & Statutory Management",
        "description": "Payroll administration, SSNIT, Tier 2, and statutory compliance management services.",
        "is_system": True,
    },
    {
        "code": "RECRUITMENT_PLACEMENTS",
        "name": "Executive Search & Recruitment",
        "description": "Talent acquisition, candidate placement fees, and executive recruitment.",
        "is_system": True,
    },
    {
        "code": "MANAGEMENT_CONSULTING",
        "name": "Management Consulting & Advisory",
        "description": "HR audit, organizational design, labor law advisory, and management consulting.",
        "is_system": True,
    },
    {
        "code": "CAMP_CATERING_LOGISTICS",
        "name": "Camp Management & Logistics",
        "description": "Mine site camp catering, logistics, cleaning, and facilities maintenance.",
        "is_system": False,
    },
]

INVOICE_TEMPLATE_PRESETS: Dict[str, Dict[str, Any]] = {
    "STAFFING_WORKFORCE": {
        "preset_code": "STAFFING_WORKFORCE",
        "template_name": "Workforce & Staffing Outsourcing Template",
        "layout_style": "DETAILED_STAFFING",
        "primary_color": "#0f172a",
        "secondary_color": "#1e293b",
        "accent_color": "#0284c7",
        "invoice_title": "TAX INVOICE - REIMBURSABLE WORKFORCE",
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": True,
        "show_unit_of_measure": True,
        "default_notes": "All timesheets and shift rosters have been verified and endorsed by the site manager.",
        "default_terms": "Payment is strictly due within 30 days of invoice date. Overdue amounts attract 2% monthly interest.",
        "footer_text": "SBP Africa Group • HR Outsourcing • Accra • Nairobi • Lagos • Johannesburg",
        "header_custom_fields": [
            {
                "key": "po_number",
                "label": "Client Purchase Order / WO",
                "type": "string",
                "required": False,
                "placeholder": "e.g. PO-2026-MINING-091",
            },
            {
                "key": "site_location",
                "label": "Project / Mine Site Location",
                "type": "string",
                "required": False,
                "placeholder": "e.g. Obuasi Gold Mine / Tarkwa Site",
            },
            {
                "key": "cost_center",
                "label": "Client Cost Center / Dept",
                "type": "string",
                "required": False,
                "placeholder": "e.g. CC-704 Operational Services",
            },
            {
                "key": "contract_number",
                "label": "Contract Agreement Code",
                "type": "string",
                "required": False,
                "placeholder": "e.g. SBP-AGL-2025-01",
            },
        ],
        "line_custom_fields": [
            {
                "key": "staff_name",
                "label": "Staff Name / Personnel",
                "type": "string",
                "required": True,
                "placeholder": "e.g. Kwame Mensah",
            },
            {
                "key": "employee_id",
                "label": "Staff / Badge No.",
                "type": "string",
                "required": False,
                "placeholder": "e.g. SBP-EMP-0412",
            },
            {
                "key": "role_designation",
                "label": "Job Role / Trade",
                "type": "string",
                "required": False,
                "placeholder": "e.g. Heavy Equipment Operator",
            },
            {
                "key": "days_worked",
                "label": "Days / Hours Worked",
                "type": "number",
                "required": False,
                "placeholder": "26",
            },
        ],
    },
    "STANDARD_CORPORATE": {
        "preset_code": "STANDARD_CORPORATE",
        "template_name": "Standard Corporate Tax Invoice",
        "layout_style": "CORPORATE",
        "primary_color": "#1e3a8a",
        "secondary_color": "#172554",
        "accent_color": "#3b82f6",
        "invoice_title": "COMMERCIAL TAX INVOICE",
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": True,
        "show_unit_of_measure": True,
        "default_notes": "Thank you for your business. Please quote invoice number during wire transfer.",
        "default_terms": "Standard payment terms: net 30 days from invoice dispatch.",
        "footer_text": "SBP Africa Group • Registered in Ghana • Tax Identification Number: C0001234567",
        "header_custom_fields": [
            {
                "key": "po_number",
                "label": "Client Purchase Order",
                "type": "string",
                "required": False,
                "placeholder": "e.g. PO-88741",
            },
            {
                "key": "attention_to",
                "label": "Attention / Contact Person",
                "type": "string",
                "required": False,
                "placeholder": "e.g. Chief Financial Officer",
            },
        ],
        "line_custom_fields": [
            {
                "key": "service_code",
                "label": "Service Code",
                "type": "string",
                "required": False,
                "placeholder": "e.g. SVC-001",
            },
        ],
    },
    "RECRUITMENT_PLACEMENTS": {
        "preset_code": "RECRUITMENT_PLACEMENTS",
        "template_name": "Executive Search & Placement Invoice",
        "layout_style": "MODERN",
        "primary_color": "#065f46",
        "secondary_color": "#064e3b",
        "accent_color": "#059669",
        "invoice_title": "INVOICE - EXECUTIVE SEARCH & PLACEMENT",
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": True,
        "show_unit_of_measure": False,
        "default_notes": "Placement guarantee period: 90 days from candidate commencement date.",
        "default_terms": "Placement fees are due in full upon candidate signing or start date.",
        "footer_text": "SBP Africa Talent Search • Accra • Nairobi • Johannesburg",
        "header_custom_fields": [
            {
                "key": "po_number",
                "label": "Purchase Order / Authorization",
                "type": "string",
                "required": False,
                "placeholder": "e.g. PO-TALENT-2026",
            },
            {
                "key": "requisition_id",
                "label": "Requisition / Position Code",
                "type": "string",
                "required": False,
                "placeholder": "e.g. REQ-ENG-089",
            },
        ],
        "line_custom_fields": [
            {
                "key": "candidate_name",
                "label": "Placed Candidate Name",
                "type": "string",
                "required": True,
                "placeholder": "e.g. Ama Serwaa",
            },
            {
                "key": "job_title",
                "label": "Designation / Position",
                "type": "string",
                "required": True,
                "placeholder": "e.g. Head of Engineering",
            },
            {
                "key": "annual_gross_salary",
                "label": "Annual Gross Remuneration",
                "type": "number",
                "required": False,
                "placeholder": "e.g. 350000.00",
            },
            {
                "key": "fee_percentage",
                "label": "Placement Fee %",
                "type": "number",
                "required": False,
                "placeholder": "15.0",
            },
        ],
    },
    "CONSULTING_MANAGEMENT": {
        "preset_code": "CONSULTING_MANAGEMENT",
        "template_name": "Management Consulting & Advisory Invoice",
        "layout_style": "CLASSIC",
        "primary_color": "#4c1d95",
        "secondary_color": "#2e1065",
        "accent_color": "#7c3aed",
        "invoice_title": "PROFESSIONAL SERVICES INVOICE",
        "show_tax_breakdown": True,
        "show_bank_details": True,
        "show_due_date_badge": True,
        "show_discount": False,
        "show_unit_of_measure": True,
        "default_notes": "Deliverables and milestone sign-offs attached to this claim.",
        "default_terms": "Payment due within 14 calendar days from receipt of billing.",
        "footer_text": "SBP Africa Advisory & Consulting Practice",
        "header_custom_fields": [
            {
                "key": "engagement_letter_ref",
                "label": "Engagement Letter / SOW Ref",
                "type": "string",
                "required": False,
                "placeholder": "e.g. SOW-2026-CONSULT-04",
            },
            {
                "key": "milestone_phase",
                "label": "Milestone / Deliverable Phase",
                "type": "string",
                "required": False,
                "placeholder": "e.g. Phase 2: Implementation & Training",
            },
        ],
        "line_custom_fields": [
            {
                "key": "lead_consultant",
                "label": "Lead Consultant",
                "type": "string",
                "required": False,
                "placeholder": "e.g. Dr. Eric Osei",
            },
            {
                "key": "deliverable_reference",
                "label": "Deliverable Ref",
                "type": "string",
                "required": False,
                "placeholder": "e.g. DEL-03-AUDIT-REPORT",
            },
        ],
    },
}


def get_template_presets_list() -> List[Dict[str, Any]]:
    return list(INVOICE_TEMPLATE_PRESETS.values())


def get_preset_by_code(code: str) -> Dict[str, Any]:
    if code not in INVOICE_TEMPLATE_PRESETS:
        raise ValueError(f"Unknown preset code: {code}. Available presets: {list(INVOICE_TEMPLATE_PRESETS.keys())}")
    return INVOICE_TEMPLATE_PRESETS[code]
