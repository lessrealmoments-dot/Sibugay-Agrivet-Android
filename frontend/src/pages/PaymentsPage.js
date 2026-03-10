import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Search, DollarSign, AlertTriangle, Percent, Receipt, Clock, Calculator,
  CheckSquare, Square, Info, ChevronDown, ChevronUp, Zap, Edit3
} from 'lucide-react';
import { toast } from 'sonner';
import SaleDetailModal from '../components/SaleDetailModal';

const METHODS = ['Cash', 'Check', 'Bank Transfer', 'GCash', 'Maya'];

const TYPE_CONFIG = {
  penalty_charge: { label: 'Penalty', cls: 'bg-red-100 text-red-700 border-red-200', priority: 1 },
  interest_charge: { label: 'Interest', cls: 'bg-amber-100 text-amber-700 border-amber-200', priority: 2 },
  farm_expense: { label: 'Farm', cls: 'bg-green-100 text-green-700 border-green-200', priority: 3 },
  cash_advance: { label: 'Customer Cash Out', cls: 'bg-purple-100 text-purple-700 border-purple-200', priority: 3 },
};
const getTypeConfig = (t) => TYPE_CONFIG[t] || { label: 'Invoice', cls: 'bg-slate-100 text-slate-700 border-slate-200', priority: 3 };

export default function PaymentsPage() {
  const { currentBranch } = useAuth();

  // Customer list
  const [customers, setCustomers] = useState([]);
  const [custSearch, setCustSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  // Open invoices
  const [invoices, setInvoices] = useState([]);

  // Per-row payment amounts: { [invoice_id]: amount_string }
  const [rowAmounts, setRowAmounts] = useState({});

  // Payment header
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payMethod, setPayMethod] = useState('Cash');
  const [payRef, setPayRef] = useState('');
  const [payMemo, setPayMemo] = useState('');

  // Interest/penalty
  const [chargesOpen, setChargesOpen] = useState(false);
  const [penaltyRate, setPenaltyRate] = useState(5);
  const [chargesPreview, setChargesPreview] = useState(null);
  const [generatingCharge, setGeneratingCharge] = useState(null); // 'interest' | 'penalty' | null

  // Payment history
  const [historyOpen, setHistoryOpen] = useState(false);
  const [payHistory, setPayHistory] = useState([]);

  // Invoice detail modal
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
    } catch { setInvoices([]); }
  }, []);

  const loadChargesPreview = useCallback(async (custId) => {
    try {
      const res = await api.get(`/customers/${custId}/charges-preview`, { params: { as_of_date: payDate } });
      setChargesPreview(res.data);
    } catch { setChargesPreview(null); }
  }, [payDate]);

  const selectCustomer = (c) => {
    setSelectedCustomer(c);
    setRowAmounts({});
    setPayRef('');
    setPayMemo('');
    loadInvoices(c.id);
    loadChargesPreview(c.id);
  };

  // Recalculate preview when date changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (selectedCustomer) loadChargesPreview(selectedCustomer.id);
  }, [payDate, selectedCustomer]);

  // ---- Calculations ----
  const totalApplied = invoices.reduce((s, inv) => {
    const v = parseFloat(rowAmounts[inv.id] || 0);
    return s + (isNaN(v) ? 0 : v);
  }, 0);

  const totalOpen = invoices.reduce((s, i) => s + (i.balance || 0), 0);
  const unapplied = Math.max(0, totalApplied); // if user enters a total, show what's unallocated

  // ---- Auto-apply: fill per-row amounts using penalty → interest → regular rule ----
  const autoApply = (totalAmt) => {
    const amt = parseFloat(totalAmt) || 0;
    if (amt <= 0) { setRowAmounts({}); return; }
    let remaining = amt;
    const newAmounts = {};
    // invoices are already sorted penalty → interest → regular (oldest first) by backend
    for (const inv of invoices) {
      if (remaining <= 0) break;
      const apply = Math.min(remaining, inv.balance);
      if (apply > 0) {
        newAmounts[inv.id] = apply.toFixed(2);
        remaining = Math.round((remaining - apply) * 100) / 100;
      }
    }
    setRowAmounts(newAmounts);
  };

  const setRowAmt = (invId, val) => {
    setRowAmounts(prev => ({ ...prev, [invId]: val }));
  };

  // ---- Generate Interest ----
  const handleGenerateInterest = async () => {
    setGeneratingCharge('interest');
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/generate-interest`, { as_of_date: payDate });
      if (res.data.total_interest > 0) {
        toast.success(`Interest invoice ${res.data.invoice_number} created — ${formatPHP(res.data.total_interest)}`);
        await loadInvoices(selectedCustomer.id);
        await loadChargesPreview(selectedCustomer.id);
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
      .map(inv => ({ invoice_id: inv.id, amount: parseFloat(rowAmounts[inv.id] || 0) }))
      .filter(a => a.amount > 0);

    if (allocations.length === 0) { toast.error('Enter payment amounts for at least one invoice'); return; }

    setProcessing(true);
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/receive-payment`, {
        allocations, method: payMethod, reference: payRef, date: payDate,
        branch_id: currentBranch?.id, memo: payMemo,
      });
      toast.success(`${formatPHP(res.data.total_applied)} applied to ${res.data.applied_invoices.length} invoice(s) — deposited to ${res.data.deposited_to}`);
      setRowAmounts({});
      setPayRef('');
      setPayMemo('');
      await loadInvoices(selectedCustomer.id);
      await loadChargesPreview(selectedCustomer.id);
      // Refresh customer balance
      const custRes = await api.get('/customers', { params: { limit: 500 } });
      const updated = (custRes.data.customers || []).find(c => c.id === selectedCustomer.id);
      if (updated) {
        setSelectedCustomer(updated);
        setCustomers(custRes.data.customers);
      }
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
    const diff = new Date(payDate) - new Date(dueDate);
    return Math.max(0, Math.floor(diff / 86400000));
  };

  const filteredCustomers = custSearch
    ? customers.filter(c => c.name.toLowerCase().includes(custSearch.toLowerCase()) || c.phone?.includes(custSearch))
    : customers;

  const hasUnsavedAmounts = Object.values(rowAmounts).some(v => parseFloat(v) > 0);

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 animate-fadeIn" data-testid="payments-page">

      {/* ── Left: Customer List ── */}
      <Card className="w-72 shrink-0 flex flex-col border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm" style={{ fontFamily: 'Manrope' }}>Customers with Balance</CardTitle>
          <div className="relative mt-1">
            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input value={custSearch} onChange={e => setCustSearch(e.target.value)}
              placeholder="Search..." className="pl-7 h-8 text-sm" data-testid="payment-customer-search" />
          </div>
        </CardHeader>
        <ScrollArea className="flex-1">
          {filteredCustomers.filter(c => c.balance > 0 || !custSearch).map(c => (
            <button key={c.id} data-testid={`pay-cust-${c.id}`} onClick={() => selectCustomer(c)}
              className={`w-full text-left px-4 py-2.5 border-b border-slate-50 hover:bg-slate-50 transition-colors ${selectedCustomer?.id === c.id ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E]' : ''}`}>
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm truncate">{c.name}</p>
                {c.balance > 0 && <span className="text-xs text-red-600 font-bold ml-2 shrink-0">{formatPHP(c.balance)}</span>}
              </div>
              <p className="text-[11px] text-slate-400">{c.price_scheme}{c.interest_rate > 0 ? ` · ${c.interest_rate}%/mo` : ''}</p>
            </button>
          ))}
          {filteredCustomers.length === 0 && (
            <p className="text-center text-slate-400 text-sm py-8">No customers found</p>
          )}
        </ScrollArea>
      </Card>

      {/* ── Right: Payment Form ── */}
      <div className="flex-1 flex flex-col gap-3 overflow-y-auto min-w-0">
        {!selectedCustomer ? (
          <Card className="flex-1 border-slate-200 flex items-center justify-center">
            <div className="text-center">
              <DollarSign size={48} className="mx-auto text-slate-200 mb-3" />
              <p className="text-slate-400">Select a customer to receive payment</p>
            </div>
          </Card>
        ) : (
          <>
            {/* ── 1. Payment Header ── */}
            <Card className="border-slate-200 shrink-0">
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>{selectedCustomer.name}</h2>
                    <p className="text-xs text-slate-500">
                      {selectedCustomer.phone && `${selectedCustomer.phone} · `}
                      Grace: {selectedCustomer.grace_period || 7} days
                      {selectedCustomer.interest_rate > 0 && ` · Interest: ${selectedCustomer.interest_rate}%/mo`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] text-slate-400 uppercase">Total Balance Due</p>
                    <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalOpen)}</p>
                  </div>
                </div>

                {/* QB-style header fields */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <Label className="text-xs text-slate-500">Payment Date</Label>
                    <Input type="date" value={payDate} onChange={e => setPayDate(e.target.value)} className="h-9" />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Method</Label>
                    <Select value={payMethod} onValueChange={setPayMethod}>
                      <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>{METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Check # / Reference</Label>
                    <Input value={payRef} onChange={e => setPayRef(e.target.value)} placeholder="Check #, OR #..." className="h-9" />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Memo</Label>
                    <Input value={payMemo} onChange={e => setPayMemo(e.target.value)} placeholder="Optional note" className="h-9" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ── 2. Charges Generation (Collapsible) ── */}
            <Card className="border-slate-200 shrink-0">
              <button className="w-full" onClick={() => setChargesOpen(o => !o)}>
                <CardContent className="p-3 flex items-center justify-between hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-2">
                    <Calculator size={15} className="text-amber-500" />
                    <span className="text-sm font-medium">Generate Interest / Penalty Charges</span>
                    {chargesPreview?.total_interest > 0 && (
                      <Badge className="text-[10px] bg-amber-100 text-amber-700">
                        ~{formatPHP(chargesPreview.total_interest)} accrued
                      </Badge>
                    )}
                  </div>
                  {chargesOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </CardContent>
              </button>
              {chargesOpen && (
                <div className="px-4 pb-4 space-y-4 border-t border-slate-100">
                  {/* Interest preview */}
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
                    <div className="flex-1 min-w-[200px]">
                      <p className="text-xs text-slate-500 mb-1">
                        Grace period: <strong>{selectedCustomer.grace_period || 7} days</strong>
                      </p>
                      {selectedCustomer.interest_rate > 0 ? (
                        <p className="text-xs text-slate-500">
                          Customer interest rate: <strong className="text-amber-600">{selectedCustomer.interest_rate}%/month</strong>
                          {' '}— click "Generate Interest" to create an INT- invoice
                        </p>
                      ) : (
                        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 flex items-center gap-1">
                          <AlertTriangle size={11} /> No interest rate on this customer's profile.
                          Go to <strong>Customers → Edit</strong> and set an interest rate to use this feature.
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Button size="sm" variant="outline" onClick={handleGenerateInterest}
                        disabled={!!generatingCharge || !selectedCustomer.interest_rate}
                        className="text-amber-600 border-amber-200 hover:bg-amber-50 gap-1 disabled:opacity-40" data-testid="generate-interest-btn">
                        <Percent size={13} /> {generatingCharge === 'interest' ? 'Generating...' : 'Generate Interest'}
                      </Button>
                      <Separator orientation="vertical" className="h-7" />
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-slate-500 whitespace-nowrap">Penalty %:</span>
                        <div className="flex items-center gap-0.5 bg-slate-100 rounded-md px-2 py-1.5">
                          <Input type="number" value={penaltyRate} onChange={e => setPenaltyRate(parseFloat(e.target.value) || 0)}
                            className="w-12 h-6 text-xs text-center border-0 bg-transparent p-0" />
                          <span className="text-xs text-slate-500">%</span>
                        </div>
                      </div>
                      <Button size="sm" variant="outline" onClick={handleGeneratePenalty} disabled={!!generatingCharge}
                        className="text-red-600 border-red-200 hover:bg-red-50 gap-1" data-testid="generate-penalty-btn">
                        <AlertTriangle size={13} /> {generatingCharge === 'penalty' ? 'Generating...' : 'Apply Penalty'}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* ── 3. Outstanding Transactions Table ── */}
            <Card className="border-slate-200 flex-1 min-h-0">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-sm" style={{ fontFamily: 'Manrope' }}>Outstanding Transactions</CardTitle>
                    {invoices.length > 0 && (
                      <button onClick={() => autoApply(totalOpen)} className="text-xs text-[#1A4D2E] hover:underline flex items-center gap-1 font-medium">
                        <Zap size={11} /> Auto-apply all
                      </button>
                    )}
                  </div>
                  <Button variant="ghost" size="sm" className="text-xs gap-1" onClick={loadHistory}>
                    <Clock size={12} /> History
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {invoices.length === 0 ? (
                  <div className="py-12 text-center text-slate-400">
                    <Receipt size={40} className="mx-auto mb-3 opacity-20" />
                    <p>No open invoices for this customer</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="invoices-table">
                      <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                        <tr>
                          <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Date</th>
                          <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Invoice #</th>
                          <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Type</th>
                          <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Due</th>
                          <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Orig. Amt</th>
                          <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Paid</th>
                          <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Balance Due</th>
                          <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase w-32">
                            Payment ↓
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoices.map((inv, idx) => {
                          const tc = getTypeConfig(inv.sale_type);
                          const daysOver = getDaysOverdue(inv.due_date);
                          const graceP = selectedCustomer?.grace_period || 7;
                          const isOverdue = daysOver > graceP && inv.balance > 0;
                          const rowAmt = rowAmounts[inv.id] || '';
                          const isApplied = parseFloat(rowAmt) > 0;

                          return (
                            <tr key={inv.id} className={`border-b border-slate-100 ${isApplied ? 'bg-emerald-50/40' : 'hover:bg-slate-50/50'} transition-colors`}>
                              <td className="px-3 py-2 text-xs text-slate-500">{inv.order_date}</td>
                              <td className="px-3 py-2">
                                <button className="font-mono text-xs text-blue-600 hover:underline flex items-center gap-1"
                                  onClick={() => { setSelectedInvoiceId(inv.id); setInvoiceModalOpen(true); }}>
                                  {inv.invoice_number}
                                  {inv.edited && <Edit3 size={9} className="text-orange-400" />}
                                </button>
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant="outline" className={`text-[10px] ${tc.cls}`}>{tc.label}</Badge>
                              </td>
                              <td className="px-3 py-2">
                                <div className="text-xs">
                                  <span className={isOverdue ? 'text-red-600 font-semibold' : 'text-slate-500'}>
                                    {inv.due_date || '—'}
                                  </span>
                                  {isOverdue && (
                                    <Badge className="ml-1 text-[9px] bg-red-100 text-red-700">{daysOver}d overdue</Badge>
                                  )}
                                  {daysOver > 0 && daysOver <= graceP && (
                                    <Badge className="ml-1 text-[9px] bg-yellow-100 text-yellow-700">Grace {daysOver}d</Badge>
                                  )}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-right text-xs">{formatPHP(inv.grand_total)}</td>
                              <td className="px-3 py-2 text-right text-xs text-slate-500">{formatPHP(inv.amount_paid || 0)}</td>
                              <td className="px-3 py-2 text-right font-semibold text-sm">{formatPHP(inv.balance)}</td>
                              <td className="px-3 py-2 text-right">
                                <Input
                                  type="number"
                                  data-testid={`payment-row-${inv.id}`}
                                  className={`h-8 w-28 text-right text-sm ml-auto ${isApplied ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'}`}
                                  value={rowAmt}
                                  placeholder="0.00"
                                  min="0"
                                  max={inv.balance}
                                  step="0.01"
                                  onChange={e => setRowAmt(inv.id, e.target.value)}
                                  onFocus={e => e.target.select()}
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* ── Footer: Totals + Apply ── */}
                {invoices.length > 0 && (
                  <div className="border-t border-slate-200 p-4 bg-slate-50/80">
                    <div className="flex items-end justify-between gap-4 flex-wrap">
                      {/* Left: Quick enter total + auto-apply */}
                      <div className="flex items-center gap-2">
                        <div>
                          <Label className="text-xs text-slate-500">Enter Total Amount</Label>
                          <div className="flex items-center gap-2">
                            <Input
                              data-testid="receive-amount"
                              type="number"
                              placeholder="0.00"
                              className="h-10 w-36 text-lg font-bold"
                              onChange={e => autoApply(e.target.value)}
                            />
                            <Button variant="outline" size="sm" onClick={() => autoApply(totalOpen)} className="gap-1 shrink-0">
                              <Zap size={13} /> Pay All {formatPHP(totalOpen)}
                            </Button>
                          </div>
                        </div>
                      </div>

                      {/* Right: Allocation summary + Apply button */}
                      <div className="flex items-center gap-4">
                        <div className="text-right space-y-0.5">
                          <div className="flex justify-between gap-6 text-sm">
                            <span className="text-slate-500">Amount to Apply</span>
                            <span className="font-bold text-[#1A4D2E]">{formatPHP(totalApplied)}</span>
                          </div>
                          <div className="flex justify-between gap-6 text-xs text-slate-400">
                            <span>Total Balance Due</span>
                            <span>{formatPHP(totalOpen)}</span>
                          </div>
                          {totalApplied > totalOpen && (
                            <p className="text-[10px] text-amber-600 flex items-center gap-1">
                              <AlertTriangle size={9} /> Amount exceeds balance due
                            </p>
                          )}
                        </div>
                        <Button
                          data-testid="apply-payment-btn"
                          onClick={handleApplyPayment}
                          disabled={processing || !hasUnsavedAmounts}
                          className="h-10 px-6 bg-[#1A4D2E] hover:bg-[#14532d] text-white shrink-0"
                        >
                          {processing ? 'Processing...' : 'Save & Apply Payment'}
                        </Button>
                      </div>
                    </div>

                    {/* Allocation preview */}
                    {hasUnsavedAmounts && (
                      <div className="mt-3 pt-3 border-t border-slate-200">
                        <p className="text-[11px] text-slate-500 font-medium mb-1.5">Allocation Preview:</p>
                        <div className="flex flex-wrap gap-2">
                          {invoices.filter(inv => parseFloat(rowAmounts[inv.id] || 0) > 0).map(inv => {
                            const tc = getTypeConfig(inv.sale_type);
                            return (
                              <div key={inv.id} className="flex items-center gap-1.5 bg-white border border-slate-200 rounded px-2 py-1 text-xs">
                                <Badge variant="outline" className={`text-[9px] ${tc.cls}`}>{tc.label}</Badge>
                                <span className="font-mono text-slate-500">{inv.invoice_number}</span>
                                <span className="font-bold text-emerald-600">{formatPHP(parseFloat(rowAmounts[inv.id]))}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>

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
                  <TableRow key={i}>
                    <TableCell className="text-xs">{p.date}</TableCell>
                    <TableCell className="font-mono text-xs">{p.invoice_number}</TableCell>
                    <TableCell><Badge variant="outline" className={`text-[9px] ${getTypeConfig(p.sale_type).cls}`}>{getTypeConfig(p.sale_type).label}</Badge></TableCell>
                    <TableCell className="text-xs">{p.method}</TableCell>
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
