import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Search, AlertTriangle, Percent, Receipt, Clock, Calculator,
  Info, ChevronDown, ChevronUp, Zap, Edit3, Banknote, CreditCard,
  Building2, Smartphone, X, Tag
} from 'lucide-react';
import { toast } from 'sonner';
import SaleDetailModal from '../components/SaleDetailModal';

const METHODS = [
  { value: 'Cash', label: 'Cash', icon: Banknote },
  { value: 'Check', label: 'Check', icon: Receipt },
  { value: 'Bank Transfer', label: 'Bank', icon: Building2 },
  { value: 'GCash', label: 'GCash', icon: Smartphone },
  { value: 'Maya', label: 'Maya', icon: CreditCard },
];

const TYPE_CONFIG = {
  penalty_charge: { label: 'Penalty', cls: 'bg-red-100 text-red-700 border-red-200', priority: 1 },
  interest_charge: { label: 'Interest', cls: 'bg-amber-100 text-amber-700 border-amber-200', priority: 2 },
  farm_expense: { label: 'Farm', cls: 'bg-green-100 text-green-700 border-green-200', priority: 3 },
  cash_advance: { label: 'Customer Cash Out', cls: 'bg-purple-100 text-purple-700 border-purple-200', priority: 3 },
};
const getTypeConfig = (t) => TYPE_CONFIG[t] || { label: 'Invoice', cls: 'bg-slate-100 text-slate-700 border-slate-200', priority: 3 };
const isDiscountable = (t) => t === 'interest_charge' || t === 'penalty_charge';

export default function PaymentsPage() {
  const { currentBranch } = useAuth();

  // Customer
  const [customers, setCustomers] = useState([]);
  const [custSearch, setCustSearch] = useState('');
  const [custDropdownOpen, setCustDropdownOpen] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const custSearchRef = useRef(null);

  // Invoices
  const [invoices, setInvoices] = useState([]);
  const [rowAmounts, setRowAmounts] = useState({});
  const [rowDiscounts, setRowDiscounts] = useState({});
  const [discountModes, setDiscountModes] = useState({}); // { [inv_id]: 'amount' | 'percent' }

  // Payment header
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payMethod, setPayMethod] = useState('Cash');
  const [payRef, setPayRef] = useState('');
  const [payMemo, setPayMemo] = useState('');

  // Interest/penalty
  const [chargesOpen, setChargesOpen] = useState(false);
  const [penaltyRate, setPenaltyRate] = useState(5);
  const [chargesPreview, setChargesPreview] = useState(null);
  const [generatingCharge, setGeneratingCharge] = useState(null);
  const [interestRateInput, setInterestRateInput] = useState('');
  const [saveRateToCustomer, setSaveRateToCustomer] = useState(false);
  const interestPreviewTimer = useRef(null);

  // Dialogs
  const [historyOpen, setHistoryOpen] = useState(false);
  const [payHistory, setPayHistory] = useState([]);
  const [invoiceModalOpen, setInvoiceModalOpen] = useState(false);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);

  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } })
      .then(r => setCustomers(r.data.customers || []))
      .catch(() => {});
  }, []);

  const loadInvoices = useCallback(async (custId) => {
    try {
      const res = await api.get(`/customers/${custId}/invoices`);
      setInvoices(res.data || []);
      setRowAmounts({});
      setRowDiscounts({});
      setDiscountModes({});
    } catch { setInvoices([]); }
  }, []);

  const loadChargesPreview = useCallback(async (custId, rateOverride) => {
    try {
      const params = { as_of_date: payDate };
      if (rateOverride !== undefined && rateOverride > 0) params.rate_override = rateOverride;
      const res = await api.get(`/customers/${custId}/charges-preview`, { params });
      setChargesPreview(res.data);
    } catch { setChargesPreview(null); }
  }, [payDate]);

  const selectCustomer = (c) => {
    setSelectedCustomer(c);
    setCustSearch(c.name);
    setCustDropdownOpen(false);
    setRowAmounts({});
    setRowDiscounts({});
    setDiscountModes({});
    setPayRef('');
    setPayMemo('');
    setInterestRateInput(c.interest_rate > 0 ? String(c.interest_rate) : '');
    setSaveRateToCustomer(false);
    loadInvoices(c.id);
    loadChargesPreview(c.id);
  };

  const clearCustomer = () => {
    setSelectedCustomer(null);
    setCustSearch('');
    setInvoices([]);
    setRowAmounts({});
    setRowDiscounts({});
    setDiscountModes({});
    setChargesPreview(null);
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (selectedCustomer) {
      const rate = parseFloat(interestRateInput) || 0;
      loadChargesPreview(selectedCustomer.id, rate > 0 ? rate : undefined);
    }
  }, [payDate, selectedCustomer]);

  // Debounce interest rate changes to update preview
  useEffect(() => {
    if (!selectedCustomer) return;
    if (interestPreviewTimer.current) clearTimeout(interestPreviewTimer.current);
    interestPreviewTimer.current = setTimeout(() => {
      const rate = parseFloat(interestRateInput) || 0;
      loadChargesPreview(selectedCustomer.id, rate > 0 ? rate : undefined);
    }, 400);
    return () => { if (interestPreviewTimer.current) clearTimeout(interestPreviewTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interestRateInput]);

  // ---- Calculations ----
  const getDiscountAmount = (inv) => {
    const mode = discountModes[inv.id] || 'amount';
    const val = parseFloat(rowDiscounts[inv.id] || 0);
    if (isNaN(val) || val <= 0 || !isDiscountable(inv.sale_type)) return 0;
    if (mode === 'percent') return Math.min(round2(inv.balance * val / 100), inv.balance);
    return Math.min(val, inv.balance);
  };

  const totalApplied = invoices.reduce((s, inv) => {
    const v = parseFloat(rowAmounts[inv.id] || 0);
    return s + (isNaN(v) ? 0 : v);
  }, 0);

  const totalDiscount = invoices.reduce((s, inv) => s + getDiscountAmount(inv), 0);
  const totalOpen = invoices.reduce((s, i) => s + (i.balance || 0), 0);
  const hasUnsavedAmounts = Object.values(rowAmounts).some(v => parseFloat(v) > 0) || totalDiscount > 0;

  function round2(n) { return Math.round(n * 100) / 100; }

  // ---- Auto-apply ----
  const autoApply = (totalAmt) => {
    const amt = parseFloat(totalAmt) || 0;
    if (amt <= 0) { setRowAmounts({}); return; }
    let remaining = amt;
    const newAmounts = {};
    for (const inv of invoices) {
      if (remaining <= 0) break;
      const disc = getDiscountAmount(inv);
      const effectiveBal = Math.max(0, inv.balance - disc);
      const apply = Math.min(remaining, effectiveBal);
      if (apply > 0) { newAmounts[inv.id] = apply.toFixed(2); remaining = round2(remaining - apply); }
    }
    setRowAmounts(newAmounts);
  };

  // ---- Generate Interest ----
  const handleGenerateInterest = async () => {
    const rate = parseFloat(interestRateInput) || 0;
    if (rate <= 0) { toast.error('Enter an interest rate (% per month) first'); return; }
    setGeneratingCharge('interest');
    try {
      const payload = { as_of_date: payDate, rate_override: rate };
      if (saveRateToCustomer) payload.save_rate = true;
      const res = await api.post(`/customers/${selectedCustomer.id}/generate-interest`, payload);
      if (res.data.total_interest > 0) {
        toast.success(`Interest invoice ${res.data.invoice_number} created — ${formatPHP(res.data.total_interest)}`);
        if (saveRateToCustomer) {
          setSelectedCustomer(prev => ({ ...prev, interest_rate: rate }));
          toast(`Interest rate ${rate}%/mo saved to ${selectedCustomer.name}'s profile`);
          setSaveRateToCustomer(false);
        }
        await loadInvoices(selectedCustomer.id);
        await loadChargesPreview(selectedCustomer.id, rate);
      } else {
        toast(`No interest to generate — ${res.data.message}`, { description: `Grace: ${res.data.grace_period} days` });
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to generate interest'); }
    setGeneratingCharge(null);
  };

  // ---- Generate Penalty ----
  const handleGeneratePenalty = async () => {
    setGeneratingCharge('penalty');
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/generate-penalty`, { penalty_rate: penaltyRate, as_of_date: payDate });
      if (res.data.total_penalty > 0) {
        toast.success(`Penalty invoice ${res.data.invoice_number} created — ${formatPHP(res.data.total_penalty)}`);
        await loadInvoices(selectedCustomer.id);
        await loadChargesPreview(selectedCustomer.id);
      } else {
        toast(`No penalty applicable — ${res.data.message}`);
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to generate penalty'); }
    setGeneratingCharge(null);
  };

  // ---- Apply Payment ----
  const handleApplyPayment = async () => {
    const allocations = invoices
      .map(inv => ({
        invoice_id: inv.id,
        amount: parseFloat(rowAmounts[inv.id] || 0),
        discount: getDiscountAmount(inv),
      }))
      .filter(a => a.amount > 0 || a.discount > 0);

    if (allocations.length === 0) { toast.error('Enter payment amounts for at least one invoice'); return; }

    setProcessing(true);
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/receive-payment`, {
        allocations, method: payMethod, reference: payRef, date: payDate,
        branch_id: currentBranch?.id, memo: payMemo,
      });
      const parts = [`${formatPHP(res.data.total_applied)} applied`];
      if (res.data.total_discounted > 0) parts.push(`${formatPHP(res.data.total_discounted)} discounted`);
      parts.push(`to ${res.data.applied_invoices.length} invoice(s)`);
      toast.success(parts.join(' ') + ` — deposited to ${res.data.deposited_to}`);
      setRowAmounts({});
      setRowDiscounts({});
      setDiscountModes({});
      setPayRef('');
      setPayMemo('');
      await loadInvoices(selectedCustomer.id);
      await loadChargesPreview(selectedCustomer.id);
      // Refresh customer balance
      const custRes = await api.get('/customers', { params: { limit: 500 } });
      const updated = (custRes.data.customers || []).find(c => c.id === selectedCustomer.id);
      if (updated) { setSelectedCustomer(updated); setCustomers(custRes.data.customers); }
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
    setProcessing(false);
  };

  const loadHistory = async () => {
    try {
      const res = await api.get(`/customers/${selectedCustomer.id}/payment-history`);
      setPayHistory(res.data);
      setHistoryOpen(true);
    } catch { toast.error('Failed to load history'); }
  };

  const getDaysOverdue = (dueDate) => {
    if (!dueDate) return 0;
    return Math.max(0, Math.floor((new Date(payDate) - new Date(dueDate)) / 86400000));
  };

  const filteredCustomers = custSearch && !selectedCustomer
    ? customers.filter(c => c.name.toLowerCase().includes(custSearch.toLowerCase()) || c.phone?.includes(custSearch))
    : [];

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] animate-fadeIn" data-testid="payments-page">

      {/* ═══════════ QB-STYLE HEADER ═══════════ */}
      <Card className="border-slate-200 shrink-0">
        <CardContent className="p-4 sm:p-5">
          {/* Title row */}
          <div className="flex items-start justify-between mb-4">
            <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }} data-testid="payments-title">
              Customer Payment
            </h1>
            {selectedCustomer && (
              <div className="text-right" data-testid="customer-balance-display">
                <p className="text-[10px] text-slate-400 uppercase tracking-wide">Customer Balance</p>
                <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalOpen)}</p>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-x-6 gap-y-3">
            {/* Left: customer + payment fields */}
            <div className="space-y-3">
              {/* RECEIVED FROM */}
              <div className="flex items-center gap-3">
                <Label className="text-xs text-slate-500 w-24 shrink-0 uppercase tracking-wide">Received From</Label>
                <div className="flex-1 relative" ref={custSearchRef}>
                  <div className="relative">
                    <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input
                      value={selectedCustomer ? selectedCustomer.name : custSearch}
                      onChange={e => { setCustSearch(e.target.value); setCustDropdownOpen(true); if (selectedCustomer) clearCustomer(); }}
                      onFocus={() => { if (!selectedCustomer) setCustDropdownOpen(true); }}
                      onBlur={() => setTimeout(() => setCustDropdownOpen(false), 200)}
                      placeholder="Search customer..."
                      className="pl-8 h-9 font-medium"
                      data-testid="payment-customer-search"
                    />
                    {selectedCustomer && (
                      <button onClick={clearCustomer} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                        <X size={14} />
                      </button>
                    )}
                  </div>
                  {custDropdownOpen && filteredCustomers.length > 0 && (
                    <div className="absolute z-50 top-full mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                      {filteredCustomers.slice(0, 12).map(c => (
                        <button key={c.id} onMouseDown={() => selectCustomer(c)} data-testid={`pay-cust-${c.id}`}
                          className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm border-b last:border-0 flex items-center justify-between">
                          <div>
                            <span className="font-medium">{c.name}</span>
                            <span className="text-[11px] text-slate-400 ml-2">
                              {c.interest_rate > 0 ? `${c.interest_rate}%/mo` : ''}
                            </span>
                          </div>
                          {c.balance > 0 && <span className="text-xs text-red-600 font-bold">{formatPHP(c.balance)}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* PAYMENT AMOUNT + DATE + REF */}
              <div className="flex items-center gap-3 flex-wrap">
                <Label className="text-xs text-slate-500 w-24 shrink-0 uppercase tracking-wide">Payment Amt</Label>
                <Input type="number" placeholder="0.00" className="h-9 w-36 text-lg font-bold font-mono" data-testid="receive-amount"
                  onChange={e => autoApply(e.target.value)} />
                <Separator orientation="vertical" className="h-7 hidden sm:block" />
                <div className="flex items-center gap-1.5">
                  <Label className="text-[10px] text-slate-400 uppercase">Date</Label>
                  <Input type="date" value={payDate} onChange={e => setPayDate(e.target.value)} className="h-9 w-36" data-testid="payment-date" />
                </div>
                <div className="flex items-center gap-1.5">
                  <Label className="text-[10px] text-slate-400 uppercase">Ref #</Label>
                  <Input value={payRef} onChange={e => setPayRef(e.target.value)} placeholder="Check #, OR#..." className="h-9 w-32" data-testid="payment-ref" />
                </div>
              </div>
            </div>

            {/* Right: payment method icons */}
            <div className="flex flex-col gap-1.5">
              <Label className="text-[10px] text-slate-400 uppercase tracking-wide text-center">Payment Method</Label>
              <div className="flex gap-1" data-testid="payment-methods">
                {METHODS.map(m => {
                  const Icon = m.icon;
                  const active = payMethod === m.value;
                  return (
                    <button key={m.value} onClick={() => setPayMethod(m.value)} data-testid={`pay-method-${m.value}`}
                      className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg border text-xs transition-all ${
                        active ? 'bg-[#1A4D2E] text-white border-[#1A4D2E] shadow-sm' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                      }`}>
                      <Icon size={16} />
                      <span className="text-[10px] font-medium">{m.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ═══════════ MAIN CONTENT ═══════════ */}
      {!selectedCustomer ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Receipt size={48} className="mx-auto text-slate-200 mb-3" />
            <p className="text-slate-400">Search and select a customer above to receive payment</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-3 mt-3 overflow-hidden min-h-0">

          {/* ── Interest/Penalty Charges Generation ── */}
          <Card className="border-slate-200 shrink-0">
            <button className="w-full" onClick={() => setChargesOpen(o => !o)}>
              <CardContent className="p-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-2">
                  <Calculator size={14} className="text-amber-500" />
                  <span className="text-xs font-medium">Generate Interest / Penalty Charges</span>
                  {chargesPreview?.total_interest > 0 && (
                    <Badge className="text-[9px] bg-amber-100 text-amber-700">
                      ~{formatPHP(chargesPreview.total_interest)} accrued
                    </Badge>
                  )}
                </div>
                {chargesOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </CardContent>
            </button>
            {chargesOpen && (
              <div className="px-4 pb-3 space-y-3 border-t border-slate-100">
                {chargesPreview && chargesPreview.total_interest > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-3">
                    <p className="text-xs font-semibold text-amber-700 mb-2 flex items-center gap-1">
                      <Info size={11} /> Accrued Interest Preview (as of {payDate})
                    </p>
                    <div className="grid grid-cols-3 gap-3 text-sm mb-2">
                      <div><p className="text-[10px] text-amber-600">Principal Due</p><p className="font-bold">{formatPHP(chargesPreview.total_principal)}</p></div>
                      <div><p className="text-[10px] text-amber-600">Computed Interest</p><p className="font-bold text-amber-700">{formatPHP(chargesPreview.total_interest)}</p></div>
                      <div><p className="text-[10px] text-amber-600">Combined Total</p><p className="font-bold text-red-600">{formatPHP(chargesPreview.total_principal + chargesPreview.total_interest)}</p></div>
                    </div>
                    {chargesPreview.interest_preview?.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-xs text-amber-700 py-0.5 border-b border-amber-100 last:border-0">
                        <span className="font-mono">{item.invoice_number}</span>
                        <span>{item.days_for_interest}d × {item.rate}%/mo</span>
                        <span className="font-medium">{formatPHP(item.interest_amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="flex-1 min-w-[220px] space-y-2">
                    <p className="text-xs text-slate-500">Grace period: <strong>{selectedCustomer.grace_period || 7} days</strong></p>
                    {/* Inline interest rate input */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <Label className="text-xs text-slate-600 shrink-0">Interest Rate:</Label>
                      <div className="flex items-center gap-0.5 bg-amber-50 border border-amber-200 rounded-md px-2 py-1">
                        <Input type="number" min="0" step="0.5" value={interestRateInput}
                          onChange={e => setInterestRateInput(e.target.value)}
                          placeholder="e.g. 3"
                          className="w-14 h-6 text-xs text-center border-0 bg-transparent p-0 font-bold text-amber-700"
                          data-testid="interest-rate-input" />
                        <span className="text-xs text-amber-600 font-medium">%/mo</span>
                      </div>
                      {selectedCustomer.interest_rate > 0 && (
                        <span className="text-[10px] text-slate-400">(saved: {selectedCustomer.interest_rate}%)</span>
                      )}
                    </div>
                    {/* Save to customer option */}
                    {interestRateInput && parseFloat(interestRateInput) > 0 && parseFloat(interestRateInput) !== selectedCustomer.interest_rate && (
                      <label className="flex items-center gap-1.5 cursor-pointer" data-testid="save-rate-checkbox">
                        <input type="checkbox" checked={saveRateToCustomer} onChange={e => setSaveRateToCustomer(e.target.checked)}
                          className="rounded border-amber-300 text-amber-600 focus:ring-amber-500 h-3.5 w-3.5" />
                        <span className="text-[11px] text-amber-700">Save {interestRateInput}%/mo to this customer's profile</span>
                      </label>
                    )}
                    {/* Interest formula explanation */}
                    <p className="text-[10px] text-slate-400 leading-relaxed">
                      Formula: principal × (rate ÷ 30) × days since last computation.
                      {' '}Computed from last interest date (not due date) to prevent double-charging.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button size="sm" variant="outline" onClick={handleGenerateInterest}
                      disabled={!!generatingCharge || !(parseFloat(interestRateInput) > 0)}
                      className="text-amber-600 border-amber-200 hover:bg-amber-50 gap-1 disabled:opacity-40" data-testid="generate-interest-btn">
                      <Percent size={12} /> {generatingCharge === 'interest' ? 'Generating...' : 'Generate Interest'}
                    </Button>
                    <Separator orientation="vertical" className="h-7" />
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-slate-500">Penalty:</span>
                      <div className="flex items-center gap-0.5 bg-slate-100 rounded-md px-2 py-1.5">
                        <Input type="number" value={penaltyRate} onChange={e => setPenaltyRate(parseFloat(e.target.value) || 0)}
                          className="w-12 h-6 text-xs text-center border-0 bg-transparent p-0" />
                        <span className="text-xs text-slate-500">%</span>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" onClick={handleGeneratePenalty} disabled={!!generatingCharge}
                      className="text-red-600 border-red-200 hover:bg-red-50 gap-1" data-testid="generate-penalty-btn">
                      <AlertTriangle size={12} /> {generatingCharge === 'penalty' ? 'Generating...' : 'Apply Penalty'}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* ── Outstanding Transactions Table (QB-style) ── */}
          <Card className="border-slate-200 flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Outstanding Transactions</span>
                {invoices.length > 0 && (
                  <button onClick={() => autoApply(totalOpen)} className="text-xs text-[#1A4D2E] hover:underline flex items-center gap-1 font-medium" data-testid="auto-apply-all-btn">
                    <Zap size={11} /> Auto-apply all
                  </button>
                )}
              </div>
              <Button variant="ghost" size="sm" className="text-xs gap-1" onClick={loadHistory} data-testid="payment-history-btn">
                <Clock size={12} /> History
              </Button>
            </div>
            {invoices.length === 0 ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center"><Receipt size={36} className="mx-auto mb-2 opacity-20 text-slate-300" /><p className="text-sm text-slate-400">No open invoices</p></div>
              </div>
            ) : (
              <ScrollArea className="flex-1">
                <table className="w-full text-sm" data-testid="invoices-table">
                  <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
                    <tr>
                      <th className="text-left px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase">Date</th>
                      <th className="text-left px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase">Number</th>
                      <th className="text-left px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase">Type</th>
                      <th className="text-right px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase">Orig. Amt</th>
                      <th className="text-right px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase">Amt. Due</th>
                      <th className="text-right px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase w-28">Discount</th>
                      <th className="text-right px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase w-32">Payment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((inv) => {
                      const tc = getTypeConfig(inv.sale_type);
                      const daysOver = getDaysOverdue(inv.due_date);
                      const graceP = selectedCustomer?.grace_period || 7;
                      const isOverdue = daysOver > graceP && inv.balance > 0;
                      const rowAmt = rowAmounts[inv.id] || '';
                      const isApplied = parseFloat(rowAmt) > 0;
                      const canDiscount = isDiscountable(inv.sale_type);
                      const discAmt = getDiscountAmount(inv);
                      const mode = discountModes[inv.id] || 'amount';

                      return (
                        <tr key={inv.id} className={`border-b border-slate-100 ${isApplied ? 'bg-emerald-50/40' : discAmt > 0 ? 'bg-blue-50/30' : 'hover:bg-slate-50/50'} transition-colors`}>
                          <td className="px-3 py-2 text-xs text-slate-500">{inv.order_date}</td>
                          <td className="px-3 py-2">
                            <button className="font-mono text-xs text-blue-600 hover:underline flex items-center gap-1"
                              onClick={() => { setSelectedInvoiceId(inv.id); setInvoiceModalOpen(true); }} data-testid={`inv-link-${inv.id}`}>
                              {inv.invoice_number}
                              {inv.edited && <Edit3 size={9} className="text-orange-400" />}
                            </button>
                            {isOverdue && <Badge className="text-[8px] bg-red-100 text-red-700 mt-0.5">{daysOver}d overdue</Badge>}
                          </td>
                          <td className="px-3 py-2"><Badge variant="outline" className={`text-[9px] ${tc.cls}`}>{tc.label}</Badge></td>
                          <td className="px-3 py-2 text-right text-xs font-mono">{formatPHP(inv.grand_total)}</td>
                          <td className="px-3 py-2 text-right font-semibold text-sm font-mono">{formatPHP(inv.balance)}</td>
                          <td className="px-3 py-2 text-right">
                            {canDiscount ? (
                              <div className="flex items-center gap-0.5 justify-end">
                                <button onClick={() => setDiscountModes(p => ({ ...p, [inv.id]: mode === 'amount' ? 'percent' : 'amount' }))}
                                  className="text-[9px] text-blue-500 hover:text-blue-700 font-medium w-5 text-center shrink-0" title="Toggle % / fixed">
                                  {mode === 'percent' ? '%' : '₱'}
                                </button>
                                <Input type="number" min="0" step="0.01" placeholder="0.00"
                                  className="h-7 w-20 text-right text-xs border-blue-200 bg-blue-50/50"
                                  value={rowDiscounts[inv.id] || ''}
                                  onChange={e => setRowDiscounts(p => ({ ...p, [inv.id]: e.target.value }))}
                                  onFocus={e => e.target.select()}
                                  data-testid={`discount-row-${inv.id}`} />
                                {discAmt > 0 && <span className="text-[9px] text-blue-600 ml-0.5">-{formatPHP(discAmt)}</span>}
                              </div>
                            ) : <span className="text-xs text-slate-300">—</span>}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Input type="number" min="0" max={inv.balance - discAmt} step="0.01" value={rowAmt} placeholder="0.00"
                              className={`h-8 w-28 text-right text-sm ml-auto font-mono ${isApplied ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'}`}
                              onChange={e => setRowAmounts(p => ({ ...p, [inv.id]: e.target.value }))}
                              onFocus={e => e.target.select()}
                              data-testid={`payment-row-${inv.id}`} />
                          </td>
                        </tr>
                      );
                    })}
                    {/* Totals row */}
                    <tr className="bg-slate-50 border-t-2 border-slate-200 font-semibold">
                      <td colSpan={3} className="px-3 py-2 text-right text-xs text-slate-500 uppercase">Totals</td>
                      <td className="px-3 py-2 text-right text-xs font-mono">{formatPHP(invoices.reduce((s, i) => s + (i.grand_total || 0), 0))}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono">{formatPHP(totalOpen)}</td>
                      <td className="px-3 py-2 text-right text-xs font-mono text-blue-600">{totalDiscount > 0 ? `-${formatPHP(totalDiscount)}` : '—'}</td>
                      <td className="px-3 py-2 text-right text-sm font-mono text-emerald-700">{formatPHP(totalApplied)}</td>
                    </tr>
                  </tbody>
                </table>
              </ScrollArea>
            )}
          </Card>

          {/* ═══════════ QB-STYLE FOOTER ═══════════ */}
          <Card className="border-slate-200 shrink-0">
            <CardContent className="p-4">
              <div className="flex items-end justify-between gap-6 flex-wrap">
                {/* Left: Memo */}
                <div className="flex-1 min-w-[200px] max-w-md">
                  <Label className="text-[10px] text-slate-400 uppercase tracking-wide">Memo</Label>
                  <Input value={payMemo} onChange={e => setPayMemo(e.target.value)}
                    placeholder="Optional note for this payment" className="h-9 mt-1" data-testid="payment-memo" />
                </div>

                {/* Right: Summary + Actions */}
                <div className="flex items-end gap-4">
                  {/* Amounts summary (QB-style) */}
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 min-w-[220px]" data-testid="payment-summary">
                    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Amounts for Selected Invoices</p>
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Amount Due</span>
                        <span className="font-mono font-medium">{formatPHP(totalOpen)}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Applied</span>
                        <span className="font-mono font-bold text-[#1A4D2E]">{formatPHP(totalApplied)}</span>
                      </div>
                      {totalDiscount > 0 && (
                        <div className="flex justify-between text-xs">
                          <span className="text-blue-600 flex items-center gap-1"><Tag size={10} /> Discount</span>
                          <span className="font-mono font-bold text-blue-600">{formatPHP(totalDiscount)}</span>
                        </div>
                      )}
                      <Separator className="my-1" />
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Remaining</span>
                        <span className="font-mono font-medium text-red-600">{formatPHP(Math.max(0, totalOpen - totalApplied - totalDiscount))}</span>
                      </div>
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex flex-col gap-2">
                    <Button onClick={handleApplyPayment} disabled={processing || !hasUnsavedAmounts}
                      className="h-10 px-6 bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="apply-payment-btn">
                      {processing ? 'Processing...' : 'Save & Apply'}
                    </Button>
                    <Button variant="outline" size="sm" className="text-xs" onClick={() => { setRowAmounts({}); setRowDiscounts({}); setDiscountModes({}); }}>
                      Clear
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Payment History Dialog ── */}
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Payment History — {selectedCustomer?.name}</DialogTitle>
            <DialogDescription>All payments received from this customer</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[420px]">
            <Table>
              <TableHeader><TableRow className="bg-slate-50">
                <TableHead className="text-xs">Date</TableHead>
                <TableHead className="text-xs">Invoice #</TableHead>
                <TableHead className="text-xs">Type</TableHead>
                <TableHead className="text-xs">Method</TableHead>
                <TableHead className="text-xs">Reference</TableHead>
                <TableHead className="text-xs text-right">Amount</TableHead>
                <TableHead className="text-xs">By</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {payHistory.length === 0 && (
                  <TableRow><TableCell colSpan={7} className="text-center py-6 text-slate-400">No payment history</TableCell></TableRow>
                )}
                {payHistory.map((p, i) => (
                  <TableRow key={i} className={p.method === 'Discount' ? 'bg-blue-50/40' : ''}>
                    <TableCell className="text-xs">{p.date}</TableCell>
                    <TableCell className="font-mono text-xs">{p.invoice_number}</TableCell>
                    <TableCell><Badge variant="outline" className={`text-[9px] ${getTypeConfig(p.sale_type).cls}`}>{getTypeConfig(p.sale_type).label}</Badge></TableCell>
                    <TableCell className="text-xs">
                      {p.method === 'Discount' ? <Badge className="text-[9px] bg-blue-100 text-blue-700">Discount</Badge> : p.method}
                    </TableCell>
                    <TableCell className="text-xs text-slate-400">{p.reference || '—'}</TableCell>
                    <TableCell className="text-right font-medium text-sm">{formatPHP(p.amount)}</TableCell>
                    <TableCell className="text-xs text-slate-400">{p.recorded_by}</TableCell>
                  </TableRow>
                ))}
                {payHistory.length > 0 && (
                  <TableRow className="bg-slate-50">
                    <TableCell colSpan={5} className="text-right text-xs font-semibold text-slate-500">Total Received</TableCell>
                    <TableCell className="text-right font-bold">{formatPHP(payHistory.reduce((s, p) => s + (p.amount || 0), 0))}</TableCell>
                    <TableCell />
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Invoice Detail Modal */}
      <SaleDetailModal
        open={invoiceModalOpen}
        onOpenChange={setInvoiceModalOpen}
        saleId={selectedInvoiceId}
        onUpdated={() => { if (selectedCustomer) { loadInvoices(selectedCustomer.id); loadChargesPreview(selectedCustomer.id); } }}
      />
    </div>
  );
}
