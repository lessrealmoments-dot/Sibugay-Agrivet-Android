# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business (originally single-tenant). Now converting to a **subscription-based, multi-tenant SaaS platform** — similar to QuickBooks for Philippine retail businesses.

**Tagline:** Audit-Grade Retail Intelligence  
**Sub-tagline:** Serious control for serious businesses  
**Built for:** Growing businesses

---

## CRITICAL AGENT RULES (CARRY TO ALL FORKS)

1. **Explain before coding** — Before making ANY code change, explain what you will change, show the formula/logic, and wait for user approval. No exceptions.
2. **Ask before creating new modules** — Always check if an existing module already handles it. Improve existing modules instead of creating new ones. Ask the user to confirm.
3. **Minimal changes** — Only touch what needs to be touched. If something is already fixed, don't re-change it.
4. **No back-and-forth** — Get it right the first time. Think through the formula and edge cases before proposing.

---

## CRITICAL AGENT NOTE — VPS DEPLOYMENT
**EVERY TIME code is ready to deploy to agri-books.com, ALWAYS include these 3 commands:**

```bash
cd /var/www/agribooks && git pull origin main
cd backend && source venv/bin/activate && pip install -r requirements.txt
supervisorctl restart agribooks-backend
cd ../frontend && yarn build
```

**Steps before running the above:**
1. User must click **"Save to Github"** in Emergent first to push the code
2. SSH into VPS: `ssh root@76.13.215.32`
3. Run the commands above in order

**VPS Details:**
- Domain: `agri-books.com`
- IP: `76.13.215.32`
- User: `root`
- Backend managed by: `supervisorctl` (process name: `agribooks-backend`)
- Frontend: static build served by Nginx from `/var/www/agribooks/frontend/build/`
- No hot reload on VPS — backend needs supervisorctl restart, frontend needs yarn build
- **IMPORTANT**: After adding new Python packages, ALWAYS run `pip install -r requirements.txt` on VPS before restarting backend

---

## Core Requirements
- Offline Functionality with auto-sync
- Product Management (3000+ SKUs, parent/repack system)
- Multi-Branch Management (branch-specific data, owner overview, Branch Transfers)
- Advanced Accounting (expenses, receivables, fund management)
- Audit System (verification, receipt review, discrepancy tracking)
- POS with barcode scanning, digital payments, price schemes
- Daily Close Wizard with Z-Report PDF generation
- Journal Entry system for post-close corrections

---

## Component Architecture — Transaction Detail Modals

### CRITICAL: Three Dedicated Modals (as of March 2026)
The app uses **three dedicated, high-quality detail modals** for viewing transactions. The generic `InvoiceDetailModal` has been **removed** and replaced with:

1. **`PODetailModal`** (`/components/PODetailModal.js`)
   - For: Purchase Orders
   - Features: Product list, edit items/DR#/qty/price, verify, upload receipt (QR), view on phone (QR), receipt gallery, receipt review (mark as reviewed), payment history, edit history, payment adjustment after edit, reopened PO banner
   - Props: `open, onOpenChange, poId, poNumber, onUpdated`

2. **`SaleDetailModal`** (`/components/SaleDetailModal.js`)
   - For: Sales/Invoices
   - Features: Product list, edit items, verify, upload receipt, view on phone, receipt gallery, void sale, payment history, edit history, digital payment info
   - Props: `open, onOpenChange, saleId, invoiceNumber, onUpdated`

3. **`ExpenseDetailModal`** (`/components/ExpenseDetailModal.js`)
   - For: Expenses
   - Features: Category/amount/date/fund source display, edit, verify, upload receipt, view on phone, receipt gallery, void/delete expense
   - Props: `open, onOpenChange, expenseId, onUpdated`

### Routing Pattern for Mixed-Type Pages
Pages that show multiple transaction types (Dashboard, TransactionSearch, CloseWizard, AuditCenter, QuickSearch) use a `detailType` state to route to the correct modal:
```javascript
const [detailType, setDetailType] = useState('sale'); // 'sale' | 'po' | 'expense'
// Then render all three modals conditioned on detailType
```

### Pages and Their Modal Usage
| Page | Modal(s) Used |
|------|--------------|
| SuppliersPage | PODetailModal |
| PaySupplierPage | PODetailModal |
| SalesPage | SaleDetailModal |
| CustomersPage | SaleDetailModal |
| InternalInvoicesPage | SaleDetailModal |
| PaymentsPage | SaleDetailModal |
| ReportsPage | SaleDetailModal |
| DailyLogPage | SaleDetailModal |
| ExpensesPage | ExpenseDetailModal + SaleDetailModal (for linked invoices) |
| AccountingPage | ExpenseDetailModal + SaleDetailModal |
| DashboardPage | PODetailModal + SaleDetailModal |
| CloseWizardPage | PODetailModal + SaleDetailModal + ExpenseDetailModal |
| AuditCenterPage | PODetailModal + SaleDetailModal + ExpenseDetailModal |
| TransactionSearchPage | PODetailModal + SaleDetailModal + ExpenseDetailModal |
| QuickSearch | PODetailModal + SaleDetailModal + ExpenseDetailModal |
| PurchaseOrderPage | Uses its own built-in detail dialog (the original standard) |

---

## Pending Issues
- (P0) Smart Journal Entries — context-aware suggestions for inventory discrepancies
- (P0) Over-limit Cash Advances handling
- (P0) Sales History Quick-Action Menu (Re-send Receipt, etc.)
- (P0) Closing History page investigation
- (P1) PWA conversion
- (P1) Weight-embedded EAN-13 barcodes
- (P1) Automated Payment Gateway
- (P1) Demo Login system
- (P2) Corrupted Purchase Orders admin tool
- (P2) SuperAdminPage refactoring (>1000 lines)
- (P2) AdminLoginPage useNavigate fix
- (P2) Merge duplicate expense dialogs (ExpensesPage ↔ AccountingPage)
- (P2) Merge duplicate create product dialogs (PurchaseOrderPage ↔ SalesOrderPage)
- (P2) Clean dead state in SuppliersPage and PaySupplierPage

---

## 3rd Party Integrations
- Cloudflare R2 (object storage)
- Resend (email)
- Google Authenticator (TOTP)
- fpdf2 (PDF generation)
- python-barcode
- jsbarcode
- html5-qrcode

---

## PIN Safety Net System

All destructive financial actions are protected by PIN verification through the `verify_pin_for_action()` system. The admin can configure which PIN methods (admin_pin, manager_pin, totp, auditor_pin) are allowed per action in **Settings > Security > PIN Policies**.

### Protected Actions (PIN_POLICY_ACTIONS in verify.py)
| Action Key | Label | Default Methods |
|------------|-------|----------------|
| `void_invoice` | Void Invoice | admin_pin, manager_pin, totp |
| `cancel_po` | Cancel Purchase Order | admin_pin, manager_pin, totp |
| `void_expense` | Void / Delete Expense | admin_pin, manager_pin, totp |
| `reopen_po` | Reopen Purchase Order | admin_pin, manager_pin, totp |
| `void_payment` | Void Payment on Invoice | admin_pin, manager_pin, totp |
| `void_return` | Void Return | admin_pin, manager_pin, totp |
| `invoice_edit` | Edit Posted Invoice | admin_pin, manager_pin, totp |
| `daily_close` | Close Day (Z-Report) | admin_pin, manager_pin, totp |
| `inventory_adjust` | Direct Inventory Correction | admin_pin, manager_pin, totp |
| `product_delete` | Delete Product | admin_pin, totp |
| `admin_action` | Admin Action (Bulk Ops) | admin_pin, totp |
| `backup_restore` | Restore Backup | admin_pin, totp |

### Frontend Safety Net Implementation
- **SaleDetailModal**: Void requires reason + PIN dialog
- **ExpenseDetailModal**: Void requires PIN input (2-step confirm + PIN)
- **PurchaseOrderPage**: Cancel PO → PIN dialog; Reopen PO → PIN dialog
- **Inline delete buttons**: Route through modal for proper PIN verification

---

## Tech Stack
- **Frontend**: React (CRA + craco), Tailwind CSS, shadcn/ui, Sonner toasts
- **Backend**: FastAPI, Motor (async MongoDB), uvicorn
- **Database**: MongoDB
- **Deployment**: VPS with Nginx + supervisor

## TOTP-Delegated Access System (March 2026)

### Concept
Two-layer authorization for users without section permissions:

**Layer 1 — Section Access Override:**
- Sidebar shows ALL navigation items — locked ones display a lock icon
- Clicking a locked item opens a TOTP/PIN dialog
- Admin reads code from phone, user enters it, access granted for that session
- Delegation is embedded in the JWT token (survives page refreshes within same login)
- Subscription-locked features (FeatureGate) remain hidden (plan upgrade required)

**Layer 2 — Critical Action Authorization:**
- Critical actions (receive PO, pay cash, void, etc.) already require PIN/TOTP verification
- Creates audit trail: "Created by Cashier, Approved by Admin"

### Architecture
- Backend: `/api/auth/section-override` endpoint verifies TOTP/PIN, issues new JWT with `delegations`
- Backend: `check_perm()` checks `user._delegations` for module overrides
- Frontend: `AuthContext` manages delegation state with `requestSectionOverride()`
- Frontend: `SectionOverrideDialog` component, `Layout.js` shows locked items
- Audit Log: All overrides logged to `audit_log` collection

---

## Bug Fixes — March 11, 2026

### Checkout Payment Type Tabs Fix
- **Problem**: Split, Partial, and Credit payment type tabs were disabled in checkout dialog (only Cash and Digital worked)
- **Root Cause**: All three tabs had `disabled={!selectedCustomer}` — preventing use without a customer
- **Fix**: 
  - **Split**: Enabled without customer (cash+digital, no AR involved)
  - **Partial/Credit**: Tabs now clickable (user sees why customer is needed) but confirm button stays disabled without a customer
  - Warning messages guide user to select a customer for Partial/Credit
  - Credit panel conditionally shows customer name or "select a customer" prompt

### Receipt Upload QR Code Visibility Fix
- **Problem**: QR code for phone upload was hidden behind a `<details>` toggle, requiring user to click to expand
- **Fix**: QR code is now always visible alongside the direct PC upload button, with a visual divider "or upload from phone"

### Partial Payment Closing Wizard Fix (March 11, 2026)
- **Problem**: Partial payments (e.g., ₱5,000 cash + ₱7,700 credit on ₱12,700 invoice) showed as a single "partial: ₱12,700" lump in the closing wizard sales log. The ₱5,000 cash wasn't counted in cash totals, and the ₱7,700 credit wasn't in the credit section.
- **Root Cause**: The `by_payment_method` breakdown in the daily-log endpoint decomposed "split" (cash+digital) but NOT "partial" (cash+credit). Partial entries were grouped as a single category.
- **Fix**:
  - Backend `log_sale_items()`: Now accepts `partial_meta` (cash_amount, credit_amount, grand_total) and stores it on sales_log entries
  - Backend `unified-sale` and `invoices` routes: Pass partial metadata when creating partial invoices
  - Backend `daily-log`: Decomposes "partial" into cash + credit in `by_payment_method`, includes partial cash in `cash_entries`, backward-compatible with old entries (falls back to invoice lookup)
  - Frontend CloseWizardPage: Shows cash/credit breakdown on partial entries in sales log table

**autoComplete Fix:**
- Changed 48 instances of `autoComplete="off"` → `autoComplete="new-password"` across 24 files
- LoginPage intentionally left untouched (browser should save login credentials)
- Prevents browser "save password" prompt on all PIN/TOTP inputs throughout the app

**PIN Verification Audit — All Endpoints Connected:**
| Action Key | Backend File | Frontend File | Status |
|---|---|---|---|
| credit_sale_approval | auth.py → verify.py | UnifiedSalesPage.js | ✅ Fixed (cartItems bug) |
| void_invoice | invoices.py | UnifiedSalesPage.js | ✅ |
| cancel_po | purchase_orders.py | PurchaseOrderPage.js | ✅ |
| reopen_po | purchase_orders.py | PurchaseOrderPage.js | ✅ |
| daily_close | daily_operations.py | CloseWizardPage.js, DailyLogPage.js | ✅ |
| daily_close_batch | daily_operations.py | CloseWizardPage.js | ✅ |
| fund_transfer_cashier_safe | accounting.py | FundManagementPage.js | ✅ |
| fund_transfer_safe_bank | accounting.py | FundManagementPage.js | ✅ |
| fund_transfer_capital_add | accounting.py | FundManagementPage.js | ✅ |
| reverse_employee_advance | auth.py → verify.py | ExpensesPage.js, AccountingPage.js, CloseWizardPage.js | ✅ |
| transaction_verify | verify.py | JournalEntriesPage.js, AuditCenterPage.js | ✅ |
- **Problem**: Credit approval dialog hardcoded "Manager PIN" with `maxLength={6}`, ignoring Admin PIN and TOTP as valid authorization methods. Did not reflect configured PIN policies from Settings > Security. **CRITICAL**: The `verifyManagerPin()` function referenced an undefined variable `cartItems` which caused a JavaScript crash before the API call was ever sent — users saw "Verification failed" for ALL PIN types.
- **Root Cause**: `cartItems` does not exist in the component scope; the correct variable is `grandTotal` (already computed). The ReferenceError was caught by the try/catch and displayed as a generic connection error.
- **Fix**: 
  - Replaced `cartItems.reduce(...)` with `grandTotal` (already computed)
  - Removed `maxLength={6}` (admin PINs can be any length)
  - Title changed to "Authorization Required"
  - Shows all accepted methods: Admin PIN, Manager PIN, TOTP (with color-coded badges)
  - Input placeholder: "PIN or 6-digit TOTP code"
  - Added debug logging to backend for future troubleshooting
  - Better error messages on both frontend and backend

### Quick Customer Picker in Checkout Dialog
- **Enhancement**: Added inline customer search directly in the checkout payment dialog
- When no customer is selected, a search input appears with live dropdown results
- Users can pick a customer without leaving the checkout flow (especially useful for Partial/Credit)
- Selected customer shows balance and credit limit, with an X button to clear


### Digital Payment Separation in Closing Formula (Mar 2026)
- **Problem**: In the Close Wizard Sales Log (Step 1) and Daily Log page, digital payments (GCash, Maya, and all other platforms) were incorrectly being added to the "Walk-in Sales" cash running total.
- **Root Cause**: The frontend running total calculation only had special cases for `partial` and `split` payments. All other payment methods fell into the `else` branch.
- **Fix**: Added `CASH_METHODS` set and `isDigital()` helper in both `CloseWizardPage.js` and `DailyLogPage.js`. Digital entries are included in the total but tracked separately. Header shows "Total Sales: ₱X (includes ₱Y digital)".
- **Files Changed**: `CloseWizardPage.js`, `DailyLogPage.js`

### CRITICAL: Partial Payment Routed to Wrong Wallet (Mar 2026)
- **Problem**: `is_digital_payment("Partial")` returned `True`, causing partial payment cash to go to the **digital wallet** instead of the **cashier wallet**. This broke the closing formula because partial cash disappeared from the cash drawer.
- **Root Cause**: In `utils/helpers.py`, the `is_digital_payment()` function's catch-all condition `m not in ("cash", "check", "cheque", "credit", "")` didn't include "partial" or "split", so they were classified as digital.
- **Fix**: Updated `is_digital_payment()` to exclude "partial" and "split" from digital classification. Added migration endpoint `/api/superadmin/migrations/fix-partial-fund-source` to fix existing corrupted data (moves cash from digital wallet → cashier wallet).
- **Files Changed**: `utils/helpers.py`, `routes/superadmin.py`

### Starting Float Formula Fix (Mar 2026)
- **Problem**: For first-ever close (no previous daily close), the starting float showed the current cashier wallet balance (which already includes today's transactions), making the Z-report breakdown meaningless.
- **Fix**: Now reverses today's cash movements to compute the true opening balance: `starting_float = current_balance - cash_in - fund_transfers + expenses`. The formula then correctly shows: Opening Float + Cash In + Transfers - Expenses = Expected.
- **Files Changed**: `routes/daily_operations.py`

### Close Wizard "Find & Pay" Panel Fix + Enhancement (Mar 12, 2026)
- **Problem**: The "Receive payment for a customer (not listed above)" panel in Step 3 of the Closing Wizard was completely non-functional.
- **Root Causes**: (1) `overflow-hidden` CSS on the container clipped the search dropdown, (2) Used wrong API endpoint `/invoices?status=open` instead of `/customers/{id}/invoices`, missing "partial" status invoices, (3) Field name mismatch (`remaining_balance` vs `balance`).
- **Enhancement**: Rebuilt the panel as a mini-PaymentsPage with: multi-invoice per-row allocation, interest generation, penalty generation with configurable %, auto-apply with quick total input, proper use of `/customers/{id}/receive-payment` endpoint for multi-allocation. After payment, wizard data auto-refreshes so the AR payments table updates immediately.
- **Files Changed**: `CloseWizardPage.js`


### QuickBooks-Style Receive Payments Page Redesign (Mar 12, 2026)
- **Change**: Complete layout rearrangement of `PaymentsPage.js` to match QuickBooks "Customer Payment" screen.
- **Layout**: (1) Inline customer search at top with "RECEIVED FROM" label and Customer Balance on right, (2) Payment method as icon buttons (Cash, Check, Bank, GCash, Maya), (3) QB-style invoice table with Date, Number, Type, Orig. Amt, Amt. Due, Discount, Payment columns + Totals row, (4) "Amounts for Selected Invoices" summary panel at bottom-right, (5) Memo field at bottom-left.
- **New Feature — Discount on Interest/Penalty**: Added discount input column for interest_charge and penalty_charge invoice types only. Supports both fixed amount and percentage toggle. Backend records discounts as separate payment entries with `method: "Discount"` and `fund_source: "discount"` (no wallet impact) for proper audit trail.
- **Files Changed**: `PaymentsPage.js`, `routes/accounting.py`

### Inline Interest Rate Override + Save to Customer (Mar 12, 2026)
- **Problem**: Users couldn't generate interest for customers without a pre-configured rate — they had to leave the Receive Payments page and go to Customers → Edit to set the rate first.
- **Fix**: Added editable interest rate input directly in the charges section. Pre-fills with customer's saved rate (if any), or allows entering a new one. Preview updates in real-time (debounced).
- **"Save to profile" option**: When the entered rate differs from the saved rate, a checkbox appears: "Save X%/mo to this customer's profile." If checked, rate is persisted when generating interest.
- **Backend**: `generate-interest` and `charges-preview` endpoints accept `rate_override` parameter. `generate-interest` also accepts `save_rate` boolean.
- **Interest formula**: `principal × (rate/100/30) × days`. Computes from `last_interest_date` (not due date) to prevent double-charging.
- **Files Changed**: `PaymentsPage.js`, `routes/accounting.py`
