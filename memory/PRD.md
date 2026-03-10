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

## Tech Stack
- **Frontend**: React (CRA + craco), Tailwind CSS, shadcn/ui, Sonner toasts
- **Backend**: FastAPI, Motor (async MongoDB), uvicorn
- **Database**: MongoDB
- **Deployment**: VPS with Nginx + supervisor
