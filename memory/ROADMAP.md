# AgriBooks — ROADMAP (Updated Mar 2026)

## Current Session Summary (Mar 2026 Fork Point)

### What Was Completed This Session
| Feature | Status | Key Files |
|---|---|---|
| AP Dashboard widget fix (cancelled POs, AP filter) | ✅ Done | `dashboard.py` |
| ReviewDetailDialog — Verify & Approve button (Phase 2) | ✅ Done | `ReviewDetailDialog.js` |
| Balance bug fix (₱0 display on older POs) | ✅ Done | `dashboard.py` |
| Pay Now panel in AP dialog (Phase 3) | ✅ Done | `ReviewDetailDialog.js`, `purchase_orders.py` |
| Bank/Digital wallet routing + double-entry journal | ✅ Done | `purchase_orders.py`, `journal_entries.py` |
| Batch receipt upload modal (Phase 4) | ✅ Done | `PaySupplierPage.js` |
| Collection receipt — "One receipt covers all" | ✅ Done | `uploads.py` (share-receipt endpoint) |
| Shared receipt provenance in ReviewDetailDialog | ✅ Done | `dashboard.py`, `ReviewDetailDialog.js` |
| Pay Supplier Page — QB-style redesign | ✅ Done | `PaySupplierPage.js` |
| Checkbox + smart budget allocation for multi-PO | ✅ Done | `PaySupplierPage.js` |
| Method icon buttons removed (redundant with Pay From) | ✅ Done | `PaySupplierPage.js` |
| Notification Center v2 — full page `/notifications` | ✅ Done | `NotificationsPage.js`, `NotificationBell.js` |
| Missing notifications: discount, below-cost, neg-stock, AP payment | ✅ Done | `sales.py`, `purchase_orders.py`, `notifications.py` |

---

## Next Up — P0 (Immediate Priority)

### 1. Compliance Calendar Widget — Dashboard ✅ NEXT TO BUILD
**What:** A widget on the main Dashboard showing upcoming business document deadlines.
**Data source:** Already built — `GET /api/documents/compliance/summary` (tested in iteration_140)
**What to build:**
- Summary widget on dashboard showing:
  - Documents expired (red alert count)
  - Expiring within 30 days (amber count)
  - Monthly filings status for current month (SSS, PhilHealth, Pag-IBIG, BIR 1601-C, 0619-E, 2550M)
- Click → navigates to `/documents` compliance view
- Add `compliance-calendar` key to dashboard grid layout
**Files:** `DashboardPage.js`, backend already done

### ~~2. Notification Alerts for Document Compliance Deadlines~~ ✅ DONE (Mar 2026)
APScheduler daily job added — see Notification System Phase 5 in PRD.md.

---

## P1 — Terminal Features

### 3. Quick Stock Check (Terminal)
**What:** Scan/search a product barcode on the terminal and instantly see stock level at current branch + optionally all branches.
**Where:** New mode in terminal floating mode selector (alongside Sales | PO Check | Transfers | Settings)
**Backend:** Reuse `GET /api/products?search=` + `GET /api/inventory?product_id=`
**Frontend:** `TerminalShell.jsx` — new mode card + `TerminalStockCheck.jsx` component
**Key UX:** Scan barcode → instant result card (product name, stock, price, branch). No PIN needed — read-only.

### 4. Price Check (Terminal)
**What:** Scan a barcode → see current retail price + cost (if permission allows) without creating a sale.
**Where:** Same terminal mode selector
**Note:** Respects `products.view_cost` permission — managers only see retail, not capital
**Files:** `TerminalShell.jsx`, new `TerminalPriceCheck.jsx`

### 5. Quick Count (Terminal)
**What:** Cashier scans products and enters counted quantities — submits a quick count sheet.
**Where:** Terminal mode (PIN required — connects to existing count sheet system)
**Backend:** Reuse `POST /api/count-sheets` → `POST /api/count-sheets/{id}/snapshot`
**Files:** `TerminalShell.jsx`, new `TerminalQuickCount.jsx`

---

## P1 — Finance & Audit

### 6. Discount Cashier Drill-Down Report
**What:** In the Notifications page (Approvals tab) or Reports — show each cashier's total discounts this month sorted by amount. Makes it easy to spot patterns.
**Backend:** Aggregate `discount_audit_log` by cashier, group by week/month
**Frontend:** Could be a tab in `/reports` under the existing Discounts tab

### 7. AP Payment History in Pay Supplier Page
**What:** Show recent payment history per supplier below the PO table — when was the last time we paid them, how much, from which wallet.
**Backend:** Query `expenses` where `po_id` is in supplier's PO list OR query `payment_history` on POs
**Files:** `PaySupplierPage.js`

---

## P2 — Backlog

### 8. Shared Receipt Clickable Link in ReviewDetailDialog
**What:** When a PO shows "Collection receipt shared from PO-XXXX", the PO number should be a clickable link that opens that source PO's review dialog.
**Files:** `ReviewDetailDialog.js` — add `onClick={() => openSourcePO(f.shared_from_record_id)}`

### 9. Cross-Branch Payment Wallet Routing
**Current state:** When customer pays at Branch B for Branch A's invoice, cash goes to Branch A's wallet. Correct behavior = Branch B cashier wallet + inter-branch settlement entry.
**Note:** User said "remember this for now" — deferred.

### 10. Admin Tool for Corrupted POs
**What:** Admin page to list/fix purchase_orders with missing fields (no grand_total, no subtotal, etc.)
**Files:** New page or extend `SuperAdminPage.jsx`

### 11. Visual Trail for Partial Invoices
**What:** Show all linked payment transactions for a single invoice — timeline view.
**Files:** `InvoiceDetailModal.js`

### 12. Smart Journal Entries for Back-Dated Sales
**What:** Allow encoding a missed sale on a closed day with proper financial corrections.
**Files:** `UnifiedSalesPage.js`, `journal_entries.py`

---

## P3 — Future / Long Term

### 13. Refactor SuperAdminPage.jsx
1000+ line monolithic component. Break into sub-pages.

### 14. Fix react-hooks/exhaustive-deps ESLint Warnings
3 remaining across the codebase. Low risk, cosmetic only.

### 15. Native Android APK (Capacitor finalization)
- Copy `printer-release.aar` to `android/app/libs/`
- Build signed APK following `ANDROID_BUILD_GUIDE.md`
- H10P thermal printer + Newland scanner native SDK

### 16. Weight-Embedded EAN-13 Barcode Recognition
Decode price/weight from standard grocery weight barcodes.

### 17. Automated Payment Gateway & Demo Login
For SaaS onboarding.

---

## Key Architecture Notes for Next Agent

### AP Payment Flow (NEW — Mar 2026)
```
User selects POs (checkbox) → enters budget → clicks Pay
→ POST /api/purchase-orders/{id}/pay (requires PIN)
→ Wallet deduction (cashier/safe/bank/digital)
→ Expense record created (Z-report picks up)
→ Journal entry auto-created for bank/digital (DR: AP 2000, CR: 1030/1020)
→ Notification fired (ap_payment → Notification Center)
→ Receipt upload modal opens (single OR collection receipt)
→ If collection: POST /api/uploads/share-receipt → mirrors session to all target POs
```

### Notification System (NEW — Mar 2026)
```
All new notifications use create_notification() helper from notifications.py
Fields: type, category, severity, title, message, metadata, target_user_ids, branch_id, org_id
Categories: security | action | approvals | operations | finance
Severities: critical | warning | info
GET /api/notifications returns: notifications[], unread_count, total, category_counts{}
Bell click → /notifications page (full page, no dropdown)
```

### New PIN Policies (Mar 2026)
- `pay_po_standard` — Pay supplier invoice from cashier/safe: admin, manager, TOTP
- `pay_po_bank` — Pay supplier invoice from bank/digital: admin, TOTP only

### New Notification Types (Mar 2026)
- `discount_given` — Sale with discount, includes full item detail + repeat-offender count
- `below_cost_sale` — Sale where item sold below capital
- `negative_stock_override` — Stock override approved, incident ticket auto-created
- `ap_payment` — Supplier payment made, includes PO#, vendor, amount, wallet source

### Credentials
- Super Admin: `janmarkeahig@gmail.com` / `Aa@58798546521325`
- Company Admin: `jovelyneahig@gmail.com` / `Aa@050772`
- Manager PIN: `521325`
- App URL: `https://review-dialog.preview.emergentagent.com`
- DB: MongoDB `test_database` at `localhost:27017`
