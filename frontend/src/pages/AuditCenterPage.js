import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  ShieldCheck, RefreshCw, AlertTriangle, Check, X, ChevronDown, ChevronUp,
  Printer, History, Plus, Package, Banknote, TrendingUp, Users, ArrowRight,
  RotateCcw, FileText, Clock, Building2, Download, ShieldAlert, Smartphone,
  KeyRound, Eye
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// ─────────────────────────────────────────────────────────────────────────────
//  Severity helpers
// ─────────────────────────────────────────────────────────────────────────────
const SEV_COLORS = {
  ok: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  warning: 'text-amber-700 bg-amber-50 border-amber-200',
  critical: 'text-red-700 bg-red-50 border-red-200',
};
const SEV_ICONS = {
  ok: <Check size={16} className="text-emerald-600" />,
  warning: <AlertTriangle size={16} className="text-amber-600" />,
  critical: <AlertTriangle size={16} className="text-red-600" />,
};
const SEV_LABELS = { ok: 'Good', warning: 'Needs Review', critical: 'Critical' };
const SEV_BADGE = {
  ok: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
};

function SevBadge({ sev }) {
  return <Badge className={`text-[10px] ${SEV_BADGE[sev] || SEV_BADGE.ok}`}>{SEV_LABELS[sev] || '—'}</Badge>;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Insight Engine — comprehensive rule-based explanations, no AI needed.
//  Context: Philippine agricultural supply multi-branch retail.
// ─────────────────────────────────────────────────────────────────────────────
function getInsight(key, data) {
  if (!data) return null;
  const php = (n) => '₱' + Math.abs(parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });
  const pct = (a, b) => b > 0 ? ((Math.abs(a) / b) * 100).toFixed(1) + '%' : '—';

  switch (key) {

    // ── CASH ────────────────────────────────────────────────────────────────
    case 'cash': {
      const disc = parseFloat(data.discrepancy) || 0;
      const expected = parseFloat(data.expected_cash) || 0;
      const cashier = parseFloat(data.current_cashier_balance) || 0;
      const expenses = parseFloat(data.total_expenses) || 0;
      const cashSales = parseFloat(data.cash_sales) || 0;
      const arCollected = parseFloat(data.ar_collected) || 0;
      const discPct = pct(disc, expected);

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `Cash is balanced. Cashier has ${php(cashier)} which closely matches the expected ${php(expected)}. No significant discrepancy detected.`,
      };

      if (disc < 0) {
        // Short — less cash than expected
        const shortfall = Math.abs(disc);
        return {
          type: data.severity,
          text: `Cash is SHORT by ${php(shortfall)} (${discPct} of expected ${php(expected)}). The cashier drawer has ${php(cashier)} but the formula says it should have ${php(expected)}.`,
          causes: [
            `Expenses of ${php(expenses)} were recorded this period — verify each one had an official receipt and was authorized. Look for cash paid outside the system`,
            'GCash/Maya collections: customer paid digitally but the sale was marked as "walk-in cash" — the money went to your e-wallet, not the drawer',
            'A supplier was paid in cash but it was NOT recorded as a PO payment or expense in the system — common when staff pay drivers directly',
            'Employee cash advance given informally from the drawer without creating an advance record',
            `Opening float issue: the starting float used in the formula (₱${data.starting_float?.toLocaleString?.() ?? 0}) may be wrong if yesterday's close was not properly completed`,
            'Change given incorrectly — cashier gave too much change to a customer (overpaid change)',
            'Void-and-pocket scheme: a sale was voided after the customer paid cash but the cash was not returned to the drawer',
            'Petty cash used for minor purchases (snacks, supplies) without recording the expense',
            'Cashier used own money earlier and already took it back ("resibo" issue — self-reimbursement without recording)',
            arCollected > 0 && `AR collections of ${php(arCollected)} were recorded — confirm these were deposited to the right fund and not taken home`,
          ].filter(Boolean),
          action: `First, physically count the entire drawer (all bills and coins). Enter the actual count in the field above. If the shortfall is consistently between ₱100–500, it may be change errors. If >₱1,000, trace each expense and GCash/Maya transaction for the period.`,
        };
      }

      // Over — more cash than expected
      const excess = Math.abs(disc);
      return {
        type: 'warning',
        text: `Cash is OVER by ${php(excess)}. There is ${php(cashier)} in the drawer but only ${php(expected)} was expected. Extra cash needs explanation — it could be a good sign (unrecorded sales) or an error.`,
        causes: [
          'Customer paid in cash but the sale was recorded as GCash/Maya — digital payment marker was wrong, actual cash went to drawer',
          'Customer advance or deposit received but not entered in the system as a customer receivable',
          'A previous short was "covered" by a staff member with their own money (common in Filipino businesses to avoid being caught short)',
          'Old cash from a previous period was mixed into today\'s float',
          'Safe replenishment to cashier was done but not recorded as a transfer',
          'Customer overpaid and the extra was retained instead of being refunded',
        ],
        action: `Trace the source of the extra ${php(excess)}. Check if there are any unrecorded customer deposits or informal cash-ins. If unresolved, it should be recorded as a liability (customer deposit) or flagged for investigation.`,
      };
    }

    // ── SALES ───────────────────────────────────────────────────────────────
    case 'sales': {
      const voided = data.voided_count || 0;
      const edited = data.edited_count || 0;
      const total = parseFloat(data.grand_total_sales) || 0;
      const txns = data.total_transactions || 0;
      const avgTxn = txns > 0 ? total / txns : 0;

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `Sales records are clean — ${txns} transactions totaling ${php(total)}. No voided or edited transactions found. Average transaction: ${php(avgTxn)}.`,
      };

      const parts = [];
      if (voided > 0) parts.push(`${voided} voided transaction${voided > 1 ? 's' : ''}`);
      if (edited > 0) parts.push(`${edited} edited invoice${edited > 1 ? 's' : ''}`);
      return {
        type: 'warning',
        text: `${parts.join(' and ')} found this period (out of ${txns} total transactions). This does not automatically mean fraud — but each one should have a documented reason.`,
        causes: [
          voided > 0 && 'VOIDS — Legitimate reasons: item was out of stock after encoding, customer changed mind, duplicate entry. Red flag: multiple voids by same cashier at end of shift, or voids shortly before or after a large cash payment',
          voided > 0 && '"Tapping" scheme risk: cashier records a sale, customer pays cash, cashier voids the transaction and pockets the cash. Most common with walk-in cash customers who do not ask for receipts',
          voided > 0 && 'New cashier errors: high void rate in first few weeks is normal for training — check if voids cluster around one user',
          edited > 0 && 'EDITS — Legitimate: wrong product entered, quantity corrected, pricing scheme changed. Red flag: price reduced significantly without discount authorization',
          edited > 0 && 'Price downward edits: could mean the cashier gave a special price to a friend/relative (suki discount) without manager approval',
          edited > 0 && 'Quantity edits upward after posting: could indicate adding products that were given but not charged (gift or commission scheme)',
          `Average transaction is ${php(avgTxn)} — if any individual transaction is 5–10× this amount, verify it was a legitimate bulk order`,
        ].filter(Boolean),
        action: `Review the edited invoices list below — check WHO made the edit and WHAT changed (price, quantity, or product). For voids, match each void to the cashier and time of day. Flag any void+same-product re-entry pattern (possible duplicate-then-void scheme).`,
      };
    }

    // ── AR ──────────────────────────────────────────────────────────────────
    case 'ar': {
      const total = parseFloat(data.total_outstanding_ar) || 0;
      const over90 = parseFloat(data.aging?.b90plus) || 0;
      const d61_90 = parseFloat(data.aging?.b61_90) || 0;
      const d31_60 = parseFloat(data.aging?.b31_60) || 0;
      const current = parseFloat(data.aging?.current) || 0;
      const collected = parseFloat(data.collected_in_period) || 0;
      const openInv = data.open_invoices_count || 0;
      const collRate = total > 0 ? ((collected / (collected + total)) * 100).toFixed(0) : 100;

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `AR is healthy — all ${php(total)} outstanding is within 30 days. Collection rate this period: ${collRate}%. Customers are paying on time.`,
      };

      if (data.severity === 'critical') return {
        type: 'critical',
        text: `${php(over90)} (${pct(over90, total)} of total AR) is MORE THAN 90 DAYS OVERDUE across ${openInv} open invoice(s). Total outstanding: ${php(total)}. Collection rate this period: ${collRate}%.`,
        causes: [
          'SEASONAL BUYERS: Farmers and agricultural cooperatives often buy on credit during planting season and pay after harvest — if your credit terms do not account for this cycle, normal seasonal accounts will appear "overdue"',
          'DISPUTED INVOICES: Customer may claim the product did not work as expected (pesticide ineffective, fertilizer damaged crops) — they are withholding payment until resolved',
          'INFORMAL CREDIT EXTENSION: A manager verbally extended payment terms to a "suki" customer but did not update the system — the system still shows the original due date',
          'CUSTOMER HARDSHIP: Small farmers or retailers may be experiencing financial difficulty, especially after a bad harvest season or typhoon',
          'MISSING STATEMENT OF ACCOUNT: Customer claims they never received the invoice or SOA — no follow-up was done at 30d and 60d marks',
          'INVOICE SENT TO WRONG CONTACT: Customer changed their buyer/accountant contact and the invoice was sent to someone who no longer handles it',
          `NO CREDIT POLICY ENFORCEMENT: Credit was approved without a clear credit limit or payment terms being signed — customer has no formal obligation date`,
          d61_90 > 0 && `An additional ${php(d61_90)} is in the 61–90 day range and will become critical soon if not collected`,
        ].filter(Boolean),
        action: `Immediately call or visit customers with 90+ day balances. For agricultural accounts: check if it aligns with harvest season timing. For disputed invoices: have a manager visit and get written acknowledgment. Consider requiring cash-on-delivery for new sales to 90+ day accounts until the balance is cleared. The ${openInv} open invoices are visible in Reports → AR Aging.`,
      };

      return {
        type: 'warning',
        text: `${php(d61_90)} is entering the danger zone (61–90 days). Total AR outstanding: ${php(total)}. Collection rate this period: ${collRate}%. If these accounts cross 90 days, they become significantly harder to collect.`,
        causes: [
          'Customer has received the goods but payment is delayed — may need a formal payment demand letter',
          'Credit terms were Net 30 but customer treats it as Net 60 informally — need to clarify and enforce',
          'No collection reminder was sent at the 30-day mark — customer was not nudged',
          d31_60 > 0 && `${php(d31_60)} is also in the 31–60 day range — the collection process should have started 2–4 weeks ago`,
          'Agricultural cycle: if customer is a farmer, they may be in a lean period between planting and harvest',
        ].filter(Boolean),
        action: `Send formal Statements of Account to all customers with 31+ day balances today. For 61–90 day accounts, follow up by phone/visit and get a firm payment commitment date. Note the commitment in the customer record.`,
      };
    }

    // ── PAYABLES ────────────────────────────────────────────────────────────
    case 'payables': {
      const overdue = data.overdue_count || 0;
      const overdueVal = parseFloat(data.overdue_value) || 0;
      const total = parseFloat(data.total_outstanding_ap) || 0;
      const unpaidCount = data.unpaid_po_count || 0;

      if (data.severity === 'ok') {
        if (total === 0) return { type: 'ok', text: 'No outstanding payables. All supplier POs have been fully paid. Good supplier payment health.' };
        return { type: 'ok', text: `${php(total)} owed to ${unpaidCount} supplier PO(s) — all within agreed payment terms. No overdue amounts.` };
      }
      return {
        type: 'critical',
        text: `${overdue} PO${overdue > 1 ? 's' : ''} worth ${php(overdueVal)} are PAST THEIR DUE DATE (out of ${php(total)} total payable to ${unpaidCount} PO${unpaidCount > 1 ? 's' : ''}).`,
        causes: [
          'CASH FLOW TIMING: Purchases were received and inventory was used for sales, but the collections from those sales have not yet come in — classic working capital gap',
          'POST-DATED CHECKS (PDC): A check was issued to the supplier but it has not yet been presented — if the due date has passed and the check hasn\'t cleared, the liability is still open in your records',
          'PAYMENT OUTSIDE SYSTEM: Payment was made directly to the supplier (cash, bank transfer) but was NOT recorded in AgriBooks using "Pay Supplier" — the system still shows it as unpaid',
          'WRONG PO LINKED: Payment was allocated to a different PO for the same supplier — check if there is a matching paid PO with a similar amount',
          'SUPPLIER CREDIT TERMS CHANGED: Supplier extended credit verbally but the system uses the original terms — the PO shows overdue but the supplier agreed to wait',
          'FORGOT TO PAY: The PO was received quietly ("Receive on Terms") and the payment follow-up was not tracked — common for smaller/regular supplier orders',
          overdue > 1 && 'Multiple overdue POs to the same supplier is especially risky — supplier may stop extending credit or demand COD for future deliveries',
        ].filter(Boolean),
        action: `Go to Pay Supplier → select the overdue supplier(s) → pay now. If payment was already made outside the system, record it using Pay Supplier so the balance clears. Check your Safe and Cashier balances (Safe: ${php(data.safe_balance || 0)} | Cashier: ${php(data.cashier_balance || 0)}) before paying.`,
      };
    }

    // ── TRANSFERS ───────────────────────────────────────────────────────────
    case 'transfers': {
      const shortage = data.with_shortage || 0;
      const excess = data.with_excess || 0;
      const pending = data.pending_count || 0;
      const requests = data.pending_requests || 0;
      const shortVal = parseFloat(data.total_shortage_value) || 0;
      const totalTxfr = data.total_transfers || 0;

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `All ${totalTxfr} transfer${totalTxfr !== 1 ? 's' : ''} completed cleanly — no shortages, no pending issues. Good inter-branch inventory accuracy.`,
      };

      const flags = [];
      if (shortage > 0) flags.push(`${shortage} shortage${shortage > 1 ? 's' : ''} (${php(shortVal)} missing)`);
      if (excess > 0) flags.push(`${excess} excess receipt${excess > 1 ? 's' : ''}`);
      if (pending > 0) flags.push(`${pending} pending confirmation`);
      if (requests > 0) flags.push(`${requests} unfulfilled stock request${requests > 1 ? 's' : ''}`);

      return {
        type: data.severity,
        text: `${flags.join('; ')} found across ${totalTxfr} transfer${totalTxfr !== 1 ? 's' : ''} this period.`,
        causes: [
          shortage > 0 && 'PACKING ERROR (most common): Source branch miscounted boxes or sacks — especially common with heavy/bulk items like 50kg fertilizer bags, boxes of 24 units, etc. A case of 24 might be counted as 1 instead of 24',
          shortage > 0 && 'TRANSIT REMOVAL: Driver or delivery person removed items from the shipment before delivery — more likely with high-value items (veterinary drugs, specialized chemicals)',
          shortage > 0 && 'RECEIVING COUNT ERROR: Destination branch counted quickly without verifying exact quantities — especially during busy periods',
          shortage > 0 && 'UNIT CONFUSION: Transfer was encoded in boxes but received was counted in pieces, or vice versa — parent vs. repack unit mismatch',
          shortage > 0 && 'ITEMS REJECTED AT DESTINATION: Some items were visibly damaged, expired, or wrong product — receiver excluded them from the count without flagging it as a formal shortage',
          excess > 0 && 'PACKING OVER-COUNT: Source branch accidentally packed more than the order — happens with loose items (packets, sachets)',
          excess > 0 && 'RECEIVING COUNT ERROR: Destination branch counted more than what was actually in the shipment',
          pending > 0 && `${pending} transfer${pending > 1 ? 's' : ''} are still waiting for the receiving branch to Accept or Dispute — inventory is in limbo until confirmed`,
          requests > 0 && `${requests} branch stock request${requests > 1 ? 's' : ''} have been sent but no Branch Transfer was generated yet — the requesting branch is waiting for stock`,
        ].filter(Boolean),
        action: shortage > 0
          ? `For each shortage: go to Branch Transfers → find orders with "Shortage" or "Pending" badge → the source branch must Accept (deducting the missing qty from source) or Dispute (asking receiving branch to recount). For transit removal suspicion, compare the signature on the delivery receipt with the actual delivery person.`
          : `Go to Branch Transfers → check pending confirmations and unfulfilled requests. Branches waiting for stock may be losing sales in the meantime.`,
      };
    }

    // ── RETURNS ─────────────────────────────────────────────────────────────
    case 'returns': {
      const pullouts = data.pullout_count || 0;
      const lossVal = parseFloat(data.total_loss_value) || 0;
      const refunded = parseFloat(data.total_refunded) || 0;
      const totalRet = data.total_returns || 0;
      const topReason = data.top_reasons?.[0]?.reason || '';

      if (data.severity === 'ok') {
        if (totalRet === 0) return { type: 'ok', text: 'No customer returns this period. Either product quality is high or return requests were handled informally — make sure all returns go through the system for proper tracking.' };
        return { type: 'ok', text: `${totalRet} return${totalRet !== 1 ? 's' : ''} processed — ${php(refunded)} refunded to customers. All items went back to shelf. No inventory losses from returns this period.` };
      }
      return {
        type: 'warning',
        text: `${pullouts} return${pullouts !== 1 ? 's' : ''} resulted in STOCK PULL-OUT — ${php(lossVal)} worth of products were removed from inventory and cannot be resold. ${php(refunded)} was refunded to customers.`,
        causes: [
          pullouts > 0 && `VETERINARY POLICY: Any returned veterinary product is automatically pulled out — you cannot resell opened or returned vet supplies (medicine, vaccines, supplements) due to integrity concerns`,
          pullouts > 0 && `EXPIRED PRODUCTS RETURNED: Customer returned an expired product — this means it was sold near or at expiry. Review receiving procedures: were these products already close to expiry when they arrived via PO?`,
          pullouts > 0 && `PRODUCT DID NOT WORK: Pesticide or fertilizer did not perform as expected — customer claims they applied correctly. This is common in agricultural products and may be a batch/storage issue`,
          pullouts > 0 && `DAMAGED PACKAGING: Product was returned with damaged packaging — if the seal is broken or contents are compromised, it cannot go back to shelf`,
          pullouts > 0 && `CONTAMINATION RISK: Some agricultural chemicals cannot be resold once returned due to potential contamination (customer may have mixed with other substances)`,
          topReason && `Your most common return reason is "${topReason}" — if this appears repeatedly, investigate whether it's a product quality issue, a training issue (wrong product recommended to customer), or a supplier problem`,
          lossVal > 5000 && `The ${php(lossVal)} in pull-out losses is significant. If the products were received close to expiry, you may be able to file a claim with the supplier`,
        ].filter(Boolean),
        action: `Pull-out losses of ${php(lossVal)} are already recorded in your expenses and will appear in today's Z-Report. Owner was notified. To reduce future pull-out losses: (1) Check PO receiving dates vs. expiry on high-risk products, (2) Train cashiers on recommending the right products, (3) For high-return suppliers, raise the issue when reordering.`,
      };
    }

    // ── ACTIVITY ────────────────────────────────────────────────────────────
    case 'activity': {
      const corrections = data.inventory_corrections_count || 0;
      const edits = data.invoice_edits_count || 0;
      const offhours = data.off_hours_count || 0;
      const users = data.sales_by_user || [];
      const topUser = users[0];
      const bottomUser = users.length > 1 ? users[users.length - 1] : null;

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `No unusual activity detected. ${corrections === 0 ? 'No inventory corrections' : ''}, no invoice edits, no off-hours transactions. User activity appears normal.`,
      };

      const flags = [];
      if (corrections > 0) flags.push(`${corrections} inventory correction${corrections > 1 ? 's' : ''}`);
      if (edits > 0) flags.push(`${edits} invoice edit${edits > 1 ? 's' : ''}`);
      if (offhours > 0) flags.push(`${offhours} off-hours transaction${offhours > 1 ? 's' : ''}`);

      return {
        type: data.severity,
        text: `${flags.join(', ')} detected this period. These are sensitive actions that change the financial record — each one deserves a review.`,
        causes: [
          corrections > 0 && `INVENTORY CORRECTIONS (${corrections}): These directly change stock levels without going through a purchase or sale. Legitimate reasons: physical damage (water/flood damage, rodent infestation — common in Philippine warehouses), expiry disposal, counting corrections after count sheet. Red flag: large corrections by non-admin users or corrections that conveniently offset a shortage`,
          corrections > 0 && 'Corrections made AFTER a count sheet was completed are especially suspicious — they may be adjusting numbers to match the count sheet instead of investigating the actual discrepancy',
          edits > 0 && `INVOICE EDITS (${edits}): Post-sale changes to price, quantity, or items. Legitimate: encoding error, wrong product selected. Red flag: price reductions without discount approval, quantity reductions after payment, or same item removed and re-added at different price`,
          edits > 0 && 'Check if edits always happen for the same customer (suki favoritism) or same cashier (unauthorized discounting)',
          offhours > 0 && `OFF-HOURS TRANSACTIONS (${offhours} before 7am or after 10pm): Could be legitimate — manager processing a late delivery, pre-opening price updates, or previous day\'s catch-up entries. Red flag: cash sales processed after hours when no customer would be present`,
          offhours > 0 && 'Check if the off-hours cashier name matches someone who was supposed to be on duty at that time. If credentials are shared, you may not be able to trace it to one person',
          topUser && bottomUser && `Sales distribution: ${topUser.user} processed ${topUser.count} transactions (${php(topUser.total)}), while ${bottomUser.user} processed only ${bottomUser.count} (${php(bottomUser.total)}). Large differences may be normal (different shifts) or worth investigating`,
        ].filter(Boolean),
        action: `Start with the off-hours transactions — these are the highest risk. Review each one: Was this entered by someone who should have been working? For inventory corrections, ask the person who made them to show documentation (damaged goods photo, expiry date photo). For invoice edits, compare the before/after amounts using the edit history below.`,
      };
    }

    // ── INVENTORY ───────────────────────────────────────────────────────────
    case 'inventory': {
      const accuracy = data.summary?.inventory_accuracy_pct;
      const criticals = data.summary?.items_critical || 0;
      const warnings = data.summary?.items_warning || 0;
      const varianceVal = parseFloat(data.summary?.total_variance_capital) || 0;
      const totalProds = data.summary?.total_products || 0;

      if (data.severity === 'ok') return {
        type: 'ok',
        text: `Excellent inventory accuracy — ${accuracy}% of ${totalProds} products counted within 1% of expected. The movement formulas (PO receipts + transfers in − sales − transfers out) closely match your physical count.`,
      };

      if (data.severity === 'critical') return {
        type: 'critical',
        text: `Inventory accuracy is ${accuracy}% — ${criticals} product${criticals !== 1 ? 's' : ''} have >5% variance from expected. Total capital impact: ${php(varianceVal)}. This is based on formula: Baseline Count + All Movements = Expected, then compared to Physical Count.`,
        causes: [
          'UNRECORDED OFF-SYSTEM SALES: Products were sold (cash) without being entered into AgriBooks — particularly common for small/frequent items like sachets, small packs, loose items',
          'RECEIVING COUNT ERROR: When PO was received, quantity was entered incorrectly — e.g., a box of 24 was counted as 1 instead of 24, overstating system inventory',
          'REPACK CONFUSION: Parent product stock was reduced to create repacks, but the repack creation was not recorded — parent shows shortage, repack shows excess',
          'PRODUCT DAMAGE/EXPIRY: Products deteriorated in storage (humidity, pests, flooding) and were disposed of without logging a correction — storage loss is not captured',
          'COUNTING ERROR IN THIS COUNT SHEET: The auditor may have miscounted — especially for products stored in multiple locations, or products with similar packaging',
          'UNIT OF MEASURE MISMATCH: System tracks in "Box" but physical count was done in "Pieces" — one box of 24 pieces counted as 1 (system) vs 24 (physical) creates a false 23-unit variance',
          'BRANCH TRANSFER NOT FULLY RECEIVED: Some transfer items were received and added to inventory but the receiving record was incomplete or still "pending"',
          'THEFT OF HIGH-VALUE ITEMS: Veterinary medicines, specialized pesticides, and tools are higher-value targets — check if the most discrepant items are in these categories',
          criticals > 5 && 'Multiple critical variances across different categories suggest a systemic issue (counting methodology) rather than individual product problems',
        ].filter(Boolean),
        action: `Focus on the ${criticals} Critical items in the table below. For each one: (1) Check the last PO receipt to verify the quantity was entered correctly, (2) Check if there was a repack/branch transfer involving this product, (3) If unexplained, do a fresh physical recount before making a correction. Document everything before logging an inventory correction in Products.`,
      };

      return {
        type: 'warning',
        text: `Inventory accuracy is ${accuracy}% — ${warnings} product${warnings !== 1 ? 's' : ''} have 1–5% variance from expected. Capital impact: ${php(varianceVal)}. Within acceptable range but worth investigating for recurring patterns.`,
        causes: [
          'Normal shrinkage: small variance expected in any physical business — handling damage, measurement tolerance, loose items',
          'Minor counting differences: physical count done quickly without recounting — a second count on flagged items often resolves small variances',
          'Weight/measure drift: products sold by weight (kg) may have small differences due to scale calibration',
          'Partial uses: open bags or sacks (fertilizer, feed) where exact partial quantity is hard to count precisely',
        ],
        action: `These 1–5% variances are acceptable for now. Document them as "known variance" in the count sheet notes. If the same products show variance in the next audit, investigate further — recurring variance on the same product often points to a systemic issue.`,
      };
    }

    default:
      return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Insight Box — renders contextual explanation for a section
// ─────────────────────────────────────────────────────────────────────────────
function InsightBox({ insight }) {
  if (!insight) return null;
  const bg = insight.type === 'ok'
    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
    : insight.type === 'critical'
    ? 'bg-red-50 border-red-200 text-red-800'
    : 'bg-amber-50 border-amber-200 text-amber-800';
  const icon = insight.type === 'ok'
    ? <Check size={13} className="text-emerald-600 shrink-0 mt-0.5" />
    : <AlertTriangle size={13} className={`shrink-0 mt-0.5 ${insight.type === 'critical' ? 'text-red-600' : 'text-amber-600'}`} />;

  return (
    <div className={`rounded-lg border p-3 mb-3 ${bg}`}>
      <div className="flex gap-2">
        {icon}
        <div className="space-y-1.5 flex-1">
          <p className="text-xs font-semibold leading-snug">{insight.text}</p>
          {insight.causes?.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold opacity-70 uppercase tracking-wide mb-0.5">Possible reasons:</p>
              <ul className="space-y-0.5">
                {insight.causes.map((c, i) => (
                  <li key={i} className="text-[11px] flex gap-1.5">
                    <span className="opacity-50 shrink-0">•</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {insight.action && (
            <div className="mt-1.5 pt-1.5 border-t border-current/10">
              <p className="text-[11px]">
                <span className="font-semibold">What to do: </span>
                {insight.action}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Section Card
// ─────────────────────────────────────────────────────────────────────────────
function SectionCard({ icon, title, sev, children, defaultOpen = false, data_testid, insight }) {
  const [open, setOpen] = useState(defaultOpen || sev === 'critical');
  return (
    <Card className={`border-2 ${sev ? SEV_COLORS[sev] : 'border-slate-200'} transition-all`} data-testid={data_testid}>
      <button className="w-full flex items-center justify-between p-4 text-left" onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${sev === 'critical' ? 'bg-red-100' : sev === 'warning' ? 'bg-amber-100' : 'bg-emerald-100'}`}>
            {icon}
          </div>
          <div>
            <p className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'Manrope' }}>{title}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sev && <SevBadge sev={sev} />}
          {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>
      {open && (
        <CardContent className="px-4 pb-4 pt-0 border-t border-current/10">
          <InsightBox insight={insight} />
          {children}
        </CardContent>
      )}
    </Card>
  );
}

function StatRow({ label, value, highlight, sub }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-600">{label}</span>
      <div className="text-right">
        <span className={`font-mono text-sm font-semibold ${highlight || ''}`}>{value}</span>
        {sub && <p className="text-[10px] text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Main Audit Center Page
// ─────────────────────────────────────────────────────────────────────────────
export default function AuditCenterPage() {
  const { currentBranch, branches, user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10);

  const [tab, setTab] = useState('run');
  const [sessions, setSessions] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // ── New Audit setup ──────────────────────────────────────────────────────
  const [auditType, setAuditType] = useState('partial');
  const [auditBranchId, setAuditBranchId] = useState(currentBranch?.id || '');
  const [periodFrom, setPeriodFrom] = useState(firstOfMonth);
  const [periodTo, setPeriodTo] = useState(today);

  // ── Computed audit data ────────────────────────────────────────────────
  const [auditData, setAuditData] = useState(null);
  const [computing, setComputing] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  // ── Cash actual count entry ────────────────────────────────────────────
  const [actualCashCount, setActualCashCount] = useState('');

  // ── Prepare for Audit (offline package) ───────────────────────────────
  const [preparing, setPreparing] = useState(false);
  const [prepProgress, setPrepProgress] = useState({ step: '', pct: 0, done: false });
  const [prepStats, setPrepStats] = useState(null);

  // ── Discrepancy report ─────────────────────────────────────────────────
  const [discrepancies, setDiscrepancies] = useState([]);
  const [loadingDisc, setLoadingDisc] = useState(false);
  const [resolveDialog, setResolveDialog] = useState(null); // discrepancy entry
  const [resolveAction, setResolveAction] = useState('dismiss');
  const [resolveNote, setResolveNote] = useState('');
  const [resolveSaving, setResolveSaving] = useState(false);

  // ── Security Flags ─────────────────────────────────────────────────────
  const [securityFlags, setSecurityFlags] = useState([]);
  const [loadingFlags, setLoadingFlags] = useState(false);
  const [ackDialog, setAckDialog] = useState(null); // event being acknowledged
  const [ackNote, setAckNote] = useState('');
  const [ackSaving, setAckSaving] = useState(false);

  useEffect(() => {
    if (currentBranch?.id) setAuditBranchId(currentBranch.id);
  }, [currentBranch?.id]);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (auditBranchId) params.set('branch_id', auditBranchId);
      const res = await api.get(`${BACKEND_URL}/api/audit/sessions?${params}`);
      setSessions(res.data.sessions || []);
    } catch { }
    setLoadingHistory(false);
  }, [auditBranchId]);

  useEffect(() => { if (tab === 'history') loadHistory(); }, [tab, loadHistory]);
  useEffect(() => { if (tab === 'discrepancies') loadDiscrepancies(); }, [tab]); // eslint-disable-line
  useEffect(() => { if (tab === 'security') loadSecurityFlags(); }, [tab, periodFrom, periodTo]); // eslint-disable-line

  const loadDiscrepancies = async () => {
    setLoadingDisc(true);
    try {
      const params = new URLSearchParams({ resolved: 'false' });
      if (auditBranchId) params.set('branch_id', auditBranchId);
      const res = await api.get(`${BACKEND_URL}/api/verify/discrepancies?${params}`);
      setDiscrepancies(res.data.discrepancies || []);
    } catch { }
    setLoadingDisc(false);
  };

  const loadSecurityFlags = async () => {
    setLoadingFlags(true);
    try {
      const params = new URLSearchParams();
      if (periodFrom) params.set('period_from', periodFrom);
      if (periodTo)   params.set('period_to',   periodTo);
      const res = await api.get(`${BACKEND_URL}/api/audit/security-flags?${params}`);
      setSecurityFlags(res.data.events || []);
    } catch { }
    setLoadingFlags(false);
  };

  const acknowledgeFlag = async () => {
    if (!ackDialog) return;
    setAckSaving(true);
    try {
      await api.post(`${BACKEND_URL}/api/audit/security-flags/${ackDialog.id}/acknowledge`, { note: ackNote });
      toast.success('Flag acknowledged and recorded');
      setAckDialog(null);
      setAckNote('');
      loadSecurityFlags();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setAckSaving(false);
  };

  const prepareForAudit = async () => {
    if (!auditBranchId) { toast.error('Select a branch first'); return; }
    setPreparing(true);
    setPrepProgress({ step: 'Fetching transaction data…', pct: 10, done: false });
    setPrepStats(null);
    try {
      const params = new URLSearchParams({ branch_id: auditBranchId });
      const res = await api.get(`${BACKEND_URL}/api/audit/offline-package?${params}`);
      const pkg = res.data;

      setPrepProgress({ step: `Caching ${pkg.totals.purchase_orders} POs, ${pkg.totals.expenses} expenses, ${pkg.totals.branch_transfers} transfers…`, pct: 40, done: false });

      // Store transaction metadata in sessionStorage for quick access
      try {
        sessionStorage.setItem(`audit_package_${auditBranchId}`, JSON.stringify({
          ...pkg,
          cached_at: new Date().toISOString(),
        }));
      } catch { /* storage full */ }

      // Pre-fetch photos (fire-and-forget, non-blocking)
      const totalFiles = pkg.file_urls?.length || 0;
      if (totalFiles > 0) {
        setPrepProgress({ step: `Preparing ${totalFiles} photos for offline access…`, pct: 60, done: false });
        let done = 0;
        const batchSize = 5;
        for (let i = 0; i < pkg.file_urls.length; i += batchSize) {
          const batch = pkg.file_urls.slice(i, i + batchSize);
          await Promise.allSettled(batch.map(f =>
            fetch(`${BACKEND_URL}/api/uploads/file/${f.record_type}/${f.record_id}/${f.file_id}`)
              .then(r => r.blob())
              .then(() => { done++; })
              .catch(() => { done++; })
          ));
          setPrepProgress({
            step: `Downloading photos (${done}/${totalFiles})…`,
            pct: 60 + Math.round((done / totalFiles) * 35),
            done: false,
          });
        }
      }

      setPrepProgress({ step: 'Audit package ready!', pct: 100, done: true });
      setPrepStats({
        period_from: pkg.period_from,
        period_to: pkg.period_to,
        auto_detected: pkg.auto_detected,
        count_sheet_refs: pkg.count_sheet_refs,
        ...pkg.totals,
        cached_at: new Date().toLocaleString(),
      });
      toast.success('Audit package prepared!');
    } catch (err) {
      toast.error('Failed to prepare audit package');
      setPrepProgress({ step: 'Failed', pct: 0, done: false });
    }
    setPreparing(false);
  };

  const resolveDiscrepancy = async () => {
    if (!resolveDialog) return;
    setResolveSaving(true);
    try {
      await api.post(`${BACKEND_URL}/api/verify/discrepancies/${resolveDialog.id}/resolve`, {
        action: resolveAction,
        justification: resolveNote,
      });
      toast.success(`Discrepancy ${resolveAction}d`);
      setResolveDialog(null);
      setResolveNote('');
      loadDiscrepancies();
    } catch { toast.error('Failed to resolve'); }
    setResolveSaving(false);
  };

  const runAudit = async () => {
    if (!auditBranchId && !isAdmin) { toast.error('Select a branch'); return; }
    setComputing(true);
    setAuditData(null);
    try {
      const params = new URLSearchParams({
        audit_type: auditType,
        period_from: periodFrom,
        period_to: periodTo,
      });
      if (auditBranchId) params.set('branch_id', auditBranchId);

      const [computeRes, sessionRes] = await Promise.all([
        api.get(`${BACKEND_URL}/api/audit/compute?${params}`),
        api.post(`${BACKEND_URL}/api/audit/sessions`, {
          audit_type: auditType,
          branch_id: auditBranchId,
          period_from: periodFrom,
          period_to: periodTo,
        }),
      ]);
      setAuditData(computeRes.data);
      setSessionId(sessionRes.data.id);
      setActualCashCount('');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Audit computation failed');
    }
    setComputing(false);
  };

  const computeOverallScore = (data) => {
    if (!data) return null;
    const sections = ['cash', 'sales', 'ar', 'payables', 'transfers', 'returns', 'activity', 'digital'];
    if (data.inventory?.available) sections.push('inventory');
    const scores = sections.map(s => {
      const sev = data[s]?.severity;
      return sev === 'ok' ? 100 : sev === 'warning' ? 60 : 20;
    });
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  };

  const finalizeAudit = async () => {
    if (!sessionId || !auditData) return;
    const score = computeOverallScore(auditData);
    try {
      await api.put(`${BACKEND_URL}/api/audit/sessions/${sessionId}`, {
        overall_score: score,
        status: 'completed',
        sections_status: {
          cash: auditData.cash?.severity,
          sales: auditData.sales?.severity,
          ar: auditData.ar?.severity,
          payables: auditData.payables?.severity,
          transfers: auditData.transfers?.severity,
          returns: auditData.returns?.severity,
          activity: auditData.activity?.severity,
          digital: auditData.digital?.severity,
          inventory: auditData.inventory?.severity,
        },
      });
      toast.success(`Audit completed! Score: ${score}/100`);
      setTab('history');
      loadHistory();
    } catch { toast.error('Failed to save audit'); }
  };

  const printAuditReport = () => {
    if (!auditData) return;
    const score = computeOverallScore(auditData);
    const branch = branches?.find(b => b.id === auditBranchId)?.name || auditBranchId;
    const win = window.open('', '_blank');
    const php = (n) => '₱' + (parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });
    const sevLabel = (s) => s === 'ok' ? '✓ Good' : s === 'warning' ? '⚠ Review' : '✗ Critical';

    win.document.write(`<html><head><title>Audit Report</title>
    <style>
      body { font-family: Arial, sans-serif; font-size: 12px; padding: 24px; }
      h1 { color: #1A4D2E; margin-bottom: 4px; }
      .meta { color: #666; margin-bottom: 20px; }
      .score { font-size: 28px; font-weight: bold; color: ${score >= 80 ? '#15803d' : score >= 50 ? '#d97706' : '#dc2626'}; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
      th { background: #1A4D2E; color: white; padding: 6px 10px; text-align: left; }
      td { padding: 5px 10px; border-bottom: 1px solid #eee; }
      .ok { color: #15803d; } .warning { color: #d97706; } .critical { color: #dc2626; }
      .section-header { background: #f1f5f9; font-weight: bold; padding: 6px 10px; margin-top: 12px; }
    </style></head><body>
    <h1>AgriBooks — Audit Report</h1>
    <div class="meta">Branch: ${branch} · Period: ${periodFrom} to ${periodTo} · Type: ${auditType} · Auditor: ${user?.username}</div>
    <div>Overall Score: <span class="score">${score}/100</span></div>
    <br/>
    <table>
      <thead><tr><th>Section</th><th>Status</th><th>Key Finding</th></tr></thead>
      <tbody>
        <tr><td>Cash/Fund Reconciliation</td><td class="${auditData.cash?.severity}">${sevLabel(auditData.cash?.severity)}</td>
            <td>Expected: ${php(auditData.cash?.expected_cash)} · Discrepancy: ${php(auditData.cash?.discrepancy)}</td></tr>
        <tr><td>Sales Audit</td><td class="${auditData.sales?.severity}">${sevLabel(auditData.sales?.severity)}</td>
            <td>Total: ${php(auditData.sales?.grand_total_sales)} · Voided: ${auditData.sales?.voided_count} · Edited: ${auditData.sales?.edited_count}</td></tr>
        <tr><td>AR/Receivables</td><td class="${auditData.ar?.severity}">${sevLabel(auditData.ar?.severity)}</td>
            <td>Outstanding: ${php(auditData.ar?.total_outstanding_ar)} · Overdue: ${auditData.ar?.aging?.b90plus > 0 ? php(auditData.ar?.aging.b90plus) + ' 90+days' : 'None'}</td></tr>
        <tr><td>Payables</td><td class="${auditData.payables?.severity}">${sevLabel(auditData.payables?.severity)}</td>
            <td>Outstanding AP: ${php(auditData.payables?.total_outstanding_ap)} · Overdue: ${auditData.payables?.overdue_count}</td></tr>
        <tr><td>Branch Transfers</td><td class="${auditData.transfers?.severity}">${sevLabel(auditData.transfers?.severity)}</td>
            <td>Shortages: ${auditData.transfers?.with_shortage} · Pending: ${auditData.transfers?.pending_count}</td></tr>
        <tr><td>Returns & Losses</td><td class="${auditData.returns?.severity}">${sevLabel(auditData.returns?.severity)}</td>
            <td>Total refunded: ${php(auditData.returns?.total_refunded)} · Loss: ${php(auditData.returns?.total_loss_value)}</td></tr>
        <tr><td>User Activity</td><td class="${auditData.activity?.severity}">${sevLabel(auditData.activity?.severity)}</td>
            <td>Corrections: ${auditData.activity?.inventory_corrections_count} · Edits: ${auditData.activity?.invoice_edits_count} · Off-hours: ${auditData.activity?.off_hours_count}</td></tr>
        ${auditData.digital ? `<tr><td>Digital Payments</td><td class="${auditData.digital?.severity}">${sevLabel(auditData.digital?.severity)}</td>
            <td>Total: ${php(auditData.digital?.total_digital_collected)} · Missing ref#: ${auditData.digital?.missing_ref_count || 0} · Transactions: ${auditData.digital?.transaction_count || 0}</td></tr>` : ''}
        ${auditData.inventory?.available ? `<tr><td>Inventory (Physical)</td><td class="${auditData.inventory?.severity}">${sevLabel(auditData.inventory?.severity)}</td>
            <td>Accuracy: ${auditData.inventory?.summary?.inventory_accuracy_pct}% · Variance: ${php(auditData.inventory?.summary?.total_variance_capital)}</td></tr>` : ''}
      </tbody>
    </table>
    <p style="font-size:10px;color:#888">Generated: ${new Date().toLocaleString()} — AgriBooks Business Management</p>
    </body></html>`);
    win.document.close();
    win.print();
  };

  const overallScore = computeOverallScore(auditData);
  const scoreColor = !overallScore ? 'text-slate-400' : overallScore >= 80 ? 'text-emerald-600' : overallScore >= 50 ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="p-6 space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#1A4D2E] flex items-center justify-center">
            <ShieldCheck size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-800" style={{ fontFamily: 'Manrope' }}>Audit Center</h1>
            <p className="text-xs text-slate-500">Comprehensive business audit — cash, inventory, sales, AR, payables, activity</p>
          </div>
        </div>
        {auditData && (
          <div className="text-center">
            <p className={`text-4xl font-bold font-mono ${scoreColor}`}>{overallScore}/100</p>
            <p className="text-xs text-slate-500 mt-0.5">Overall Audit Score</p>
          </div>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="run"><ShieldCheck size={14} className="mr-1.5" />Run Audit</TabsTrigger>
          <TabsTrigger value="discrepancies" data-testid="discrepancies-tab">
            <ShieldAlert size={14} className="mr-1.5" />Discrepancies
            {discrepancies.length > 0 && (
              <span className="ml-1.5 bg-amber-500 text-white text-[10px] rounded-full px-1.5 py-0.5 font-bold">{discrepancies.length}</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="prepare" data-testid="prepare-audit-tab">
            <Download size={14} className="mr-1.5" />Prepare for Audit
            {prepStats && <span className="ml-1.5 bg-emerald-500 text-white text-[10px] rounded-full px-1.5 py-0.5">✓</span>}
          </TabsTrigger>
          <TabsTrigger value="history" data-testid="audit-history-tab"><History size={14} className="mr-1.5" />Audit History</TabsTrigger>
        </TabsList>

        {/* ── RUN AUDIT TAB ────────────────────────────────────────────── */}
        <TabsContent value="run" className="mt-4 space-y-4">
          {/* Setup card */}
          <Card className="border-slate-200">
            <CardContent className="p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {isAdmin && (
                  <div>
                    <Label className="text-xs text-slate-500">Audit Type</Label>
                    <Select value={auditType} onValueChange={setAuditType}>
                      <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="partial">Partial — Financial Only</SelectItem>
                        <SelectItem value="full">Full — Includes Inventory</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {isAdmin && (
                  <div>
                    <Label className="text-xs text-slate-500">Branch</Label>
                    <Select value={auditBranchId || 'all'} onValueChange={v => setAuditBranchId(v === 'all' ? '' : v)}>
                      <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Branches</SelectItem>
                        {(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div>
                  <Label className="text-xs text-slate-500">Period From</Label>
                  <Input type="date" value={periodFrom} onChange={e => setPeriodFrom(e.target.value)} className="mt-1 h-9" />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Period To</Label>
                  <Input type="date" value={periodTo} onChange={e => setPeriodTo(e.target.value)} className="mt-1 h-9" />
                </div>
              </div>

              {auditType === 'full' && (
                <div className="mt-3 p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-800">
                  <p className="font-semibold mb-0.5">Full Audit — Inventory Comparison</p>
                  <p>The system will auto-detect the last 2 completed count sheets for the selected branch and compare expected quantities (from all movements) against physical counts.</p>
                </div>
              )}

              <div className="flex gap-3 mt-4">
                <Button onClick={runAudit} disabled={computing}
                  className="bg-[#1A4D2E] hover:bg-[#14532d] text-white h-10 px-8"
                  data-testid="run-audit-btn">
                  {computing ? <RefreshCw size={16} className="animate-spin mr-2" /> : <ShieldCheck size={16} className="mr-2" />}
                  {computing ? 'Computing...' : 'Run Audit'}
                </Button>
                {auditData && (
                  <>
                    <Button variant="outline" onClick={printAuditReport} className="h-10">
                      <Printer size={14} className="mr-1.5" /> Print Report
                    </Button>
                    <Button onClick={finalizeAudit} className="bg-emerald-600 hover:bg-emerald-700 text-white h-10 ml-auto">
                      <Check size={14} className="mr-1.5" /> Finalize Audit
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {auditData && (
            <div className="space-y-3">
              {/* Score summary */}
              <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
                {[
                  { key: 'cash', label: 'Cash', icon: <Banknote size={14} /> },
                  { key: 'sales', label: 'Sales', icon: <TrendingUp size={14} /> },
                  { key: 'ar', label: 'AR', icon: <FileText size={14} /> },
                  { key: 'payables', label: 'Payables', icon: <Building2 size={14} /> },
                  { key: 'transfers', label: 'Transfers', icon: <ArrowRight size={14} /> },
                  { key: 'returns', label: 'Returns', icon: <RotateCcw size={14} /> },
                  { key: 'activity', label: 'Activity', icon: <Users size={14} /> },
                  ...(auditData.inventory?.available ? [{ key: 'inventory', label: 'Inventory', icon: <Package size={14} /> }] : []),
                ].map(s => {
                  const sev = auditData[s.key]?.severity || 'ok';
                  return (
                    <div key={s.key} className={`p-2 rounded-lg border text-center ${SEV_COLORS[sev]}`}>
                      <div className="flex justify-center mb-1">{s.icon}</div>
                      <p className="text-[10px] font-medium">{s.label}</p>
                      <p className="text-[9px] mt-0.5">{SEV_LABELS[sev]}</p>
                    </div>
                  );
                })}
              </div>

              {/* Section 2: Cash */}
              <SectionCard title="Cash & Fund Reconciliation" icon={<Banknote size={16} className="text-emerald-700" />}
                sev={auditData.cash?.severity} defaultOpen insight={getInsight('cash', auditData.cash)} data_testid="audit-cash-section">
                <div className="space-y-1 mt-2">
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 mb-3">
                    <p className="text-[10px] text-slate-500 font-medium uppercase mb-2">Formula: Starting Float + Cash Sales + AR Collected − All Expenses = Expected Cash</p>
                    <StatRow label="Starting Float" value={formatPHP(auditData.cash.starting_float)} />
                    <StatRow label="+ Cash Sales" value={formatPHP(auditData.cash.cash_sales)} highlight="text-emerald-600" />
                    <StatRow label="+ AR Collected" value={formatPHP(auditData.cash.ar_collected)} highlight="text-emerald-600" />
                    <StatRow label="− Total Expenses" value={`-${formatPHP(auditData.cash.total_expenses)}`} highlight="text-red-600" />
                    <Separator className="my-2" />
                    <StatRow label="Expected Cash" value={formatPHP(auditData.cash.expected_cash)} highlight="font-bold text-slate-800" />
                    <StatRow label="Current Cashier Balance" value={formatPHP(auditData.cash.current_cashier_balance)} />
                    <StatRow label="Safe Balance" value={formatPHP(auditData.cash.safe_balance)} />
                  </div>
                  {/* Cash actual count entry + Reconcile Now */}
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                    <div className="flex-1">
                      <Label className="text-xs text-amber-800 font-medium">Enter Actual Cash Count (Cashier Drawer Only)</Label>
                      <Input type="number" min={0} value={actualCashCount}
                        onChange={e => setActualCashCount(e.target.value)}
                        placeholder="0.00" className="mt-1 h-8 font-mono" />
                    </div>
                    {actualCashCount && (
                      <div className="text-right shrink-0">
                        <p className="text-xs text-slate-500">Discrepancy vs Expected</p>
                        <p className={`text-lg font-bold font-mono ${parseFloat(actualCashCount) >= auditData.cash.expected_cash ? 'text-emerald-600' : 'text-red-600'}`}>
                          {parseFloat(actualCashCount) >= auditData.cash.expected_cash ? '+' : ''}{formatPHP(parseFloat(actualCashCount) - auditData.cash.expected_cash)}
                        </p>
                      </div>
                    )}
                    <Button
                      size="sm"
                      onClick={() => navigate('/close-wizard')}
                      className="h-9 shrink-0 bg-amber-600 hover:bg-amber-700 text-white"
                      data-testid="reconcile-now-btn"
                    >
                      <Banknote size={14} className="mr-1.5" /> Reconcile Now
                    </Button>
                  </div>
                  {auditData.cash.expense_breakdown?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">Expense Breakdown ({auditData.cash.expense_breakdown.length} categories)</summary>
                      <div className="mt-2 space-y-0.5">
                        {auditData.cash.expense_breakdown.map(e => (
                          <StatRow key={e.category} label={e.category} value={formatPHP(e.total)} sub={`${e.count} entries`} />
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 3: Sales */}
              <SectionCard title="Sales Audit" icon={<TrendingUp size={16} className="text-blue-600" />}
                sev={auditData.sales?.severity} insight={getInsight('sales', auditData.sales)} data_testid="audit-sales-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Sales (period)" value={formatPHP(auditData.sales.grand_total_sales)} highlight="font-bold" />
                  <StatRow label="Total Transactions" value={auditData.sales.total_transactions} />
                  {Object.entries(auditData.sales.by_payment_type || {}).map(([type, v]) => (
                    <StatRow key={type} label={`  → ${type}`} value={formatPHP(v.total)} sub={`${v.count} txns`} />
                  ))}
                  <Separator className="my-2" />
                  <StatRow label="Voided Transactions" value={auditData.sales.voided_count}
                    highlight={auditData.sales.voided_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Edited Invoices" value={auditData.sales.edited_count}
                    highlight={auditData.sales.edited_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  {auditData.sales.edited_invoices?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-amber-700 cursor-pointer">View edited invoices ({auditData.sales.edited_count})</summary>
                      <div className="mt-2 space-y-1">
                        {auditData.sales.edited_invoices.map((e, i) => (
                          <div key={i} className="text-xs p-2 bg-amber-50 rounded">
                            <span className="font-mono">{e.invoice_number}</span>
                            <span className="text-slate-500 ml-2">{e.edited_by_name} · {e.edited_at?.slice(0, 10)}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 4: AR */}
              <SectionCard title="Accounts Receivable" icon={<FileText size={16} className="text-purple-600" />}
                sev={auditData.ar?.severity} insight={getInsight('ar', auditData.ar)} data_testid="audit-ar-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Outstanding AR" value={formatPHP(auditData.ar.total_outstanding_ar)} highlight="font-bold" />
                  <StatRow label="Open Invoices" value={auditData.ar.open_invoices_count} />
                  <StatRow label="Collected in Period" value={formatPHP(auditData.ar.collected_in_period)} highlight="text-emerald-600" />
                  <Separator className="my-2" />
                  <p className="text-xs text-slate-500 font-medium">AR Aging Buckets</p>
                  <StatRow label="Current (0–30 days)" value={formatPHP(auditData.ar.aging?.current)} highlight="text-emerald-600" />
                  <StatRow label="31–60 days" value={formatPHP(auditData.ar.aging?.b31_60)} highlight="text-amber-600" />
                  <StatRow label="61–90 days" value={formatPHP(auditData.ar.aging?.b61_90)} highlight="text-orange-600" />
                  <StatRow label="90+ days (Critical)" value={formatPHP(auditData.ar.aging?.b90plus)}
                    highlight={auditData.ar.aging?.b90plus > 0 ? 'text-red-600 font-bold' : 'text-emerald-600'} />
                </div>
              </SectionCard>

              {/* Section 5: Payables */}
              <SectionCard title="Accounts Payable" icon={<Building2 size={16} className="text-orange-600" />}
                sev={auditData.payables?.severity} insight={getInsight('payables', auditData.payables)} data_testid="audit-payables-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Outstanding AP" value={formatPHP(auditData.payables.total_outstanding_ap)} highlight="font-bold" />
                  <StatRow label="Unpaid POs" value={auditData.payables.unpaid_po_count} />
                  <StatRow label="Overdue POs" value={auditData.payables.overdue_count}
                    highlight={auditData.payables.overdue_count > 0 ? 'text-red-600 font-bold' : ''} />
                  <StatRow label="Overdue Value" value={formatPHP(auditData.payables.overdue_value)}
                    highlight={auditData.payables.overdue_value > 0 ? 'text-red-600' : ''} />
                </div>
              </SectionCard>

              {/* Section 6: Transfers */}
              <SectionCard title="Branch Transfers" icon={<ArrowRight size={16} className="text-blue-600" />}
                sev={auditData.transfers?.severity} insight={getInsight('transfers', auditData.transfers)} data_testid="audit-transfers-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Transfers (period)" value={auditData.transfers.total_transfers} />
                  <StatRow label="Successfully Received" value={auditData.transfers.received_count} highlight="text-emerald-600" />
                  <StatRow label="With Shortage" value={auditData.transfers.with_shortage}
                    highlight={auditData.transfers.with_shortage > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="With Excess" value={auditData.transfers.with_excess}
                    highlight={auditData.transfers.with_excess > 0 ? 'text-blue-600' : ''} />
                  <StatRow label="Pending (unresolved)" value={auditData.transfers.pending_count}
                    highlight={auditData.transfers.pending_count > 0 ? 'text-amber-600' : ''} />
                  <StatRow label="Pending Stock Requests" value={auditData.transfers.pending_requests}
                    highlight={auditData.transfers.pending_requests > 0 ? 'text-slate-600' : ''} />
                  {auditData.transfers.total_shortage_value > 0 && (
                    <StatRow label="Total Shortage Value" value={formatPHP(auditData.transfers.total_shortage_value)} highlight="text-red-600 font-bold" />
                  )}
                </div>
              </SectionCard>

              {/* Section 7: Returns */}
              <SectionCard title="Returns & Losses" icon={<RotateCcw size={16} className="text-amber-600" />}
                sev={auditData.returns?.severity} insight={getInsight('returns', auditData.returns)} data_testid="audit-returns-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Returns (period)" value={auditData.returns.total_returns} />
                  <StatRow label="Total Refunded" value={formatPHP(auditData.returns.total_refunded)} highlight="text-red-600" />
                  <StatRow label="Pull-out (Loss) Count" value={auditData.returns.pullout_count}
                    highlight={auditData.returns.pullout_count > 0 ? 'text-red-600 font-bold' : ''} />
                  <StatRow label="Total Loss Value (Capital)" value={formatPHP(auditData.returns.total_loss_value)}
                    highlight={auditData.returns.total_loss_value > 0 ? 'text-red-600' : ''} />
                  {auditData.returns.top_reasons?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-500 font-medium mb-1">Top Return Reasons</p>
                      {auditData.returns.top_reasons.slice(0, 3).map(r => (
                        <StatRow key={r.reason} label={r.reason} value={`${r.count} returns`} />
                      ))}
                    </div>
                  )}
                </div>
              </SectionCard>

              {/* Section 8: Activity */}
              <SectionCard title="User Activity" icon={<Users size={16} className="text-slate-600" />}
                sev={auditData.activity?.severity} insight={getInsight('activity', auditData.activity)} data_testid="audit-activity-section">
                <div className="space-y-1 mt-2">
                  <p className="text-xs text-slate-500 font-medium mb-2">Sales by User</p>
                  {auditData.activity.sales_by_user?.map(u => (
                    <StatRow key={u.user} label={u.user} value={formatPHP(u.total)} sub={`${u.count} transactions`} />
                  ))}
                  <Separator className="my-2" />
                  <StatRow label="Inventory Corrections" value={auditData.activity.inventory_corrections_count}
                    highlight={auditData.activity.inventory_corrections_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Invoice Edits" value={auditData.activity.invoice_edits_count}
                    highlight={auditData.activity.invoice_edits_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Off-hours Transactions" value={auditData.activity.off_hours_count}
                    highlight={auditData.activity.off_hours_count > 0 ? 'text-red-600 font-bold' : ''}
                    sub="Before 7am or after 10pm" />
                  {auditData.activity.off_hours_transactions?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-red-700 cursor-pointer">View off-hours transactions</summary>
                      <div className="mt-2 space-y-1">
                        {auditData.activity.off_hours_transactions.map((t, i) => (
                          <div key={i} className="text-xs p-2 bg-red-50 rounded flex justify-between">
                            <span><span className="font-mono">{t.invoice_number}</span> · {t.cashier_name}</span>
                            <span>{formatPHP(t.grand_total)} · {t.created_at?.slice(11, 16)}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 9: Digital Payments */}
              {auditData.digital && (
                <SectionCard
                  title="Digital Payments (GCash / Maya / E-wallet)"
                  icon={<Smartphone size={16} className="text-blue-600" />}
                  sev={auditData.digital.severity}
                  data_testid="audit-digital-section"
                  insight={{
                    type: auditData.digital.missing_ref_count > 0 ? 'critical' : 'ok',
                    text: auditData.digital.missing_ref_count > 0
                      ? `${auditData.digital.missing_ref_count} digital transaction(s) are missing reference numbers — these cannot be traced back to their source. Require cashiers to always enter the GCash/Maya reference code before completing the sale.`
                      : `All ${auditData.digital.transaction_count} digital payments have reference numbers. Total collected: ${formatPHP(auditData.digital.total_digital_collected)}. These funds are tracked in the Digital wallet separately from the cashier drawer.`,
                  }}
                >
                  <div className="space-y-2 mt-2">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div className="rounded-lg bg-blue-50 border border-blue-200 p-2.5 text-center">
                        <p className="text-xs text-blue-500 mb-0.5">Total Digital Collected</p>
                        <p className="font-bold font-mono text-blue-700">{formatPHP(auditData.digital.total_digital_collected)}</p>
                      </div>
                      <div className="rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-center">
                        <p className="text-xs text-slate-500 mb-0.5">Digital Wallet Balance</p>
                        <p className="font-bold font-mono text-slate-700">{formatPHP(auditData.digital.digital_wallet_balance)}</p>
                      </div>
                    </div>

                    {/* By Platform */}
                    {Object.entries(auditData.digital.by_platform || {}).map(([platform, amt]) => (
                      <StatRow key={platform} label={platform} value={formatPHP(amt)} />
                    ))}

                    {auditData.digital.missing_ref_count > 0 && (
                      <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 mt-2">
                        <p className="text-xs font-semibold text-red-700">
                          ⚠ {auditData.digital.missing_ref_count} transaction(s) missing reference number
                        </p>
                        <p className="text-[10px] text-red-500 mt-0.5">
                          These cannot be traced back to the GCash/Maya app for verification.
                        </p>
                      </div>
                    )}

                    {/* Transaction list */}
                    {auditData.digital.transactions?.length > 0 && (
                      <details className="mt-2">
                        <summary className="text-xs text-blue-600 cursor-pointer font-medium">
                          View {auditData.digital.transactions.length} digital transaction(s)
                        </summary>
                        <div className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                          {auditData.digital.transactions.map((t, i) => (
                            <div key={i} className={`text-xs p-2 rounded flex items-center justify-between gap-2 ${t.has_ref ? 'bg-blue-50' : 'bg-red-50 border border-red-200'}`}>
                              <div className="min-w-0">
                                <span className="font-mono text-blue-700 mr-1">{t.invoice_number}</span>
                                <span className="text-slate-500 truncate">{t.customer_name}</span>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="text-[10px] text-blue-500">{t.platform}</span>
                                  {t.ref_number ? (
                                    <span className="text-[10px] font-mono text-slate-500">#{t.ref_number}</span>
                                  ) : (
                                    <span className="text-[10px] text-red-500 font-semibold">No ref#</span>
                                  )}
                                  {t.is_split && <span className="text-[10px] text-purple-500">split</span>}
                                </div>
                              </div>
                              <span className="font-bold text-blue-700 font-mono shrink-0">{formatPHP(t.amount)}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </SectionCard>
              )}

              {/* Section 1: Inventory (full audit only) */}
              {auditData.inventory?.available && (
                <SectionCard title={`Inventory Physical Count (${auditData.inventory.baseline_date} → ${auditData.inventory.current_date})`}
                  icon={<Package size={16} className="text-[#1A4D2E]" />}
                  sev={auditData.inventory.severity} insight={getInsight('inventory', auditData.inventory)} data_testid="audit-inventory-section">
                  <div className="space-y-2 mt-2">
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold text-emerald-600">{auditData.inventory.summary.inventory_accuracy_pct}%</p>
                        <p className="text-xs text-slate-500">Accuracy</p>
                      </div>
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold text-red-600">{auditData.inventory.summary.items_critical}</p>
                        <p className="text-xs text-slate-500">Critical Items</p>
                      </div>
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold font-mono">{formatPHP(auditData.inventory.summary.total_variance_capital)}</p>
                        <p className="text-xs text-slate-500">Variance Value</p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 font-medium mb-1">Formula: Baseline Count + All Movements = Expected · Physical Count − Expected = Variance</p>
                    <div className="max-h-64 overflow-y-auto">
                      <table className="w-full text-xs border-collapse">
                        <thead className="sticky top-0 bg-white">
                          <tr className="border-b">
                            <th className="text-left px-2 py-1.5 text-slate-500 uppercase">Product</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Baseline</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">+Movements</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Expected</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Physical</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Variance</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">₱ Impact</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditData.inventory.items?.filter(i => i.severity !== 'ok').map((item, idx) => (
                            <tr key={idx} className={`border-b ${item.severity === 'critical' ? 'bg-red-50' : item.severity === 'warning' ? 'bg-amber-50' : ''}`}>
                              <td className="px-2 py-1.5">
                                <p className="font-medium">{item.product_name}</p>
                                <p className="text-slate-400">{item.sku}</p>
                              </td>
                              <td className="px-2 py-1.5 text-right font-mono">{item.baseline_qty}</td>
                              <td className="px-2 py-1.5 text-right font-mono text-blue-600">{item.net_movement >= 0 ? '+' : ''}{item.net_movement}</td>
                              <td className="px-2 py-1.5 text-right font-mono">{item.expected_qty}</td>
                              <td className="px-2 py-1.5 text-right font-mono font-bold">{item.physical_count}</td>
                              <td className={`px-2 py-1.5 text-right font-mono font-bold ${item.variance < 0 ? 'text-red-600' : item.variance > 0 ? 'text-blue-600' : 'text-emerald-600'}`}>
                                {item.variance >= 0 ? '+' : ''}{item.variance}
                              </td>
                              <td className={`px-2 py-1.5 text-right font-mono ${item.variance_value_capital < 0 ? 'text-red-600' : 'text-blue-600'}`}>
                                {item.variance_value_capital >= 0 ? '+' : ''}{formatPHP(item.variance_value_capital)}
                              </td>
                            </tr>
                          ))}
                          {!auditData.inventory.items?.filter(i => i.severity !== 'ok').length && (
                            <tr><td colSpan={7} className="text-center py-4 text-emerald-600">All products within acceptable variance. Inventory accuracy is high.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </SectionCard>
              )}

              {auditData.inventory && !auditData.inventory.available && (
                <Card className="border-slate-200 bg-slate-50">
                  <CardContent className="p-4 text-center text-slate-500">
                    <Package size={24} className="mx-auto mb-2 opacity-40" />
                    <p className="text-sm">{auditData.inventory.message}</p>
                    {auditType === 'partial' && <p className="text-xs mt-1">Switch to Full Audit to include inventory comparison.</p>}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* ── DISCREPANCIES TAB ────────────────────────────────────────── */}
        <TabsContent value="discrepancies" className="mt-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-slate-800">Unresolved Discrepancies</h3>
              <p className="text-xs text-slate-500 mt-0.5">Flagged during transaction verification. Resolve after full audit review.</p>
            </div>
            <Button size="sm" variant="outline" onClick={loadDiscrepancies} className="h-8">
              <RefreshCw size={13} className="mr-1" /> Refresh
            </Button>
          </div>
          {loadingDisc ? (
            <div className="text-center py-8"><RefreshCw size={20} className="animate-spin mx-auto text-slate-400" /></div>
          ) : discrepancies.length === 0 ? (
            <Card className="border-slate-200 bg-slate-50">
              <CardContent className="p-8 text-center">
                <ShieldCheck size={28} className="mx-auto mb-2 text-emerald-400" />
                <p className="text-sm text-slate-500">No unresolved discrepancies. All verified transactions are clean.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {discrepancies.map(disc => (
                <Card key={disc.id} className="border-amber-200">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <ShieldAlert size={14} className="text-amber-500 shrink-0" />
                          <span className="font-semibold text-sm text-slate-800">{disc.doc_number}</span>
                          <Badge className="text-[10px] bg-amber-100 text-amber-700">{disc.doc_type?.replace('_', ' ')}</Badge>
                          <span className="text-[10px] text-slate-400">{disc.doc_date}</span>
                        </div>
                        {disc.doc_title && <p className="text-xs text-slate-500 mb-1">{disc.doc_title}</p>}
                        {disc.item_description && (
                          <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs mt-2">
                            <span className="font-medium text-amber-800">{disc.item_description}</span>
                            {disc.expected_qty != null && (
                              <span className="ml-2 text-amber-700">
                                Expected: <b>{disc.expected_qty}</b> {disc.unit} · Found: <b>{disc.found_qty}</b> {disc.unit}
                                {disc.value_impact != null && (
                                  <span className={`ml-2 font-bold ${disc.value_impact < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                                    {disc.value_impact > 0 ? '+' : ''}{formatPHP(disc.value_impact)}
                                  </span>
                                )}
                              </span>
                            )}
                            <p className="text-slate-500 mt-1">{disc.note}</p>
                          </div>
                        )}
                        <p className="text-[10px] text-slate-400 mt-1.5">Verified by {disc.verified_by_name} · {disc.verified_at?.slice(0, 16)?.replace('T', ' ')}</p>
                      </div>
                      <Button size="sm" onClick={() => { setResolveDialog(disc); setResolveAction('dismiss'); setResolveNote(''); }}
                        className="shrink-0 h-8 text-xs bg-slate-800 hover:bg-slate-900 text-white">
                        Resolve
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          {resolveDialog && (
            <div className="fixed inset-0 flex items-center justify-center p-4" style={{ backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 9999 }}
              onClick={e => { if (e.target === e.currentTarget) setResolveDialog(null); }}>
              <div className="bg-white rounded-2xl shadow-2xl w-full p-5" style={{ maxWidth: '420px' }}>
                <p className="font-bold text-slate-800 mb-1">Resolve Discrepancy</p>
                <p className="text-xs text-slate-400 mb-4">{resolveDialog.doc_number} · {resolveDialog.item_description}</p>
                <div className="flex gap-2 mb-4">
                  {['dismiss', 'apply'].map(a => (
                    <button key={a} onClick={() => setResolveAction(a)}
                      className={`flex-1 py-2 rounded-xl text-sm font-medium border transition-colors capitalize ${resolveAction === a ? 'bg-slate-800 text-white border-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                      {a === 'apply' ? 'Apply Correction' : 'Dismiss'}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-slate-500 mb-2">{resolveAction === 'apply' ? 'Creates an inventory adjustment with audit trail' : 'Records justification and marks as reviewed'}</p>
                <textarea value={resolveNote} onChange={e => setResolveNote(e.target.value)} placeholder="Justification / note…" rows={2}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm mb-4 focus:outline-none resize-none" />
                <div className="flex gap-2">
                  <button onClick={() => setResolveDialog(null)} className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-600 hover:bg-slate-50">Cancel</button>
                  <button onClick={resolveDiscrepancy} disabled={resolveSaving}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 ${resolveAction === 'apply' ? 'bg-[#1A4D2E] hover:bg-[#14532d]' : 'bg-slate-700 hover:bg-slate-800'}`}>
                    {resolveSaving ? 'Saving…' : resolveAction === 'apply' ? 'Apply Correction' : 'Dismiss'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── PREPARE FOR AUDIT TAB ─────────────────────────────────────── */}
        <TabsContent value="prepare" className="mt-4">
          <Card className="border-slate-200">
            <CardContent className="p-5">
              <div className="flex items-start gap-3 mb-5">
                <div className="w-10 h-10 rounded-xl bg-[#1A4D2E]/10 flex items-center justify-center shrink-0">
                  <Download size={18} className="text-[#1A4D2E]" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-800">Prepare Audit Package</h3>
                  <p className="text-sm text-slate-500 mt-0.5">Downloads all transactions and attached photos. Period auto-detected from your last two count sheets. Photos will open instantly.</p>
                </div>
              </div>
              {prepStats && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Check size={14} className="text-emerald-600" />
                    <span className="font-semibold text-emerald-800 text-sm">Package Ready</span>
                    <span className="text-[10px] text-emerald-600 ml-auto">{prepStats.cached_at}</span>
                  </div>
                  <p className="text-xs text-emerald-700 mb-1">Period: <b>{prepStats.period_from}</b> → <b>{prepStats.period_to}</b>
                    {prepStats.auto_detected && <span className="ml-2 text-emerald-500">(auto-detected)</span>}</p>
                  {prepStats.count_sheet_refs && <p className="text-xs text-emerald-600">{prepStats.count_sheet_refs.baseline} → {prepStats.count_sheet_refs.current}</p>}
                  <div className="grid grid-cols-4 gap-2 mt-2">
                    {[['POs', prepStats.purchase_orders], ['Expenses', prepStats.expenses], ['Transfers', prepStats.branch_transfers], ['Photos', prepStats.total_files]].map(([l, v]) => (
                      <div key={l} className="text-center bg-white rounded-lg py-1.5">
                        <p className="font-bold text-emerald-700 text-sm">{v}</p>
                        <p className="text-[10px] text-slate-400">{l}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {preparing && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <RefreshCw size={13} className="animate-spin text-[#1A4D2E]" />
                    <span className="text-sm text-slate-700">{prepProgress.step}</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2">
                    <div className="bg-[#1A4D2E] h-2 rounded-full transition-all duration-300" style={{ width: `${prepProgress.pct}%` }} />
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1 text-right">{prepProgress.pct}%</p>
                </div>
              )}
              <Button onClick={prepareForAudit} disabled={preparing || !auditBranchId}
                className={`w-full h-11 font-semibold transition-all ${preparing || !auditBranchId ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'bg-[#1A4D2E] hover:bg-[#14532d] text-white'}`} data-testid="prepare-audit-btn">
                {preparing ? <><RefreshCw size={15} className="animate-spin mr-2" />Preparing…</> : <><Download size={15} className="mr-2" />Prepare Audit Package</>}
              </Button>
              <p className="text-xs text-slate-400 text-center mt-2">Select a branch above first. Large datasets may take a few minutes.</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── HISTORY TAB ──────────────────────────────────────────────── */}
        <TabsContent value="history" className="mt-4 space-y-3">
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={loadHistory} disabled={loadingHistory}>
              <RefreshCw size={12} className={`mr-1.5 ${loadingHistory ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>
          {sessions.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <History size={32} className="mx-auto mb-2 opacity-40" />
              <p>No audits found. Run your first audit!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map(session => {
                const score = session.overall_score;
                const color = !score ? 'text-slate-400' : score >= 80 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-red-600';
                const sectionStatuses = Object.values(session.sections_status || {});
                const criticals = sectionStatuses.filter(s => s === 'critical').length;
                const warnings = sectionStatuses.filter(s => s === 'warning').length;
                return (
                  <Card key={session.id} className="border-slate-200 hover:border-slate-300 transition-colors">
                    <CardContent className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="text-center w-14">
                          <p className={`text-2xl font-bold font-mono ${color}`}>{score || '—'}</p>
                          <p className="text-[9px] text-slate-400">Score</p>
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-0.5">
                            <Badge className={`text-[10px] ${session.audit_type === 'full' ? 'bg-[#1A4D2E] text-white' : 'bg-blue-100 text-blue-700'}`}>
                              {session.audit_type === 'full' ? 'Full Audit' : 'Partial'}
                            </Badge>
                            <Badge className={`text-[10px] ${session.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                              {session.status}
                            </Badge>
                          </div>
                          <p className="font-semibold text-sm">{session.branch_name}</p>
                          <p className="text-xs text-slate-500">{session.period_from} → {session.period_to}</p>
                          <p className="text-xs text-slate-400">{session.created_by_name} · {session.created_at?.slice(0, 10)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {criticals > 0 && <Badge className="bg-red-100 text-red-700 text-[10px]">{criticals} critical</Badge>}
                        {warnings > 0 && <Badge className="bg-amber-100 text-amber-700 text-[10px]">{warnings} warnings</Badge>}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
