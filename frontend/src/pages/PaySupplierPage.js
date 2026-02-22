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
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import {
  Search, AlertTriangle, Zap, Building2, FileText, CheckCircle2,
  Wallet, Shield, Info, ChevronRight, Clock, Package
} from 'lucide-react';
import { toast } from 'sonner';

const METHODS = ['Cash', 'Check', 'Bank Transfer', 'GCash'];

export default function PaySupplierPage() {
  const { currentBranch } = useAuth();

  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null); // selected supplier object
  const [rowAmounts, setRowAmounts] = useState({});

  // Payment form
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payMethod, setPayMethod] = useState('Cash');
  const [checkNumber, setCheckNumber] = useState('');
  const [checkDate, setCheckDate] = useState('');
  const [reference, setReference] = useState('');
  const [fundSource, setFundSource] = useState('cashier');

  // Fund balances
  const [cashierBalance, setCashierBalance] = useState(0);
  const [safeBalance, setSafeBalance] = useState(0);

  // PO detail dialog
  const [poDetailDialog, setPoDetailDialog] = useState(false);
  const [poDetail, setPoDetail] = useState(null);

  const [processing, setProcessing] = useState(false);

  const today = new Date().toISOString().slice(0, 10);
  const soon = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);

  const loadSuppliers = useCallback(async () => {
    try {
      const params = currentBranch ? { branch_id: currentBranch.id } : {};
      const res = await api.get('/purchase-orders/payables-by-supplier', { params });
      setSuppliers(res.data || []);
    } catch { toast.error('Failed to load suppliers'); }
  }, [currentBranch]);

  const loadFundBalances = useCallback(async () => {
    if (!currentBranch?.id) return;
    try {
      const res = await api.get('/fund-wallets', { params: { branch_id: currentBranch.id } });
      const wallets = res.data || [];
      const cashier = wallets.find(w => w.type === 'cashier');
      const safe = wallets.find(w => w.type === 'safe');
      setCashierBalance(cashier?.balance || 0);
      setSafeBalance(safe?.balance || 0);
    } catch {}
  }, [currentBranch]);

  useEffect(() => {
    loadSuppliers();
    loadFundBalances();
  }, [loadSuppliers, loadFundBalances]);

  const selectSupplier = (sup) => {
    setSelected(sup);
    setRowAmounts({});
  };

  const totalApplied = Object.values(rowAmounts).reduce((s, v) => s + (parseFloat(v) || 0), 0);
  const currentFundBalance = fundSource === 'safe' ? safeBalance : cashierBalance;
  const isShort = totalApplied > currentFundBalance && totalApplied > 0;
  const shortfall = Math.max(0, totalApplied - currentFundBalance);

  const autoPayAll = () => {
    if (!selected) return;
    const newAmounts = {};
    selected.pos.forEach(po => {
      const bal = po.balance ?? po.subtotal ?? 0;
      if (bal > 0) newAmounts[po.id] = bal.toFixed(2);
    });
    setRowAmounts(newAmounts);
  };

  const getDueStatus = (dueDate) => {
    if (!dueDate) return null;
    if (dueDate < today) return { label: 'Overdue', cls: 'bg-red-100 text-red-700 border-red-200' };
    if (dueDate <= soon) return { label: 'Due Soon', cls: 'bg-amber-100 text-amber-700 border-amber-200' };
    return { label: `Due ${dueDate}`, cls: 'bg-slate-100 text-slate-600' };
  };

  const handlePayment = async () => {
    const allocations = selected.pos
      .filter(po => parseFloat(rowAmounts[po.id] || 0) > 0)
      .map(po => ({ po_id: po.id, amount: parseFloat(rowAmounts[po.id]) }));

    if (allocations.length === 0) { toast.error('Enter payment amounts first'); return; }
    if (payMethod === 'Check' && !checkNumber) { toast.error('Check number is required for Check payments'); return; }
    if (!currentBranch?.id) { toast.error('Select a specific branch first'); return; }

    setProcessing(true);
    let totalPaid = 0, errors = [];

    for (const alloc of allocations) {
      try {
        await api.post(`/purchase-orders/${alloc.po_id}/pay`, {
          amount: alloc.amount,
          fund_source: fundSource,
          method: payMethod,
          check_number: checkNumber,
          check_date: checkDate,
          reference: reference,
          payment_date: payDate,
        });
        totalPaid += alloc.amount;
      } catch (e) {
        const detail = e.response?.data?.detail;
        if (typeof detail === 'object' && detail?.type === 'insufficient_funds') {
          toast.error(`${detail.message} Safe: ₱${detail.safe_balance?.toFixed(2)}`);
          setProcessing(false);
          return;
        }
        errors.push(detail || 'Payment failed');
      }
    }

    if (errors.length) {
      toast.error(`${errors.length} payment(s) failed: ${errors[0]}`);
    } else {
      toast.success(`₱${totalPaid.toFixed(2)} paid to ${selected.vendor} from ${fundSource}`);
    }

    setRowAmounts({});
    setCheckNumber('');
    setReference('');
    await loadSuppliers();
    await loadFundBalances();

    // Refresh selected supplier data
    const refreshed = (await api.get('/purchase-orders/payables-by-supplier', {
      params: currentBranch ? { branch_id: currentBranch.id } : {}
    }).then(r => r.data || []).catch(() => [])).find(s => s.vendor === selected.vendor);
    setSelected(refreshed || null);
    setProcessing(false);
  };

  const filteredSuppliers = search
    ? suppliers.filter(s => s.vendor.toLowerCase().includes(search.toLowerCase()))
    : suppliers;

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 animate-fadeIn" data-testid="pay-supplier-page">

      {/* ── Left: Supplier List ── */}
      <Card className="w-72 shrink-0 flex flex-col border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm" style={{ fontFamily: 'Manrope' }}>Suppliers with Balance</CardTitle>
          <div className="relative mt-1">
            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="pl-7 h-8 text-sm" />
          </div>
        </CardHeader>
        <ScrollArea className="flex-1">
          {filteredSuppliers.map(s => (
            <button key={s.vendor} onClick={() => selectSupplier(s)}
              className={`w-full text-left px-4 py-2.5 border-b border-slate-50 hover:bg-slate-50 transition-colors ${selected?.vendor === s.vendor ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E]' : ''}`}>
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm truncate">{s.vendor}</p>
                <span className="text-xs font-bold text-red-600 ml-1">{formatPHP(s.total_owed)}</span>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[11px] text-slate-400">{s.pos.length} PO{s.pos.length !== 1 ? 's' : ''}</span>
                {s.has_overdue && <Badge className="text-[9px] bg-red-100 text-red-700 px-1">Overdue</Badge>}
              </div>
            </button>
          ))}
          {filteredSuppliers.length === 0 && (
            <p className="text-center text-sm text-slate-400 py-8">No unpaid POs</p>
          )}
        </ScrollArea>
      </Card>

      {/* ── Right: Payment Panel ── */}
      {!selected ? (
        <Card className="flex-1 border-slate-200 flex items-center justify-center">
          <div className="text-center">
            <Building2 size={48} className="mx-auto text-slate-200 mb-3" />
            <p className="text-slate-400">Select a supplier to pay</p>
          </div>
        </Card>
      ) : (
        <div className="flex-1 flex flex-col gap-3 overflow-y-auto min-w-0">

          {/* ── Header ── */}
          <Card className="border-slate-200 shrink-0">
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>{selected.vendor}</h2>
                  <p className="text-xs text-slate-500">{selected.pos.length} open purchase order{selected.pos.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right">
                  <p className="text-[11px] text-slate-400 uppercase">Total Owed</p>
                  <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(selected.total_owed)}</p>
                </div>
              </div>

              {/* Fund Source Selection */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
                {[
                  { key: 'cashier', label: 'Cashier', balance: cashierBalance, icon: Wallet },
                  { key: 'safe', label: 'Safe', balance: safeBalance, icon: Shield },
                ].map(fund => (
                  <button key={fund.key} onClick={() => setFundSource(fund.key)}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${fundSource === fund.key ? 'border-[#1A4D2E] bg-[#1A4D2E]/5' : 'border-slate-200 hover:border-slate-300'}`}>
                    <fund.icon size={15} className={fundSource === fund.key ? 'text-[#1A4D2E]' : 'text-slate-400'} />
                    <div>
                      <p className="text-xs font-medium">{fund.label}</p>
                      <p className={`text-[11px] font-bold ${fund.balance < totalApplied && totalApplied > 0 ? 'text-red-500' : 'text-slate-600'}`}>{formatPHP(fund.balance)}</p>
                    </div>
                  </button>
                ))}
              </div>

              {/* Cashier insufficient warning */}
              {isShort && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 flex items-start gap-2">
                  <AlertTriangle size={15} className="text-amber-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-700">Insufficient {fundSource === 'cashier' ? 'Cashier' : 'Safe'} Balance</p>
                    <p className="text-xs text-amber-600">
                      {fundSource === 'cashier'
                        ? `Cashier has ₱${cashierBalance.toFixed(2)}, short by ₱${shortfall.toFixed(2)}. ${safeBalance >= totalApplied ? 'Switch to Safe to cover full payment.' : 'Check both Cashier and Safe balances.'}`
                        : `Safe has ₱${safeBalance.toFixed(2)}, short by ₱${shortfall.toFixed(2)}.`}
                    </p>
                  </div>
                </div>
              )}

              {/* Payment Header Fields */}
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
                  <Label className="text-xs text-slate-500">{payMethod === 'Check' ? 'Check # *' : 'Reference #'}</Label>
                  <Input value={checkNumber} onChange={e => setCheckNumber(e.target.value)}
                    placeholder={payMethod === 'Check' ? 'Required' : 'Optional'} className="h-9"
                    data-testid="check-number-input" />
                </div>
                {payMethod === 'Check' && (
                  <div>
                    <Label className="text-xs text-slate-500">Check Date</Label>
                    <Input type="date" value={checkDate} onChange={e => setCheckDate(e.target.value)} className="h-9" />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* ── PO Table ── */}
          <Card className="border-slate-200 flex-1 min-h-0">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm" style={{ fontFamily: 'Manrope' }}>Open Purchase Orders</CardTitle>
                <button onClick={autoPayAll} className="text-xs text-[#1A4D2E] hover:underline flex items-center gap-1 font-medium">
                  <Zap size={11} /> Pay All {formatPHP(selected.total_owed)}
                </button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="po-table">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">PO #</th>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Date</th>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">DR #</th>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Status</th>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Due</th>
                      <th className="text-left px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Items</th>
                      <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Grand Total</th>
                      <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Paid</th>
                      <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase">Balance</th>
                      <th className="text-right px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase w-32">Payment ↓</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.pos.map(po => {
                      const balance = po.balance ?? po.subtotal ?? 0;
                      const dueStatus = getDueStatus(po.due_date);
                      const rowAmt = rowAmounts[po.id] || '';
                      const isApplied = parseFloat(rowAmt) > 0;
                      const itemsSummary = po.items?.slice(0, 2).map(i => i.product_name).join(', ') || '—';

                      return (
                        <tr key={po.id} className={`border-b border-slate-100 ${isApplied ? 'bg-emerald-50/40' : 'hover:bg-slate-50/50'} transition-colors`}>
                          <td className="px-3 py-2">
                            <button className="font-mono text-xs text-blue-600 hover:underline"
                              onClick={() => { setPoDetail(po); setPoDetailDialog(true); }}>
                              {po.po_number}
                            </button>
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500">{po.purchase_date}</td>
                          <td className="px-3 py-2 text-xs text-slate-400 font-mono">{po.dr_number || '—'}</td>
                          <td className="px-3 py-2">
                            <Badge className={`text-[9px] ${po.status === 'received' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'}`}>
                              {po.status === 'received' ? 'Received' : 'Pending'}
                            </Badge>
                          </td>
                          <td className="px-3 py-2">
                            {dueStatus ? (
                              <Badge variant="outline" className={`text-[9px] ${dueStatus.cls}`}>{dueStatus.label}</Badge>
                            ) : <span className="text-[11px] text-slate-400">—</span>}
                          </td>
                          <td className="px-3 py-2 text-xs text-slate-500 max-w-[140px] truncate">{itemsSummary}</td>
                          <td className="px-3 py-2 text-right text-xs">{formatPHP(po.grand_total || po.subtotal)}</td>
                          <td className="px-3 py-2 text-right text-xs text-slate-500">{formatPHP(po.amount_paid || 0)}</td>
                          <td className="px-3 py-2 text-right font-semibold text-sm">{formatPHP(balance)}</td>
                          <td className="px-3 py-2 text-right">
                            <Input type="number"
                              className={`h-8 w-28 text-right text-sm ml-auto ${isApplied ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'}`}
                              value={rowAmt} placeholder="0.00" min="0" max={balance} step="0.01"
                              data-testid={`pay-row-${po.id}`}
                              onChange={e => setRowAmounts(prev => ({ ...prev, [po.id]: e.target.value }))}
                              onFocus={e => e.target.select()}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Footer */}
              <div className="border-t border-slate-200 p-4 bg-slate-50/80">
                <div className="flex items-end justify-between gap-4 flex-wrap">
                  <div className="flex items-center gap-2">
                    <div>
                      <Label className="text-xs text-slate-500">Enter Total</Label>
                      <div className="flex items-center gap-2">
                        <Input type="number" placeholder="0.00" className="h-10 w-36 text-lg font-bold"
                          onChange={e => {
                            const amt = parseFloat(e.target.value) || 0;
                            let rem = amt;
                            const newAmounts = {};
                            for (const po of selected.pos) {
                              if (rem <= 0) break;
                              const bal = po.balance ?? po.subtotal ?? 0;
                              const apply = Math.min(rem, bal);
                              if (apply > 0) { newAmounts[po.id] = apply.toFixed(2); rem -= apply; }
                            }
                            setRowAmounts(newAmounts);
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right space-y-0.5">
                      <div className="flex justify-between gap-6 text-sm">
                        <span className="text-slate-500">Total Payment</span>
                        <span className={`font-bold ${isShort ? 'text-red-600' : 'text-[#1A4D2E]'}`}>{formatPHP(totalApplied)}</span>
                      </div>
                      <div className="flex justify-between gap-6 text-xs text-slate-400">
                        <span>Fund: {fundSource === 'cashier' ? 'Cashier' : 'Safe'} ({formatPHP(currentFundBalance)} available)</span>
                      </div>
                    </div>
                    <Button data-testid="save-payment-btn"
                      onClick={handlePayment}
                      disabled={processing || totalApplied <= 0 || isShort}
                      className="h-10 px-6 bg-[#1A4D2E] hover:bg-[#14532d] text-white shrink-0 disabled:opacity-40">
                      {processing ? 'Processing...' : 'Save & Pay'}
                    </Button>
                  </div>
                </div>

                {/* Allocation chips */}
                {Object.entries(rowAmounts).some(([, v]) => parseFloat(v) > 0) && (
                  <div className="mt-3 pt-3 border-t border-slate-200">
                    <p className="text-[11px] text-slate-500 font-medium mb-1.5">Payment Allocation:</p>
                    <div className="flex flex-wrap gap-2">
                      {selected.pos.filter(po => parseFloat(rowAmounts[po.id] || 0) > 0).map(po => (
                        <div key={po.id} className="flex items-center gap-1.5 bg-white border border-slate-200 rounded px-2 py-1 text-xs">
                          <FileText size={10} className="text-slate-400" />
                          <span className="font-mono text-slate-500">{po.po_number}</span>
                          <span className="font-bold text-emerald-600">{formatPHP(parseFloat(rowAmounts[po.id]))}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* PO Detail Dialog */}
      <Dialog open={poDetailDialog} onOpenChange={setPoDetailDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>PO Details — {poDetail?.po_number}</DialogTitle>
            <DialogDescription>{poDetail?.vendor} · {poDetail?.purchase_date}</DialogDescription>
          </DialogHeader>
          {poDetail && (
            <div className="space-y-4">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="text-left px-2 py-1.5 text-xs text-slate-500">Product</th>
                    <th className="text-right px-2 py-1.5 text-xs text-slate-500">Qty</th>
                    <th className="text-right px-2 py-1.5 text-xs text-slate-500">Unit Price</th>
                    <th className="text-right px-2 py-1.5 text-xs text-slate-500">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {poDetail.items?.map((item, i) => (
                    <tr key={i} className="border-b border-slate-100">
                      <td className="px-2 py-1.5 font-medium">{item.product_name}</td>
                      <td className="px-2 py-1.5 text-right">{item.quantity}</td>
                      <td className="px-2 py-1.5 text-right">{formatPHP(item.unit_price)}</td>
                      <td className="px-2 py-1.5 text-right font-semibold">{formatPHP(item.total || item.quantity * item.unit_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex justify-between font-bold text-lg border-t pt-2">
                <span>Total</span>
                <span>{formatPHP(poDetail.subtotal)}</span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3 grid grid-cols-3 gap-3 text-sm">
                <div><p className="text-xs text-slate-400">Paid</p><p className="font-bold text-emerald-600">{formatPHP(poDetail.amount_paid || 0)}</p></div>
                <div><p className="text-xs text-slate-400">Balance</p><p className="font-bold text-red-600">{formatPHP(poDetail.balance ?? poDetail.subtotal)}</p></div>
                <div><p className="text-xs text-slate-400">Status</p>
                  <Badge className={`text-[10px] ${poDetail.status === 'received' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'}`}>
                    {poDetail.status}
                  </Badge>
                </div>
              </div>
              {poDetail.notes && <p className="text-xs text-slate-500 bg-slate-50 p-2 rounded">{poDetail.notes}</p>}
              {(poDetail.payment_history || []).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-2">Payment History</p>
                  {poDetail.payment_history.map((p, i) => (
                    <div key={i} className="flex justify-between text-xs py-1 border-b border-slate-100">
                      <span>{p.date} — {p.method}{p.check_number ? ` #${p.check_number}` : ''}</span>
                      <span className="font-medium">{formatPHP(p.amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
