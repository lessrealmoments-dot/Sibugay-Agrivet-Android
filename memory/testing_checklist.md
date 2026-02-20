# AgriPOS — Comprehensive Testing Checklist

> Use this document to verify all features after updates or deployments.
> Check off each item as you test it. Items marked ⚠️ are common failure points.

---

## 0. PRE-TEST SETUP

- [ ] Log in as **admin/owner** (full access)
- [ ] Select a specific branch in the sidebar (required for expenses, sales, etc.)
- [ ] Verify you are in Online mode (green Wi-Fi indicator on Sales page)

---

## 1. AUTHENTICATION & ACCOUNTS

### 1.1 Login / Logout
- [ ] Log in with correct credentials → redirected to Dashboard
- [ ] Log in with wrong password → shows "Invalid credentials"
- [ ] Log out → redirected to Login

### 1.2 Accounts Page (`/accounts`)
- [ ] Page loads with user table showing all users
- [ ] Role stat cards (Admin/Manager/Cashier/Inventory) show correct counts
- [ ] **Create User**: Click "New User" → fill username, full name, role, branch, password → save
- [ ] Created user appears in table with correct role badge
- [ ] **Set Manager PIN**: Click key icon → enter 4-digit PIN → save → PIN column shows "Set"
- [ ] **Edit User**: Change full name / branch → save → reflected in table
- [ ] **Deactivate User**: Click lock icon → user marked Inactive
- [ ] ⚠️ Cannot deactivate your own account (error message)

### 1.3 User Permissions (`/user-permissions`)
- [ ] Select a user → permissions panel loads
- [ ] Toggle a permission on/off → yellow "unsaved changes" banner appears
- [ ] Click "Save" → changes persist on page refresh
- [ ] Apply Preset (e.g., "Cashier") → permissions update to match preset
- [ ] "None" button disables all permissions in a module
- [ ] "All" button enables all permissions in a module

---

## 2. BRANCHES (`/branches`)

- [ ] Branches page loads with list of branches
- [ ] Create new branch → appears in list
- [ ] Branch shows in the sidebar branch selector

---

## 3. PRODUCTS (`/products`)

### 3.1 Product List
- [ ] Products page loads with product grid
- [ ] Search by name or SKU → filters correctly
- [ ] Filter by category → shows correct products

### 3.2 Create Product
- [ ] Click "New Product" → form opens
- [ ] Fill name, SKU, category, unit, cost price
- [ ] Set prices for at least Retail and Wholesale schemes
- [ ] ⚠️ Retail price cannot be below cost (validation error if attempted)
- [ ] Save → product appears in list

### 3.3 Product Detail (`/products/:id`)
- [ ] Click a product → detail page loads (no "Failed to load" error)
- [ ] Shows inventory per branch
- [ ] Repacks tab shows linked repack products
- [ ] Edit product → changes save correctly

### 3.4 Repack Products
- [ ] Open a parent product → "Generate Repack" button available
- [ ] Create repack with units_per_parent = 12 → repack appears in list with R- SKU prefix
- [ ] Repack cost auto-calculated from parent cost ÷ units

---

## 4. INVENTORY (`/inventory`)

- [ ] Inventory page loads with stock levels per product per branch
- [ ] Count Sheets link works
- [ ] Adjust stock → movement recorded in product history

### 4.1 Count Sheets (`/count-sheets`)
- [ ] Create new count sheet for a branch → snapshot taken
- [ ] Enter counted quantities for each item
- [ ] Complete count sheet → variances applied to inventory
- [ ] Only one active count sheet per branch at a time

---

## 5. SALES PAGE (`/sales-new`) ⚠️ Most Critical

### 5.1 Quick Mode
- [ ] Product search returns results (type at least 1 character)
- [ ] Click product → added to cart
- [ ] ⚠️ **Editable Quantity**: Click the number in cart → type new quantity → updates total
- [ ] ⚠️ **+/- buttons** still work
- [ ] ⚠️ **Editable Price**: Click price field → type new price → total updates
- [ ] Price below cost shows **red warning** ("Below capital ₱X.XX")
- [ ] Price of 0 shows **amber warning** ("Set price before checkout")

### 5.2 Price Scheme (Quick Mode)
- [ ] "Price Scheme" dropdown visible even with no customer selected (walk-in)
- [ ] Change scheme (e.g., Retail → Wholesale) → product prices in grid update
- [ ] Products with no Wholesale price show **₱0.00** in grid
- [ ] Scheme dropdown visible when customer IS selected
- [ ] Change scheme with customer selected → "Update Customer Scheme?" dialog appears
- [ ] Click "No, this sale only" → scheme applies, "Override" badge shows, customer unchanged
- [ ] Click "Yes, update customer" → customer's stored scheme updated (toast confirms)

### 5.3 Customer Selection (Quick Mode)
- [ ] Search and select existing customer → prices reprice to their scheme
- [ ] Type new name → "Create [name] as new customer" option appears
- [ ] Create new customer from sales → customer selected immediately
- [ ] Clear customer → back to walk-in mode

### 5.4 Order Mode
- [ ] Switch to "Order" mode tab
- [ ] Empty row shows SmartProductSearch input
- [ ] ⚠️ **Type in search** → dropdown appears (fixed: uses position:fixed, not clipped)
- [ ] **Click a product in dropdown** → product name shown in the row (not empty!)
- [ ] X button appears on hover → clicking it clears the line back to search mode
- [ ] Qty and Rate fields are editable
- [ ] ⚠️ Rate field with price 0 shows amber border
- [ ] Change rate → blur → "Save Price Change?" dialog appears
- [ ] Add Freight and Overall Discount → Total updates correctly

### 5.5 Checkout
- [ ] ⚠️ Checkout with item price = 0 → **blocked** with error message
- [ ] ⚠️ Checkout with price below capital → **blocked** with error message
- [ ] Cash payment → enter amount tendered → shows change
- [ ] Partial payment → shows balance going to AR
- [ ] **Admin/Manager** doing credit sale → **NO PIN dialog** (auto-approved)
- [ ] Regular cashier doing credit sale → manager PIN dialog appears
- [ ] Successful sale → toast with invoice number, cart clears

---

## 6. PURCHASE ORDERS (`/purchase-orders`)

- [ ] Create PO with supplier and items
- [ ] PO appears in list with "Draft" status
- [ ] Receive items → inventory increases, cost updates if price changed
- [ ] PO status changes to "Received"

---

## 7. SUPPLIERS (`/suppliers`)

- [ ] Create supplier with contact info → appears in list
- [ ] View supplier transaction history
- [ ] Edit supplier details → saves correctly

---

## 8. CUSTOMERS (`/customers`)

- [ ] Customer list loads
- [ ] Create customer with name, phone, price scheme
- [ ] ⚠️ **Set interest rate** (e.g., 2%) and grace period (e.g., 7 days) → required for interest generation in Payments
- [ ] Edit customer → all fields save correctly
- [ ] View customer transaction history → shows all invoices and payments

---

## 9. PRICE SCHEMES (`/price-schemes`)

- [ ] Price schemes page loads (Retail, Wholesale, Special, Government by default)
- [ ] Create custom scheme
- [ ] Edit scheme name/description → saves

---

## 10. RECEIVE PAYMENTS (`/payments`) ⚠️ Key Feature

### 10.1 Customer Selection
- [ ] Customer list shows customers with balance highlighted in red
- [ ] Search by name or phone filters list
- [ ] Click customer → invoice table loads on right

### 10.2 Invoice Display
- [ ] ⚠️ **Open invoices appear** (penalty invoices first, then interest, then regular oldest-first)
- [ ] Table shows: Date, Invoice #, Type badge, Due Date, Orig. Amount, Paid, Balance Due
- [ ] Overdue invoices show red "Xd overdue" badge
- [ ] Grace period invoices show yellow "Grace Xd" badge
- [ ] Click invoice number → Invoice Detail Modal opens

### 10.3 Payment Entry (QuickBooks Style)
- [ ] Payment header: Date, Method, Reference, Memo fields visible
- [ ] Type amount in "Enter Total Amount" → ⚠️ **per-row amounts auto-fill** (penalty rows filled first)
- [ ] "Pay All ₱X.XX" button → fills all rows for full balance
- [ ] ⚠️ **Manually edit a row amount** → Allocation Preview chips update
- [ ] "Amount to Apply" total matches sum of per-row amounts
- [ ] Click "Save & Apply Payment" → toast shows "₱X applied to N invoice(s)"
- [ ] After payment: customer balance updates, paid invoices disappear from list

### 10.4 Generate Charges
- [ ] Click "Generate Interest / Penalty Charges" → section expands
- [ ] ⚠️ **Customer with NO interest rate**: "Generate Interest" button is **disabled** (grayed out) with warning message pointing to Customers → Edit
- [ ] **Customer WITH interest rate** (set in step 8): button enabled, accrued interest preview shows
- [ ] Click "Generate Interest" → INT-XXXXXXXX-XXXX invoice created → toast with amount → appears in invoice list
- [ ] ⚠️ If interest was already generated today, clicking again shows "already computed" or no change
- [ ] Set Penalty % (e.g., 10%) → click "Apply Penalty" → PEN-XXXXXXXX-XXXX invoice created
- [ ] ⚠️ Penalty only applies to invoices OUTSIDE grace period
- [ ] Penalty cannot be applied twice to same invoice ("already penalized")

### 10.5 Payment History
- [ ] Click "History" button → dialog opens
- [ ] All past payments shown with date, invoice, method, amount, recorded by
- [ ] Total received footer shown

---

## 11. ACCOUNTING (`/accounting`) ⚠️ Branch Required

> ⚠️ **IMPORTANT**: Always select a specific branch from the sidebar before recording any expenses. "All Branches" view blocks expense creation.

### 11.1 Regular Expense
- [ ] Click "New Expense" → dialog opens
- [ ] Select category (e.g., Utilities), fill description and amount
- [ ] Save → expense appears in list, cashier wallet deducted

### 11.2 Employee Advance (CA)
- [ ] Select "Employee Advance" category → ⚠️ **Employee picker appears** (amber section)
- [ ] Select an employee from dropdown → CA summary shows (This Month, Limit, Balance)
- [ ] Enter amount below monthly limit → save → employee advance_balance increases
- [ ] Enter amount **above monthly limit** → Manager PIN dialog appears
- [ ] Enter correct PIN → expense saves with manager approval note
- [ ] ⚠️ No branch selected → error "Please select a specific branch"

### 11.3 Farm Expense
- [ ] Click "Farm Expense" → customer picker dialog
- [ ] Select customer, enter amount, due date
- [ ] Save → expense created + invoice auto-generated for the customer

### 11.4 Customer Cash Out
- [ ] Click "Customer Cash Out" → similar flow to farm expense
- [ ] Receivable created, linked to customer

### 11.5 Receivables / Payables
- [ ] Receivables tab shows outstanding customer receivables
- [ ] Record payment on receivable → balance reduces
- [ ] Payables tab shows outstanding supplier payables

---

## 12. EMPLOYEES (`/employees`)

### 12.1 Dashboard Stats
- [ ] Shows: Active Staff, Total CA Balance, Over Limit count, Total Employees

### 12.2 Employee List
- [ ] Employees show as cards with name, position, branch, hire date
- [ ] CA progress bar visible for employees with a monthly limit
- [ ] ⚠️ Over-limit employees show red bar

### 12.3 Create/Edit Employee
- [ ] Click "Add Employee" → form opens with all fields:
  - Name, Position, Employment Type
  - Branch, Phone, Hire Date
  - Monthly Salary, Daily Rate, **Monthly CA Limit**
  - SSS, PhilHealth, Pag-IBIG, TIN numbers
  - Emergency Contact Name and Phone
  - Notes
- [ ] Save → employee appears in grid with CA progress bar

### 12.4 Employee Detail
- [ ] Click employee card → modal opens
- [ ] Profile tab: all fields visible
- [ ] Cash Advances tab: shows This Month total, Monthly Limit, Unpaid Balance, progress bar
- [ ] "Previous month overage" note appears if last month was over limit
- [ ] If advance balance > 0: "Record Salary Deduction" button appears
- [ ] Record deduction → advance_balance decreases, log created

---

## 13. FUND MANAGEMENT (`/fund-management`)

- [ ] Cashier Drawer, Safe, Bank wallets shown with balances
- [ ] Deposit to Safe → safe balance increases
- [ ] Pay from Safe → safe balance decreases, lot-based tracking
- [ ] Transfer between wallets → both balances update

---

## 14. DAILY OPERATIONS (`/daily-ops`)

### 14.1 Daily Sales Log
- [ ] Sequential log shows all items sold today per branch
- [ ] Running total visible

### 14.2 Daily Profit Report
- [ ] Summary: Total Sales, Total Expenses, Net Profit
- [ ] Breakdown by category

### 14.3 Close Accounts
- [ ] Close day for current branch → day status changes to "closed"
- [ ] Cannot add more transactions for that day after closing

---

## 15. PRICE CHANGE SAVE DIALOG (Sales — Both Modes)

- [ ] Quick mode: Change price of item in cart → on blur → "Save Price Change?" dialog
- [ ] Click "No, this sale only" → price used for this sale, no DB change
- [ ] Click "Yes, update price" → product's scheme price updated in database
- [ ] Order mode: Change rate in line item → on blur → same dialog
- [ ] Dialog shows old price, new price, and scheme name badge

---

## 16. INVOICE DETAIL MODAL

- [ ] Click any invoice number → modal opens with full details
- [ ] Items, totals, payments list visible
- [ ] Edit invoice → enter reason → save → "Edited" badge appears
- [ ] Audit trail shows changes with reason

---

## 17. OFFLINE MODE (POS)

- [ ] Disconnect internet → WifiOff indicator shows on Sales page
- [ ] Add items and complete a sale → "Sale saved offline" toast
- [ ] Pending count badge increments
- [ ] Reconnect internet → auto-sync → pending count clears
- [ ] "Sync" button manually triggers sync

---

## 18. SETTINGS (`/settings`)

- [ ] Invoice prefixes configurable (SI, PO, INT, PEN, etc.)
- [ ] Payment terms options configurable

---

## KNOWN RULES / BUSINESS LOGIC TO REMEMBER

| Rule | Location |
|------|----------|
| Cannot sell below capital (cost price) | Sales checkout |
| If price scheme has no price → shows ₱0.00, blocks checkout | Sales checkout |
| Admin/Manager auto-approves credit sales (no PIN needed) | Sales checkout |
| Cashier needs manager PIN for credit sales | Sales checkout |
| Payment rule: Penalty → Interest → Invoice (oldest) | Receive Payments |
| Interest generation requires customer to have an interest rate set | Receive Payments |
| Penalty only applies once per invoice (per billing cycle) | Receive Payments |
| Employee CA over monthly limit requires manager PIN | Accounting |
| Expenses require a specific branch (not "All Branches") | Accounting |
| Repack stock is calculated from parent stock × units_per_parent | Products/Inventory |

---

## QUICK SMOKE TEST (5 minutes)

For a fast daily check:

1. **Login** as owner → Dashboard loads
2. **Sales** → Search "vit" → add product to cart → try checkout (should work if price > 0)
3. **Receive Payments** → select a customer with balance → "Pay All" → apply payment
4. **Employees** → verify employee list loads
5. **Accounts** → verify user list loads

---

*Last updated: Feb 2026 | AgriPOS v3.0*
