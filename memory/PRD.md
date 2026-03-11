# AgriBooks — Product Requirements Document

## Original Problem Statement
Build a comprehensive Accounting, Inventory, and Point of Sale (POS) web application for a multi-branch business (originally single-tenant). Now converting to a **subscription-based, multi-tenant SaaS platform** — similar to QuickBooks for Philippine retail businesses.

**Tagline:** Audit-Grade Retail Intelligence  
**Sub-tagline:** Serious control for serious businesses  
**Built for:** Growing businesses

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
