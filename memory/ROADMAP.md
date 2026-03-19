# AgriBooks — ROADMAP & Handoff

## Current Status (Mar 2026 — Fork Point)

### QR Workflow — What's Done
| Phase | Feature | Status |
|---|---|---|
| Phase 1 | Stock Reservation Model (`release_mode`, `sale_reservations`, `reserved_qty`) | ✅ Done |
| Phase 2 | QR Stock Release (`/qr-actions/{code}/release_stocks`) | ✅ Done |
| Extras | Count Sheet reserved stock fix, Pending Releases page | ✅ Done |

### What Phase 2 Built (IMPORTANT for context)
- `inventory.quantity` = available to sell. Deducted at sale time (even partial release).
- `inventory.reserved_qty` = customer's stock pending pickup. Added at partial sale. Drained at release/expiry.
- `sale_reservations` collection = per-invoice, per-product delivery tracking.
- `DocViewerPage.jsx` at `/doc/:code` — unified PIN-gated panel: history + release form + confirmation step.
- `StockReleaseManager` component inside `DocViewerPage.jsx` — this is the **UI pattern** for all future QR action panels (PIN prompt → unlock → content → confirmation → done).
- `POST /api/qr-actions/{code}/verify_pin` — validate PIN without side effects (used to unlock panels).
- Auto doc_code generated when partial-release sale is created. Returned in sale response as `doc_code`.

---

## Phase 3 — QR Payment Receive

### What it does
Staff scans an invoice QR on their phone, receives a cash or digital payment directly. Updates balance, routes to correct wallet.

### Backend: `POST /api/qr-actions/{code}/receive_payment`
Add to `/app/backend/routes/qr_actions.py`

```python
Body: { pin, amount, payment_method, fund_source, digital_platform, digital_ref_number, release_ref }

Steps:
1. _resolve_doc(code) → verify doc_type == "invoice"
2. invoice = db.invoices.find_one({"id": doc_id})
3. Validate: invoice not voided, invoice.balance > 0, amount <= invoice.balance
4. verify_pin_for_action(pin, "qr_receive_payment", branch_id=invoice.branch_id)
5. Build payment record (same schema as invoice.payments[]):
   {
     id, amount, date (today), method, fund_source,
     digital_platform, digital_ref_number,
     applied_to_principal, applied_to_interest: 0,
     recorded_by: verifier.verifier_name, recorded_at
   }
6. Update invoice: $inc amount_paid, recalc balance, update status (partial→paid if balance=0)
7. Route to wallet:
   - fund_source="cashier" → update_cashier_wallet(branch_id, +amount, ref)
   - fund_source="digital" → update_digital_wallet(branch_id, amount, ...)
8. If invoice.customer_id and balance was reduced: db.customers.update_one $inc balance: -amount_received
9. _log_action(doc_ref, "receive_payment", verifier, f"₱{amount} {payment_method}")
10. Return { success, new_balance, new_status, payment_record }
```

**Integration points:**
- `update_cashier_wallet`, `update_digital_wallet`, `is_digital_payment` already in `utils.py`
- Payment record schema matches `invoices.payments[]` exactly — Z-report AR section picks it up automatically
- Customer balance: same `$inc {balance: -amount}` pattern used everywhere

### Frontend: `DocViewerPage.jsx`
- `available_actions` already includes `receive_payment` when balance > 0 (done in `/doc/view/{code}`)
- Add a `ReceivePaymentPanel` component (same structure as `StockReleaseManager`):
  - Locked state: "Receive Payment · Balance ₱X" button
  - PIN prompt (same as release)
  - Unlocked: payment form (amount input, method selector: Cash/GCash/Maya, fund source)
  - Confirmation step: "Confirm ₱500 Cash payment?"
  - Done: "Payment recorded · New balance: ₱X"
- Two separate PIN-gated sections can coexist on the page (release + payment)

### PIN policy
`qr_receive_payment` already defined. Defaults: `[admin_pin, manager_pin, admin_totp]`

---

## Phase 4 — PO Receive via QR

### What it does
Warehouse staff scans a PO QR, enters actual received quantities, confirms with PIN. System calls the existing terminal-finalize logic. Already-received POs are view-only.

### Backend: `POST /api/qr-actions/{code}/po_receive`
Add to `/app/backend/routes/qr_actions.py`

```python
Body: { pin, items: [{product_id, qty_received}], notes, release_ref }

Steps:
1. _resolve_doc(code) → doc_type == "purchase_order"
2. po = db.purchase_orders.find_one({"id": doc_id})
3. If po.status == "received": raise 400 "PO already received — view only"
4. If po.status not in ("ordered", "draft", "in_progress"): raise 400
5. verify_pin_for_action(pin, "qr_po_receive", branch_id=po.branch_id)
6. Call existing terminal_finalize_po logic (in purchase_orders.py) directly:
   - Build updated items with qty_received
   - Calculate variances
   - Set status = "ordered" (unlocked for PC to finalize with capital choices)
   OR call _apply_po_inventory directly if you want full receive without PC step
7. _log_action(...)
8. Return { success, variances, status }
```

**Recommended mode:** Use "terminal-finalize" approach (status → "ordered") so PC still reviews capital choices before finalizing. Safer.

**Key function to reuse:** `terminal_finalize_po()` in `purchase_orders.py` (line ~1005). Extract the core logic into a shared helper.

### Frontend: `DocViewerPage.jsx`
- `available_actions` includes `po_receive` when `raw_status` in ("Draft", "Ordered", "In Progress")
- Add `POReceivePanel` component:
  - Locked: "Receive This PO" button
  - PIN unlock
  - Table: Product | Ordered Qty | Actual Received (input) | Variance (live)
  - Variance color: green=match, red=shortage, amber=excess
  - Confirmation step: shows variance summary
  - Done: "PO verified — pending PC confirmation"

### Updates needed in `/doc/view/{code}`
`available_actions` already returns `po_receive` for correct statuses (done in doc_lookup.py). Add `po.items` to the open view response so the receive form can pre-populate expected quantities.

---

## Phase 5 — Transfer QR Receive

### What it does
Receiving branch scans the transfer QR, enters actual quantities. If match → inventory moves. If variance → enters `received_pending` for source to accept/dispute (existing flow).

### Backend: `POST /api/qr-actions/{code}/transfer_receive`
Add to `/app/backend/routes/qr_actions.py`

```python
Body: { pin, items: [{product_id, qty_received}], notes, release_ref }

Steps:
1. _resolve_doc(code) → doc_type == "branch_transfer"
2. transfer = db.branch_transfer_orders.find_one({"id": doc_id})
3. If transfer.status != "sent": raise 400
4. verify_pin_for_action(pin, "qr_transfer_receive", branch_id=transfer.to_branch_id)
   (Receiver's branch PIN — the branch accepting the goods)
5. Call receive_transfer(transfer_id, {items, notes, skip_receipt_check: True}, user)
   — This existing function handles EVERYTHING:
     exact match → _apply_receipt() → inventory moves, status "received"
     variance → status "received_pending", source notified
6. _log_action(...)
7. Return result from receive_transfer
```

**This is almost purely delegation.** The `receive_transfer()` function in `branch_transfers.py` handles:
- Inventory movement on exact match
- `received_pending` on variance
- Notifications to source branch
- Shortages/excesses calculation

### Frontend: `DocViewerPage.jsx`
- `available_actions` includes `transfer_receive` when `raw_status == "sent"` (done)
- Add `TransferReceivePanel` component — same pattern as POReceivePanel
- Items come from `basic.items` (already in doc view response)
- Show: Product | Sent Qty | Received (input) | Variance (live)
- After submit: show result (received / pending confirmation)

---

## Phase 6 — Terminal Doc Code Entry

### What it does
Cashier on terminal can type a doc code (e.g., `K7EFPTZQ`) to open any document's action page without scanning a QR.

### What to build
- Add "Find by Code" option in `TerminalShell.jsx` quick action area OR in terminal header
- Simple input → `navigate('/doc/${code.toUpperCase()}')`
- The `/doc/:code` page already works on terminal (standard React route, no terminal-specific code needed)

---

## Other Backlog (Non-QR)

### P0 — Permission Enforcement Phase 2 (NEXT)
Wire up all remaining dead permission toggles. Detailed spec in PRD.md.
1. `products.view_cost` — hide cost/capital in Sales + Products when OFF
2. `customers.view_balance` — hide AR balance info when OFF
3. `customers.manage_credit` — gate credit limit editing separately
4. `reports.export` — hide print/export buttons when OFF
5. `reports.view_profit` — **NEW: build Profit Report** (revenue - capital, margin %) and gate behind this permission
6. `accounting.generate_interest/penalty` — remap to proper permission keys

### P1 — User Verification Pending
Phase 3 incident resolution (PIN auth + auto-journal entries) was completed but user never confirmed. Ask user to verify before proceeding.

### P2 — Visual Trail for Partial Invoices
Show linked payment transactions for a single invoice. Which payments went toward which invoice, timeline view.

### P2 — Smart Journal Entries for Forgotten Sales
Allow back-dating a sale to a closed day with proper inventory/financial corrections.

### P2 — Admin Tool for Broken POs
Production DB has corrupted `purchase_orders` documents. Build a secure admin page to list and fix them.

### P2 — Refactor `SuperAdminPage.jsx`
1000+ line monolithic component. Break into smaller modules.

### P3 — Cross-Branch Payment Wallet Routing ⚠️ DEFERRED BY USER
When a customer pays at Branch B for an invoice from Branch A (cross-branch payment via QR), the current system records cash into Branch A's wallet (the invoice's branch). The correct behavior is:
- Cash received at Branch B → goes into Branch B's cashier wallet
- An inter-branch settlement entry is created (Branch B owes Branch A the amount)
- Journal entry: `Debit: Branch B Cash | Credit: Inter-Branch Payable to Branch A`
- The audit trail already captures the cross-branch event via TOTP verification
- **Note:** This is a financial correctness improvement. Currently, the cross-branch TOTP gate and audit are in place. Wallet routing fix is the next step.
- **User instruction:** "remember this for now, we will get back to it"

### P3 — Weight-Embedded EAN-13 Barcodes
Decode price/weight from standard grocery weight barcodes.

---

## Key Architecture Files

| File | Purpose |
|---|---|
| `backend/routes/qr_actions.py` | All QR actions live here. Add Phase 3/4/5 endpoints here. |
| `backend/routes/doc_lookup.py` | `/doc/view/{code}` — `available_actions[]` computed here. Add po.items to PO response. |
| `backend/routes/purchase_orders.py` | `terminal_finalize_po()` reused by Phase 4 |
| `backend/routes/branch_transfers.py` | `receive_transfer()` reused by Phase 5 |
| `backend/routes/invoices.py` | Payment schema reference for Phase 3 |
| `backend/routes/verify.py` | `verify_pin_for_action()`, `_resolve_pin()` — PIN system |
| `backend/routes/stock_releases.py` | Pending releases list/summary endpoints |
| `frontend/src/pages/DocViewerPage.jsx` | ALL QR action UI. `StockReleaseManager` = pattern to follow. |
| `frontend/src/pages/PendingReleasesPage.jsx` | Tracking page for unreleased stock |
| `frontend/src/pages/CountSheetsPage.js` | Shows `system_reserved_qty` breakdown |

---

## DB Collections Added (New Agent Must Know)

| Collection | Purpose |
|---|---|
| `sale_reservations` | Per-invoice, per-product delivery tracking. `qty_remaining` drained by release/expiry. |
| `qr_action_log` | Immutable audit trail for every QR-triggered action. |

## Inventory Model (Critical)

```
inventory.quantity     = available to sell (deducted at sale time, always)
inventory.reserved_qty = customer's stock pending pickup (drained by release/expiry)
Physical on shelf      = quantity + reserved_qty

At partial sale creation:
  quantity    -= qty_sold
  reserved_qty += qty_sold

At stock release via QR:
  reserved_qty -= qty_released
  (quantity unchanged — already moved at sale time)

At 30-day expiry:
  quantity     += qty_remaining_in_reservation
  reserved_qty -= qty_remaining_in_reservation
  Movement: "expiry_return"

At void of partial-release invoice:
  quantity     += reserved_qty (only unreleased portion)
  reserved_qty -= reserved_qty
  Reservations deleted from sale_reservations
```

---

## Credentials

- **Super Admin:** `janmarkeahig@gmail.com` / `Aa@58798546521325`
- **Manager PIN:** `521325`
- **App URL:** `https://sales-date-sync.preview.emergentagent.com`
- **DB:** MongoDB `test_database` at `localhost:27017`
