# AgriBooks Changelog

## Mar 12, 2026 — Close Wizard "Find & Pay" Panel Fix + Enhancement
- **Fixed 3 bugs** in CloseWizardPage.js Step 3 "Receive payment for a customer (not listed above)" panel:
  1. `overflow-hidden` CSS on container clipped the customer search dropdown
  2. Wrong API endpoint: `/invoices?status=open` → `/customers/{id}/invoices` (now includes "partial" status invoices)
  3. Field name mismatch: dialog expected `remaining_balance` but invoices have `balance`
- **Enhanced** panel into full mini-PaymentsPage:
  - Multi-invoice per-row payment allocation
  - Interest generation (uses customer's configured rate)
  - Penalty generation with configurable percentage
  - Quick total input + "Pay All" auto-apply button
  - Uses proper `/customers/{id}/receive-payment` endpoint for multi-allocation
  - Wizard data auto-refreshes after payment so AR table updates immediately
- Testing: 10/10 frontend tests passed

## Mar 11, 2026 — Critical Accounting Fixes
- Fixed `is_digital_payment` helper: "Partial" and "Split" payments no longer classified as digital
- Fixed starting float calculation for first-ever daily close
- Fixed Sales Log running totals: digital payments and split sale totals now correct
- Created and ran data migration endpoints to fix corrupted invoice + wallet balances
- Established agent communication protocol: explain before coding, ask before creating new modules

## Earlier — Various Bug Fixes
- Checkout payment type tabs fix (Split/Partial/Credit)
- Receipt upload QR code visibility
- Partial payment closing wizard decomposition
- autoComplete fix (48 instances)
- PIN verification audit (all endpoints connected)
- Quick customer picker in checkout dialog
- Digital payment separation in closing formula
