# SBP-FMS — Complete Frontend Integration Master Guide

> **Backend Base URL**: `https://account.sbpafrica.group` (or `http://localhost:8000`)  
> **Interactive OpenAPI / Swagger Docs**: `/api/docs/` | **ReDoc**: `/api/redoc/` | **JSON Schema**: `/api/schema.json`  
> **Detailed Sub-Guides**:
> * [Invoicing Module Integration Guide](./FRONTEND_INVOICING_INTEGRATION_GUIDE.md)
> * [Invoicing Excel (Custom Headers, Upload & Export) Guide](./FRONTEND_INVOICING_EXCEL_GUIDE.md)

---

## 1. Global Integration Requirements (Must Implement First)

To make the entire system functional, the frontend HTTP client (Axios / Fetch wrapper) **must** implement these global behaviors:

### 1.1. Required Request Headers
| Header | When Required | Value |
| :--- | :--- | :--- |
| `Authorization` | All authenticated requests | `Bearer <access_token>` |
| `X-Organization-ID` | All tenant-scoped requests | Active workspace `<organization.id>` (UUID) or `<slug>` |
| `Idempotency-Key` | Mutating `POST` / `PUT` requests (payments, journal posts, approvals) | Unique UUID v4 per action |
| `Content-Type` | JSON requests / File uploads | `application/json` (or `multipart/form-data` for Excel/file uploads) |

### 1.2. Standard API Response Envelope
All endpoints return a consistent JSON envelope:
```json
{
  "status": "success",
  "message": "...",
  "data": { ... }
}
```
Paginated endpoints return `{ count, next, previous, results }` inside `data` (or top-level pagination wrapper depending on view).

### 1.3. Global Error Interceptors
* **`401 Unauthorized`**: Access token expired → call `POST /api/v1/users/public/token/refresh/` with `{ "refresh": "<refresh_token>" }`. If refresh fails, clear auth state and redirect to `/login`.
* **`402 Payment Required` (`code: "SUBSCRIPTION_EXPIRED"`)**: The tenant's 30-day trial or subscription expired. Redirect/open modal to **Subscriptions & Billing** (`/billing`) to subscribe via Paystack. *(Note: `/api/v1/organizations/plans/`, `/api/v1/organizations/billing/*`, `/api/v1/organizations/me/`, and `/api/v1/users/*` remain accessible during `402` lock.)*
* **`403 Forbidden`**: Hide/disable actions the user's `permissions` array does not include.

### 1.4. RBAC & Sidebar Visibility Rules
On login and app boot (`GET /api/v1/users/public/me/`), inspect `user.is_superuser`, `user.role`, and `permissions`:
* **Superadmin-only pages** (hide for `ORGANIZATION_OWNER` and tenant staff):
  * **Organizations Directory** (`/organizations`) → show ONLY if `is_superuser === true` or `permissions.includes('organizations:all')` or `permissions.includes('organizations:read')`.
  * **Roles & Permissions** (`/roles`) → show ONLY if `is_superuser === true` or `permissions.includes('roles:read')`.
  * **Audit Trail** (`/audit`) → show ONLY if `is_superuser === true` or `permissions.includes('audit:read')`.
* **Tenant Admin pages** (visible to `ORGANIZATION_OWNER`):
  * **Organization Settings** (`organization:settings`), **Member Invitations** (`members:read`), **Subscriptions & Billing**, **User Directory** (`users:read`), **Document Vault** (`documents:read`).
* **Wildcard check**: If `permissions.includes('*')`, grant access to all features.

---

## 2. Complete Endpoint Directory by Module

### Module 1: Authentication, Password Management & Users (`/api/v1/users/`)
| Feature | Method | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| Login | `POST` | `/api/v1/users/public/login/` | `{ email, password }` → returns `access`, `refresh`, `user`, `permissions` |
| Refresh Token | `POST` | `/api/v1/users/public/token/refresh/` | `{ refresh }` |
| Verify Token | `POST` | `/api/v1/users/public/token/verify/` | `{ token }` |
| Current User Profile | `GET` | `/api/v1/users/public/me/` | Returns `user` + `permissions` |
| Change Password | `POST` | `/api/v1/users/public/password/change/` | `{ old_password, new_password }` |
| Forgot Password | `POST` | `/api/v1/users/public/password/forgot/` | `{ email }` (sends reset token email) |
| Confirm Password Reset | `POST` | `/api/v1/users/public/password/reset/` | `{ uid, token, new_password }` |
| User Directory (List) | `GET` | `/api/v1/users/admin/users/` | List staff in workspace |
| Create Staff User | `POST` | `/api/v1/users/admin/users/create/` | Create tenant user |
| User Detail / Update | `GET`, `PUT` | `/api/v1/users/admin/users/{user_id}/` | View or edit user |
| Assign Role | `POST` | `/api/v1/users/admin/users/{user_id}/assign-role/` | Assign role to staff |
| Assign Direct Permissions | `POST` | `/api/v1/users/admin/users/{user_id}/assign-permissions/` | Granular overrides |
| Deactivate User | `POST` | `/api/v1/users/admin/users/{user_id}/deactivate/` | Disable user access |
| Admin Reset User Password | `POST` | `/api/v1/users/admin/users/{user_id}/reset-password/` | Admin sets/resets staff password |
| Roles (Superadmin) | `GET`, `POST` | `/api/v1/users/admin/roles/` | List / create platform roles |
| Role Detail & Perms | `GET`, `PUT`, `DELETE` | `/api/v1/users/admin/roles/{role_id}/` | + `/assign-permissions/` |
| Permissions Catalog | `GET`, `POST` | `/api/v1/users/admin/permissions/` | + `/{permission_id}/` |

---

### Module 2: Organizations, Multi-Tenancy & Subscriptions/Billing (`/api/v1/organizations/`)
| Feature | Method | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| Public SaaS Signup | `POST` | `/api/v1/organizations/register/` | Creates Organization (30-day trial) + Owner + JWT tokens |
| My Organizations | `GET` | `/api/v1/organizations/me/` | Populates workspace switcher dropdown |
| Switch Active Workspace | `POST` | `/api/v1/organizations/switch/` | `{ organization_id }` → returns refreshed org-scoped JWT |
| Organization Settings | `GET`, `PUT`, `PATCH` | `/api/v1/organizations/{organization_id}/` | View/update name, currency, branding |
| Invite Team Member | `POST` | `/api/v1/organizations/invite/` | `{ email, role }` |
| Accept Invitation | `POST` | `/api/v1/organizations/accept-invite/` | `{ token, password, first_name, last_name }` |
| Deactivate / Reactivate Org | `POST` | `/api/v1/organizations/{organization_id}/deactivate/` | + `/reactivate/` |
| **Public Pricing Plans** | `GET` | `/api/v1/organizations/plans/` | Lists active subscription plans, prices, intervals, limits |
| **Initialize Paystack Checkout** | `POST` | `/api/v1/organizations/billing/initialize/` | `{ plan_id, callback_url }` → returns `authorization_url`, `access_code`, `reference` |
| **Verify Paystack Payment** | `POST` | `/api/v1/organizations/billing/verify/` | `{ reference }` → activates subscription & updates `plan_expires_at` |
| **Billing History** | `GET` | `/api/v1/organizations/billing/transactions/` | Past subscription invoices/receipts |
| Superadmin: All Orgs | `GET`, `POST` | `/api/v1/organizations/admin/list/`, `/admin/create/` | Superadmin only |
| Superadmin: Manage Plans | `GET`, `POST`, `PUT` | `/api/v1/organizations/admin/plans/`, `/admin/plans/{plan_id}/` | Superadmin only |

---

### Module 3: General Ledger, Chart of Accounts & Financial Reports (`/api/v1/ledger/`)
| Feature | Method | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| Chart of Accounts (List/Create) | `GET`, `POST` | `/api/v1/ledger/admin/accounts/`, `/admin/accounts/create/` | Also public read at `/api/v1/ledger/public/accounts/` |
| Account Detail / Update | `GET`, `PUT`, `DELETE` | `/api/v1/ledger/admin/accounts/{account_id}/` | Edit/inspect GL account |
| Journal Entries (List) | `GET` | `/api/v1/ledger/admin/entries/` | Filter by date, module, status |
| Post Journal Entry | `POST` | `/api/v1/ledger/admin/entries/post/` | Must balance (`Sum(debit) == Sum(credit)`) |
| Journal Entry Detail / Reverse | `GET`, `POST` | `/api/v1/ledger/admin/entries/{entry_id}/`, `/reverse/` | Double-entry reversal |
| **Trial Balance** | `GET` | `/api/v1/ledger/admin/trial-balance/` | `?as_of_date=YYYY-MM-DD` |
| **Profit & Loss (Income Statement)** | `GET` | `/api/v1/ledger/admin/reports/profit-and-loss/` | `?start_date=...&end_date=...` |
| **Balance Sheet** | `GET` | `/api/v1/ledger/admin/reports/balance-sheet/` | `?as_of_date=YYYY-MM-DD` |
| **Cash Flow Statement** | `GET` | `/api/v1/ledger/admin/reports/cash-flow/` | `?start_date=...&end_date=...` |
| **GL Account Statement** | `GET` | `/api/v1/ledger/admin/reports/gl-statement/{account_id}/` | Running balance ledger |
| **Executive / CEO Dashboard** | `GET` | `/api/v1/ledger/admin/reports/ceo-dashboard/` | KPIs, revenue, cash, AR/AP summary |
| Company Profile | `GET`, `PUT` | `/api/v1/ledger/admin/company-profile/` | Legal name, TIN, business address, prefixes |
| Departments & Cost Centres | `GET`, `POST` | `/api/v1/ledger/admin/departments/`, `/admin/cost-centres/` | Organizational cost tracking |

---

### Module 4: Invoicing & Customizable Excel Import/Export (`/api/v1/invoicing/`)
*(See [FRONTEND_INVOICING_INTEGRATION_GUIDE.md](./FRONTEND_INVOICING_INTEGRATION_GUIDE.md) and [FRONTEND_INVOICING_EXCEL_GUIDE.md](./FRONTEND_INVOICING_EXCEL_GUIDE.md) for full payloads.)*

| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Categories | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoicing/categories/`, `/categories/seed-defaults/`, `/categories/{id}/` |
| Template Builder & Presets | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoicing/templates/`, `/templates/presets/`, `/templates/apply-preset/`, `/templates/preview/`, `/templates/{id}/` |
| Billable Catalog | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoicing/items/`, `/items/{id}/` |
| Commercial Invoices | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoicing/invoices/`, `/invoices/{id}/` |
| Approve / Credit Note / Void / Render | `POST`, `GET` | `/invoices/{id}/approve/`, `/credit-note/`, `/void/`, `/render/` |
| Recurring Schedules | `GET`, `POST`, `PUT` | `/api/v1/invoicing/schedules/`, `/schedules/run-due/`, `/schedules/{id}/` |
| **Excel Header Setup (Templates)** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoicing/excel/templates/`, `/excel/templates/{id}/`, `/excel/templates/reset-default/` |
| **Excel Template Download** | `GET` | `/api/v1/invoicing/excel/template/download/?template_id=...` |
| **Excel Upload Preview & Commit** | `POST` | `/api/v1/invoicing/excel/preview/`, `/api/v1/invoicing/excel/commit/` |
| **Export Invoices to Excel** | `GET` | `/api/v1/invoicing/invoices/export/` (also `/api/v1/invoicing/excel/export/`) |

---

### Module 5: Accounts Receivable (`/api/v1/receivables/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Clients (Customers) | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/receivables/admin/clients/`, `/admin/clients/{client_id}/` |
| Customer Statement | `GET` | `/api/v1/receivables/admin/clients/{client_id}/statement/` |
| Client Invoices | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/receivables/admin/invoices/`, `/{invoice_id}/`, `/{invoice_id}/issue/`, `/{invoice_id}/render/` |
| Client Invoice Templates | `GET`, `POST`, `PUT` | `/api/v1/receivables/admin/invoice-templates/`, `/presets/`, `/preview/` |
| Paystack Invoice Payment | `POST` | `/api/v1/receivables/invoices/{invoice_id}/paystack/initialize/`, `/invoices/paystack/verify/` |
| Payment Receipts | `GET`, `POST`, `PUT` | `/api/v1/receivables/admin/receipts/`, `/admin/receipts/{receipt_id}/` |
| AR Aging Report | `GET` | `/api/v1/receivables/admin/aging-report/` |

---

### Module 6: Accounts Payable & Expense Claims (`/api/v1/payables/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Suppliers (Vendors) | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/payables/admin/suppliers/`, `/{supplier_id}/`, `/{supplier_id}/statement/` |
| Purchase Orders (PO) | `GET`, `POST`, `PUT` | `/api/v1/payables/admin/purchase-orders/`, `/{po_id}/` |
| Goods Received Notes (GRN) | `GET`, `POST`, `PUT` | `/api/v1/payables/admin/goods-received-notes/`, `/{grn_id}/` |
| Supplier Bills & 3-Way Match | `GET`, `POST` | `/api/v1/payables/admin/invoices/`, `/{invoice_id}/`, `/{invoice_id}/match/` |
| Payment Vouchers | `GET`, `POST` | `/api/v1/payables/admin/vouchers/`, `/{voucher_id}/submit/`, `/review/`, `/approve/`, `/reject/`, `/mark-paid/` |
| Expense Claims | `GET`, `POST` | `/api/v1/payables/admin/expense-claims/`, `/{claim_id}/submit/`, `/approve/`, `/reject/`, `/settle/` |
| AP Aging Report | `GET` | `/api/v1/payables/admin/aging-report/` |

---

### Module 7: Treasury, Cashbook & Bank Reconciliation (`/api/v1/treasury/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Bank Accounts | `GET`, `POST`, `PUT` | `/api/v1/treasury/admin/accounts/`, `/{account_id}/` |
| Cashbook | `GET` | `/api/v1/treasury/admin/cashbook/` |
| Bank Statements & Import | `GET`, `POST` | `/api/v1/treasury/admin/statements/`, `/statements/import/`, `/{statement_id}/` |
| Reconciliation Engine | `GET`, `POST` | `/admin/reconciliation/summary/`, `/auto-match/`, `/manual-match/`, `/manual-unmatch/{line_id}/`, `/adjust/` |
| Reconciliations & Finalize | `GET`, `POST` | `/api/v1/treasury/admin/reconciliations/`, `/{reconciliation_id}/`, `/{reconciliation_id}/finalize/` |
| Bank Transactions | `GET`, `POST` | `/api/v1/treasury/admin/transactions/`, `/{transaction_id}/reconcile/` |
| Cash Flow Forecast | `GET` | `/api/v1/treasury/admin/forecast/` |
| Live Bank Feeds | `GET`, `POST` | `/admin/accounts/{bank_account_id}/feed-session/`, `/feed-exchange/`, `/feed-disconnect/`, `/feed-config/`, `/sync-feed/` |

---

### Module 8: Fixed Assets (`/api/v1/assets/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Asset Categories | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/assets/admin/categories/`, `/{category_id}/` |
| Fixed Asset Register | `GET`, `POST`, `PUT` | `/api/v1/assets/admin/assets/`, `/{asset_id}/` |
| Depreciation Schedule & Dispose | `GET`, `POST` | `/api/v1/assets/admin/assets/{asset_id}/schedule/`, `/dispose/` |
| Monthly Depreciation Runs | `GET`, `POST` | `/api/v1/assets/admin/depreciation-runs/`, `/{run_id}/`, `/{run_id}/post/` |
| Asset Register Summary KPIs | `GET` | `/api/v1/assets/admin/summary/` |

---

### Module 9: Payroll Escrow (`/api/v1/payroll-escrow/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Client Escrow Balance | `GET` | `/api/v1/payroll-escrow/public/client-balance/{client_id}/` |
| Payroll Batches (List/Create) | `GET`, `POST` | `/api/v1/payroll-escrow/admin/batches/`, `/{batch_id}/` |
| Disburse Payroll Batch | `POST` | `/api/v1/payroll-escrow/admin/batches/{batch_id}/disburse/` |

---

### Module 10: Taxation & Statutory Returns (`/api/v1/taxation/`)
| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Public Tax Calculator | `POST` | `/api/v1/taxation/public/calculate/` |
| Tax Rules | `GET`, `POST`, `PUT` | `/api/v1/taxation/admin/rules/`, `/{rule_id}/` |
| VAT Return Summary | `GET` | `/api/v1/taxation/admin/returns/vat-summary/` |
| SSNIT Return Summary & Schedule | `GET` | `/api/v1/taxation/admin/returns/ssnit-summary/`, `/ssnit-schedule/` |
| SSNIT Exports & Voucher | `GET`, `POST` | `/ssnit-export/`, `/ssnit-multi-client-export/`, `/ssnit-voucher/` |
| Indirect Tax Calculator | `POST` | `/api/v1/taxation/admin/calculate/indirect-tax/` |

---

### Module 11: Budgeting, Contracts & FX Consolidation
| Module | Method | Endpoints |
| :--- | :--- | :--- |
| **Budgeting** (`/api/v1/budgeting/`) | `GET`, `POST`, `PUT` | `/admin/budgets/`, `/{budget_id}/`, `/{budget_id}/submit/`, `/approve/`, `/variance/`, `/admin/pre-commitment-check/` |
| **Contracts** (`/api/v1/contracts/`) | `GET`, `POST`, `PUT` | `/admin/contracts/`, `/{contract_id}/`, `/{contract_id}/profitability/` |
| **Consolidation** (`/api/v1/consolidation/`) | `GET`, `POST` | `/admin/rates/`, `/admin/rates/live/`, `/admin/revaluations/`, `/admin/trial-balance/` |

---

### Module 12: Common — Bulk Excel Migration Hub, Document Vault & Audit Logs (`/api/v1/common/`)
Supports customizable Excel import for `CHART_OF_ACCOUNTS`, `JOURNAL_ENTRY`, `FIXED_ASSET`, `CLIENT`, `SUPPLIER`, `BILLABLE_ITEM`, and `INVOICE`:

| Feature | Method | Endpoint |
| :--- | :--- | :--- |
| Import Templates (Setup Headers) | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/common/imports/templates/?entity_type=...`, `/{template_id}/`, `/reset-default/` |
| Download Excel Template | `GET` | `/api/v1/common/imports/templates/download/?entity_type=...&template_id=...` |
| Upload Preview & Commit | `POST` | `/api/v1/common/imports/preview/`, `/api/v1/common/imports/commit/` |
| Import History | `GET` | `/api/v1/common/imports/jobs/` |
| Document Vault | `GET`, `POST`, `DELETE` | `/api/v1/common/admin/attachments/`, `/{attachment_id}/` |
| Audit Trail (Superadmin Only) | `GET` | `/api/v1/common/admin/audit-logs/` |

---

## 3. End-to-End Frontend Functional Checklist

1. **Auth & Onboarding**:
   * Login (`/login`), Forgot/Reset Password (`/forgot-password`, `/reset-password`), Self-Service Organization Signup (`/register`), Invite Acceptance (`/accept-invite`).
2. **Workspace Switcher & Billing Guard**:
   * Top-bar dropdown populated by `/organizations/me/`; calls `/organizations/switch/` and sets `X-Organization-ID` header on every request.
   * Global `402` handler + trial countdown banner using `days_remaining` from `/organizations/me/`.
   * Paystack checkout + callback verification page (`/billing/verify`).
3. **Accounting Setup (Day-1 Onboarding)**:
   * Company Profile form (`/ledger/admin/company-profile/`).
   * Bulk Excel Migration Wizard (`/common/imports/*`) so new clients can upload their Chart of Accounts, Opening Balances, Clients, Suppliers, and Fixed Assets.
4. **Core Daily Operations**:
   * **Invoicing**: Create/Approve/Void/Credit Note + Custom Excel Header Setup + Excel Upload & Export.
   * **Receivables**: Client management, Payment Receipts, Paystack invoice payment links, AR Aging.
   * **Payables**: Suppliers, POs, GRNs, 3-Way Match, Payment Voucher approval workflow, Expense Claims.
   * **Treasury**: Bank Accounts, Statement Import, Auto/Manual Reconciliation, Cashbook, Forecast.
   * **Assets, Payroll, Taxation, Budgets, Contracts**: Register, monthly depreciation runs, payroll disbursement, VAT/SSNIT returns, budget variance, contract profitability.
5. **Financial Statements**:
   * Executive Dashboard, Profit & Loss, Balance Sheet, Cash Flow, Trial Balance, Consolidated Trial Balance, GL Account Statements.
