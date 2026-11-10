# SBP Africa Financial Management System (SBP-FMS) - Backend Developer Guide

Welcome to the **SBP-FMS** backend repository. This backend is engineered specifically for SBP Africa Group's multi-country Employer of Record (EOR), HR outsourcing, and workforce management operations across Ghana, Nigeria, Kenya, and Francophone West Africa (UEMOA).

---

## 1. Architectural Philosophy: The Service-Selector Pattern

SBP-FMS does **not** use Django REST Framework ViewSets or Django Admin. Instead, the entire backend is structured around the **HackSoft Service-Selector Pattern** with explicit, granular Role-Based Access Control (RBAC) and automated cache invalidation.

```text
               ┌────────────────────────────────────────────────────────┐
               │             INCOMING HTTP REQUEST + JWT TOKEN          │
               └───────────────────────────┬────────────────────────────┘
                                           │
                         [JWTAuthentication & RBAC Check]
                         (Role, Country Scope & Permission Code)
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
             ┌─────────────────────┐               ┌─────────────────────┐
             │    api/public.py    │               │     api/admin.py    │
             │   (Public APIView)  │               │   (Admin APIView)   │
             └──────────┬──────────┘               └──────────┬──────────┘
                        │                                     │
                        │ 1. Validate Input                   │ 1. Validate Input
                        ▼                                     ▼
             ┌─────────────────────┐               ┌─────────────────────┐
             │   serializers.py    │               │   serializers.py    │
             │  (Input Serializer) │               │  (Input Serializer) │
             └──────────┬──────────┘               └──────────┬──────────┘
                        │                                     │
           ┌────────────┴─────────────────────────────────────┴────────────┐
           │                                                               │
     [READ QUERY]                                                   [MUTATION / WRITE]
           │                                                               │
           ▼                                                               ▼
┌─────────────────────┐                                         ┌─────────────────────┐
│    selectors.py     │                                         │     services.py     │
│  • Check Redis Cache│                                         │  • Business Logic   │
│  • DB Fallback Query│                                         │  • Atomic DB Commit │
│  • Write Cache Back │                                         │  • Invalidate Cache │
└──────────┬──────────┘                                         └──────────┬──────────┘
           │                                                               │
           │ 2. Return QuerySet / Data                                     │ 2. Return Model Instance
           └──────────────────────────────┬────────────────────────────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │   serializers.py    │
                               │ (Output Serializer) │
                               └──────────┬──────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │ HTTP 200 / 201 JSON │
                               └─────────────────────┘
```

---

## 2. Roles, Permissions & Authentication (Zero Django Admin)

Because SBP-FMS operates as a headless API for React/Next.js and external banking portals, **Django Admin is completely excluded**. Access control is governed by an enterprise dynamic Role-Based Access Control (RBAC) model and JWT token authentication powered by `djangorestframework-simplejwt`.

### Dynamic Roles & Permissions Created by Superuser

All enterprise roles and granular permissions are stored as first-class database entities (`Role` and `Permission`) and are **created, updated, and assigned strictly by the Superuser** (`is_superuser=True`).

* **Permissions (`Permission`)**: Granular action codes (e.g. `ledger:read`, `ledger:write`, `payroll:disburse`).
* **Roles (`Role`)**: Collections of permissions assigned to users (e.g. `FINANCE_MANAGER`, `CHIEF_ACCOUNTANT`).
* **Assignment**: The superuser assigns roles and/or direct granular permissions to users.

### The Standard Initial Enterprise Roles

1. **`SUPER_ADMIN`** (CEO / Board): Global read/write access across all countries and modules (`*`).
2. **`FINANCE_MANAGER`**: Full group-level financial control, journal approvals, payment authorizations, and multi-country consolidated reports.
3. **`CHIEF_ACCOUNTANT`**: General ledger owner, trial balance verification, period closing, and reversal entries.
4. **`ACCOUNTS_RECEIVABLE_OFFICER`** (`AR_OFFICER`): Client billing profiles, invoice generation, customer statements, and debt collection monitoring.
5. **`ACCOUNTS_PAYABLE_OFFICER`** (`AP_OFFICER`): Supplier verification, purchase order checking, and 3-way matching.
6. **`PAYROLL_ACCOUNTANT`**: Monthly workforce payroll batch creation and client escrow deposit tracking.
7. **`TREASURY_OFFICER`**: Bank account management, daily statement imports, fuzzy transaction matching, and 90-day cash forecasting.
8. **`INTERNAL_AUDITOR`**: **Strictly Read-Only** access across all financial ledgers, journals, tax filings, and audit trails. Cannot post, reverse, approve, or disburse any funds.
9. **`COUNTRY_ACCOUNTANT`**: Localized accounting operations, strictly bounded to their assigned operating country (e.g., Ghana, Côte d'Ivoire, Burkina Faso).

### Multi-Tenant Country Scoping & Segregation of Duties

* **Country Scoping (`CountryScopedAccess`)**: If a user is assigned to `'GH'` (Ghana), they cannot query or post transactions with `'CI'` (Côte d'Ivoire) or `'BF'` (Burkina Faso). Group-level roles have unconstrained multi-country visibility.
* **Segregation of Duties (`SegregationOfDuties`)**: Enforces that the officer preparing/initiating a journal, payment, or payroll release cannot approve or disburse it (`created_by != approved_by`).

---

## 3. Caching & Cache Invalidation Framework

High-volume financial queries (e.g., Trial Balances, Overdue Debtor Aging, and Cash Liquidity Forecasts) are cached in Redis via `apps/common/cache.py` (`CacheManager`).

### Standardized Cache Keys

| Query Target | Cache Key Pattern | Default TTL | Invalidation Trigger |
| :--- | :--- | :--- | :--- |
| **Trial Balance** | `fms:tb:{country}:{date}` | 30 minutes | Journal entry posted or reversed |
| **Debtor Aging Report** | `fms:aging:{country}` | 30 minutes | Client invoice issued or payment allocated |
| **90-Day Cash Forecast** | `fms:forecast` | 30 minutes | Journal posted, payroll released, or invoice issued |
| **Client Escrow Balance**| `fms:escrow:{client_id}:{country}` | 30 minutes | Client funding deposited or payroll disbursed |
| **Active Chart of Accounts**| `fms:accounts:{country}:{is_active}`| 60 minutes | New account created or modified |

---

## 4. Complete API Endpoints Reference

### Authentication & User Management (`/api/v1/users/`)
* `POST /api/v1/users/public/login/`: Authenticate with email & password. Returns JWT `access` & `refresh` tokens, user profile, and active permissions list.
* `POST /api/v1/users/public/token/refresh/`: Refresh an expired access token using a valid refresh token.
* `POST /api/v1/users/public/token/verify/`: Validate an existing JWT token.
* `GET /api/v1/users/public/me/`: Retrieve current authenticated user profile, role, and country scope.

#### Superuser Role & Permission Endpoints (Restricted to `is_superuser`)
* `GET /api/v1/users/admin/permissions/`: List all granular permission codes (filterable by `?module=ledger`).
* `POST /api/v1/users/admin/permissions/`: Create a new permission code.
* `GET /api/v1/users/admin/permissions/<uuid:id>/`: Get permission details.
* `PUT /api/v1/users/admin/permissions/<uuid:id>/`: Update a permission.
* `DELETE /api/v1/users/admin/permissions/<uuid:id>/`: Delete a permission.
* `GET /api/v1/users/admin/roles/`: List all enterprise roles and their permissions.
* `POST /api/v1/users/admin/roles/`: Create a new enterprise role with initial permissions.
* `GET /api/v1/users/admin/roles/<uuid:id>/`: Retrieve role details.
* `PUT /api/v1/users/admin/roles/<uuid:id>/`: Update role details.
* `DELETE /api/v1/users/admin/roles/<uuid:id>/`: Delete role.
* `POST /api/v1/users/admin/roles/<uuid:id>/assign-permissions/`: Assign/sync permissions to a role.
* `POST /api/v1/users/admin/users/create/`: Provision new finance staff account with assigned role and country.
* `GET /api/v1/users/admin/users/`: List enterprise staff accounts.
* `GET /api/v1/users/admin/users/<uuid:id>/`: Retrieve staff user profile.
* `PUT /api/v1/users/admin/users/<uuid:id>/`: Modify user role and country scoping.
* `POST /api/v1/users/admin/users/<uuid:id>/assign-role/`: Assign role to a user.
* `POST /api/v1/users/admin/users/<uuid:id>/assign-permissions/`: Assign direct granular permissions to a user.
* `POST /api/v1/users/admin/users/<uuid:id>/deactivate/`: Revoke user access.

### General Ledger (`/api/v1/ledger/`)
* `GET /api/v1/ledger/public/accounts/`: Active chart of accounts list for dropdowns (cached).
* `GET /api/v1/ledger/admin/accounts/`: Full COA list with type filters (`permission: ledger:read`).
* `POST /api/v1/ledger/admin/accounts/create/`: Create COA account (`permission: ledger:write`).
* `GET /api/v1/ledger/admin/accounts/<uuid:id>/`: Retrieve COA account details (`permission: ledger:read`).
* `PUT /api/v1/ledger/admin/accounts/<uuid:id>/`: Update COA account (`permission: ledger:write`).
* `PATCH /api/v1/ledger/admin/accounts/<uuid:id>/`: Partially update COA account (`permission: ledger:write`).
* `DELETE /api/v1/ledger/admin/accounts/<uuid:id>/`: Delete COA account (`permission: ledger:write`).
* `GET /api/v1/ledger/admin/entries/`: List journal entries (`permission: ledger:read`).
* `POST /api/v1/ledger/admin/entries/post/`: Atomically post balanced journal (`permission: ledger:write`).
* `GET /api/v1/ledger/admin/entries/<uuid:id>/`: Retrieve journal entry details (`permission: ledger:read`).
* `DELETE /api/v1/ledger/admin/entries/<uuid:id>/`: Delete draft journal entry (`permission: ledger:write`).
* `POST /api/v1/ledger/admin/entries/<uuid:id>/reverse/`: Reverse posted journal (`permission: ledger:reverse`).
* `GET /api/v1/ledger/admin/trial-balance/?country=GH&date=YYYY-MM-DD`: Cached trial balance audit.

### Payroll Escrow (`/api/v1/payroll-escrow/`)
* `GET /api/v1/payroll-escrow/public/client-balance/<uuid:client_id>/`: Client escrow deposit balance (cached).
* `GET /api/v1/payroll-escrow/admin/batches/`: List client payroll batches (`permission: payroll:read`).
* `POST /api/v1/payroll-escrow/admin/batches/`: Create monthly payroll batch (`permission: payroll:create`).
* `GET /api/v1/payroll-escrow/admin/batches/<uuid:id>/`: Retrieve payroll batch details (`permission: payroll:read`).
* `PUT /api/v1/payroll-escrow/admin/batches/<uuid:id>/`: Update payroll batch (`permission: payroll:create`).
* `PATCH /api/v1/payroll-escrow/admin/batches/<uuid:id>/`: Partially update payroll batch (`permission: payroll:create`).
* `DELETE /api/v1/payroll-escrow/admin/batches/<uuid:id>/`: Delete payroll batch (`permission: payroll:create`).
* `POST /api/v1/payroll-escrow/admin/batches/<uuid:id>/disburse/`: Release payroll through solvency gatekeeper (`permission: payroll:disburse`).

### Accounts Payable (`/api/v1/payables/`)
* `GET /api/v1/payables/public/invoices/<uuid:id>/status/`: Vendor checks bill status.
* `GET /api/v1/payables/admin/suppliers/`: List registered vendors (`permission: payables:read`).
* `POST /api/v1/payables/admin/suppliers/`: Register new vendor (`permission: payables:create`).
* `GET /api/v1/payables/admin/suppliers/<uuid:id>/`: Retrieve vendor profile (`permission: payables:read`).
* `PUT /api/v1/payables/admin/suppliers/<uuid:id>/`: Update vendor profile (`permission: payables:create`).
* `PATCH /api/v1/payables/admin/suppliers/<uuid:id>/`: Partially update vendor profile (`permission: payables:create`).
* `DELETE /api/v1/payables/admin/suppliers/<uuid:id>/`: Delete vendor profile (`permission: payables:create`).
* `GET /api/v1/payables/admin/purchase-orders/`: List purchase orders (`permission: payables:read`).
* `POST /api/v1/payables/admin/purchase-orders/`: Create purchase order (`permission: payables:create`).
* `GET /api/v1/payables/admin/purchase-orders/<uuid:id>/`: Retrieve PO details (`permission: payables:read`).
* `PUT /api/v1/payables/admin/purchase-orders/<uuid:id>/`: Update PO (`permission: payables:create`).
* `DELETE /api/v1/payables/admin/purchase-orders/<uuid:id>/`: Delete PO (`permission: payables:create`).
* `GET /api/v1/payables/admin/goods-received-notes/`: List GRNs (`permission: payables:read`).
* `POST /api/v1/payables/admin/goods-received-notes/`: Create GRN (`permission: payables:create`).
* `GET /api/v1/payables/admin/goods-received-notes/<uuid:id>/`: Retrieve GRN details (`permission: payables:read`).
* `PUT /api/v1/payables/admin/goods-received-notes/<uuid:id>/`: Update GRN (`permission: payables:create`).
* `DELETE /api/v1/payables/admin/goods-received-notes/<uuid:id>/`: Delete GRN (`permission: payables:create`).
* `GET /api/v1/payables/admin/invoices/`: List supplier invoices (`permission: payables:read`).
* `POST /api/v1/payables/admin/invoices/`: Create supplier invoice (`permission: payables:create`).
* `GET /api/v1/payables/admin/invoices/<uuid:id>/`: Retrieve supplier invoice details (`permission: payables:read`).
* `PUT /api/v1/payables/admin/invoices/<uuid:id>/`: Update supplier invoice (`permission: payables:create`).
* `DELETE /api/v1/payables/admin/invoices/<uuid:id>/`: Delete supplier invoice (`permission: payables:create`).
* `POST /api/v1/payables/admin/invoices/<uuid:id>/match/`: Execute 3-way match against PO and GRN (`permission: payables:match`).

### Accounts Receivable (`/api/v1/receivables/`)
* `GET /api/v1/receivables/public/clients/<uuid:client_id>/invoices/`: Client billing statements.
* `GET /api/v1/receivables/admin/clients/`: List clients and credit limits (`permission: receivables:read`).
* `POST /api/v1/receivables/admin/clients/`: Create client account (`permission: receivables:create`).
* `GET /api/v1/receivables/admin/clients/<uuid:id>/`: Retrieve client details (`permission: receivables:read`).
* `PUT /api/v1/receivables/admin/clients/<uuid:id>/`: Update client details (`permission: receivables:create`).
* `PATCH /api/v1/receivables/admin/clients/<uuid:id>/`: Partially update client (`permission: receivables:create`).
* `DELETE /api/v1/receivables/admin/clients/<uuid:id>/`: Delete client (`permission: receivables:create`).
* `GET /api/v1/receivables/admin/invoices/`: List client invoices (`permission: receivables:read`).
* `POST /api/v1/receivables/admin/invoices/`: Issue client invoice (`permission: receivables:create`).
* `GET /api/v1/receivables/admin/invoices/<uuid:id>/`: Retrieve invoice details (`permission: receivables:read`).
* `PUT /api/v1/receivables/admin/invoices/<uuid:id>/`: Update invoice (`permission: receivables:create`).
* `DELETE /api/v1/receivables/admin/invoices/<uuid:id>/`: Delete invoice (`permission: receivables:create`).
* `GET /api/v1/receivables/admin/aging-report/?country=GH`: 30/60/90-day overdue debtor buckets (cached).

### Treasury & Cash Management (`/api/v1/treasury/`)
* `POST /api/v1/treasury/public/webhook/`: Bank statement feed webhook.
* `GET /api/v1/treasury/admin/accounts/`: Bank accounts list (`permission: treasury:read`).
* `POST /api/v1/treasury/admin/accounts/`: Create bank account linked to GL (`permission: treasury:write`).
* `GET /api/v1/treasury/admin/accounts/<uuid:id>/`: Retrieve bank account details (`permission: treasury:read`).
* `PUT /api/v1/treasury/admin/accounts/<uuid:id>/`: Update bank account (`permission: treasury:write`).
* `DELETE /api/v1/treasury/admin/accounts/<uuid:id>/`: Delete bank account (`permission: treasury:write`).
* `GET /api/v1/treasury/admin/transactions/`: Bank statement lines (`permission: treasury:read`).
* `POST /api/v1/treasury/admin/transactions/`: Record bank transaction (`permission: treasury:write`).
* `GET /api/v1/treasury/admin/transactions/<uuid:id>/`: Retrieve transaction details (`permission: treasury:read`).
* `PUT /api/v1/treasury/admin/transactions/<uuid:id>/`: Update transaction (`permission: treasury:write`).
* `DELETE /api/v1/treasury/admin/transactions/<uuid:id>/`: Delete transaction (`permission: treasury:write`).
* `POST /api/v1/treasury/admin/transactions/<uuid:id>/reconcile/`: Reconcile transaction against GL (`permission: treasury:reconcile`).
* `GET /api/v1/treasury/admin/forecast/`: 30/60/90-day executive liquidity forecast (cached).

### Taxation (`/api/v1/taxation/`)
* `POST /api/v1/taxation/public/calculate/`: Salary tax & Ghana SSNIT calculator.
* `GET /api/v1/taxation/admin/rules/`: Multi-country tax brackets (`permission: tax:read`).
* `POST /api/v1/taxation/admin/rules/`: Create statutory tax rule (`permission: tax:write`).
* `GET /api/v1/taxation/admin/rules/<uuid:id>/`: Retrieve tax rule details (`permission: tax:read`).
* `PUT /api/v1/taxation/admin/rules/<uuid:id>/`: Update tax rule (`permission: tax:write`).
* `PATCH /api/v1/taxation/admin/rules/<uuid:id>/`: Partially update tax rule (`permission: tax:write`).
* `DELETE /api/v1/taxation/admin/rules/<uuid:id>/`: Delete tax rule (`permission: tax:write`).


---

## 5. Seed Users & Quickstart

Default seed credentials initialized in `seed_data.py`:

| Email | Default Password | Role | Country Scope |
| :--- | :--- | :--- | :--- |
| `ceo@sbp-africa.com` | `Password123!` | `SUPER_ADMIN` | Global (All Countries) |
| `finance.mgr@sbp-africa.com` | `Password123!` | `FINANCE_MANAGER` | Global (All Countries) |
| `chief.acct@sbp-africa.com` | `Password123!` | `CHIEF_ACCOUNTANT` | Global (All Countries) |
| `auditor@sbp-africa.com` | `Password123!` | `INTERNAL_AUDITOR` | Global (Strict Read-Only) |
| `gh.acct@sbp-africa.com` | `Password123!` | `COUNTRY_ACCOUNTANT` | Ghana (`GH`) Only |
| `payroll@sbp-africa.com` | `Password123!` | `PAYROLL_ACCOUNTANT` | Global |
| `treasury@sbp-africa.com` | `Password123!` | `TREASURY_OFFICER` | Global |

### Booting Up with Docker
```bash
cd sbp_fms
docker compose up --build -d
docker compose exec api python manage.py migrate
docker compose exec api python seed_data.py
```
