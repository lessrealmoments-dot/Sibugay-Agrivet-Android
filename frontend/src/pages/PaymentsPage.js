import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { DollarSign, Search, AlertTriangle, Percent, Receipt, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

export default function PaymentsPage() {
  const { currentBranch } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [search, setSearch] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('Cash');
  const [payRef, setPayRef] = useState('');
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [allocations, setAllocations] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [penaltyRate, setPenaltyRate] = useState(5);
  const [payHistory, setPayHistory] = useState([]);

  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
  }, []);

  const loadInvoices = async (custId) => {
    try {
      const res = await api.get(`/customers/${custId}/invoices`);
      setInvoices(res.data);
    } catch { setInvoices([]); }
    try {
      const res = await api.get(`/customers/${custId}/payment-history`);
      setPayHistory(res.data);
    } catch { setPayHistory([]); }
  };

  const selectCustomer = (c) => {
    setSelectedCustomer(c);
    loadInvoices(c.id);
    setPayAmount('');
    setAllocations([]);
  };

  const filteredCustomers = search
    ? customers.filter(c => c.name.toLowerCase().includes(search.toLowerCase()) || c.phone?.includes(search))
    : customers;

  const totalOpen = invoices.reduce((s, i) => s + (i.balance || 0), 0);
  const interestInvoices = invoices.filter(i => i.sale_type === 'interest_charge');
  const penaltyInvoices = invoices.filter(i => i.sale_type === 'penalty_charge');
  const regularInvoices = invoices.filter(i => !['interest_charge', 'penalty_charge'].includes(i.sale_type));

  // Preview allocation when amount changes
  const previewAllocation = (amt) => {
    const amount = parseFloat(amt) || 0;
    if (amount <= 0) { setAllocations([]); return; }
    const sorted = [...interestInvoices, ...penaltyInvoices, ...regularInvoices.sort((a, b) => (a.order_date || '').localeCompare(b.order_date || ''))];
    let remaining = amount;
    const allocs = [];
    for (const inv of sorted) {
      if (remaining <= 0) break;
      const apply = Math.min(remaining, inv.balance);
      allocs.push({ invoice: inv.invoice_number, type: inv.sale_type || 'regular', applied: apply, balance_after: Math.round((inv.balance - apply) * 100) / 100 });
      remaining = Math.round((remaining - apply) * 100) / 100;
    }
    setAllocations(allocs);
  };

  const handleGenerateInterest = async () => {
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/generate-interest`, { as_of_date: payDate });
      if (res.data.total_interest > 0) {
        toast.success(`Interest invoice created: ${res.data.invoice_number} for ${formatPHP(res.data.total_interest)}`);
        loadInvoices(selectedCustomer.id);
      } else { toast(res.data.message); }
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleGeneratePenalty = async () => {
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/generate-penalty`, { penalty_rate: penaltyRate, as_of_date: payDate });
      if (res.data.total_penalty > 0) {
        toast.success(`Penalty invoice created: ${res.data.invoice_number} for ${formatPHP(res.data.total_penalty)}`);
        loadInvoices(selectedCustomer.id);
      } else { toast(res.data.message); }
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleReceivePayment = async () => {
    const amount = parseFloat(payAmount);
    if (!amount || amount <= 0) { toast.error('Enter a valid amount'); return; }
    setProcessing(true);
    try {
      const res = await api.post(`/customers/${selectedCustomer.id}/receive-payment`, {
        amount, method: payMethod, reference: payRef, date: payDate,
      });
      const msg = res.data.allocations.map(a => `${a.invoice}: ${formatPHP(a.applied)}`).join(', ');
      toast.success(`Payment applied! ${msg}`);
      setPayAmount('');
      setAllocations([]);
      loadInvoices(selectedCustomer.id);
      // Refresh customer list for updated balance
      api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
    setProcessing(false);
  };

  const typeLabel = (t) => {
    if (t === 'interest_charge') return { text: 'Interest', cls: 'bg-amber-100 text-amber-700' };
    if (t === 'penalty_charge') return { text: 'Penalty', cls: 'bg-red-100 text-red-700' };
    if (t === 'farm_expense') return { text: 'Farm', cls: 'bg-green-100 text-green-700' };
    return { text: 'Invoice', cls: 'bg-blue-100 text-blue-700' };
  };

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="payments-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Receive Payments</h1>
        <p className="text-sm text-slate-500">QuickBooks-style payment application — interest & penalty first, then oldest invoice</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        {/* Customer List */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Customer</CardTitle>
            <div className="relative mt-2">
              <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input data-testid="payment-customer-search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search customer..." className="pl-8 h-9" />
            </div>
          </CardHeader>
          <CardContent className="p-0 max-h-[500px] overflow-y-auto">
            {filteredCustomers.map(c => (
              <button key={c.id} data-testid={`pay-cust-${c.id}`} onClick={() => selectCustomer(c)}
                className={`w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors ${selectedCustomer?.id === c.id ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E]' : ''}`}>
                <p className="font-medium text-sm">{c.name}</p>
                <p className="text-xs text-slate-400">{c.phone || 'No phone'} &middot; {c.price_scheme}</p>
                {c.balance > 0 && <p className="text-xs text-red-500 font-semibold mt-0.5">Owes: {formatPHP(c.balance)}</p>}
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Main Content */}
        <div className="lg:col-span-2 space-y-4">
          {selectedCustomer ? (
            <>
              {/* Customer Header + Payment Form */}
              <Card className="border-slate-200">
                <CardContent className="p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>{selectedCustomer.name}</h2>
                      <p className="text-xs text-slate-500">{selectedCustomer.phone} &middot; {selectedCustomer.price_scheme} &middot; Interest Rate: {selectedCustomer.interest_rate || 0}%/mo</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-slate-500 uppercase">Total Open Balance</p>
                      <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalOpen)}</p>
                    </div>
                  </div>

                  {invoices.length > 0 && (
                    <>
                      <Separator />
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <Label className="text-xs">Amount Received</Label>
                          <Input data-testid="receive-amount" type="number" value={payAmount}
                            onChange={e => { setPayAmount(e.target.value); previewAllocation(e.target.value); }}
                            placeholder="0.00" className="h-11 text-lg font-bold" />
                        </div>
                        <div>
                          <Label className="text-xs">Payment Date</Label>
                          <Input type="date" value={payDate} onChange={e => setPayDate(e.target.value)} className="h-11" />
                        </div>
                        <div>
                          <Label className="text-xs">Check # / Reference</Label>
                          <Input value={payRef} onChange={e => setPayRef(e.target.value)} placeholder="Check #, ref..." className="h-11" />
                        </div>
                        <div>
                          <Label className="text-xs">Method</Label>
                          <Select value={payMethod} onValueChange={setPayMethod}>
                            <SelectTrigger className="h-11"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Cash">Cash</SelectItem>
                              <SelectItem value="Check">Check</SelectItem>
                              <SelectItem value="Bank Transfer">Bank Transfer</SelectItem>
                              <SelectItem value="GCash">GCash</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* Allocation Preview */}
                      {allocations.length > 0 && (
                        <div className="bg-emerald-50/60 rounded-lg border border-emerald-200 p-3 space-y-1">
                          <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Payment Allocation Preview</p>
                          {allocations.map((a, i) => (
                            <div key={i} className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-2">
                                <ArrowRight size={12} className="text-emerald-500" />
                                <span className="font-mono text-xs">{a.invoice}</span>
                                <Badge className={`text-[9px] ${typeLabel(a.type).cls}`}>{typeLabel(a.type).text}</Badge>
                              </div>
                              <div className="text-right">
                                <span className="font-bold text-emerald-600">{formatPHP(a.applied)}</span>
                                <span className="text-xs text-slate-400 ml-2">bal: {formatPHP(a.balance_after)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <Button data-testid="apply-payment-btn" onClick={handleReceivePayment} disabled={processing || !payAmount}
                        className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                        <Receipt size={16} className="mr-2" /> {processing ? 'Processing...' : `Apply Payment of ${formatPHP(parseFloat(payAmount) || 0)}`}
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Interest & Penalty Actions */}
              <div className="flex gap-2 flex-wrap items-center">
                <Button size="sm" variant="outline" onClick={handleGenerateInterest} className="text-amber-600 border-amber-200 hover:bg-amber-50" data-testid="generate-interest-btn">
                  <Percent size={13} className="mr-1" /> Generate Interest
                </Button>
                <Button size="sm" variant="outline" onClick={handleGeneratePenalty} className="text-red-600 border-red-200 hover:bg-red-50" data-testid="generate-penalty-btn">
                  <AlertTriangle size={13} className="mr-1" /> Compute Penalty
                </Button>
                <Input type="number" value={penaltyRate} onChange={e => setPenaltyRate(parseFloat(e.target.value) || 0)} className="w-16 h-8 text-xs text-center" />
                <span className="text-xs text-slate-400">% penalty rate</span>
              </div>

              {/* Invoices Table */}
              <Card className="border-slate-200">
                <CardContent className="p-0">
                  <Table>
                    <TableHeader><TableRow className="bg-slate-50">
                      <TableHead className="text-xs uppercase text-slate-500">Invoice #</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Type</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Due</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Original</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Paid</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Open Balance</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {invoices.length === 0 && (
                        <TableRow><TableCell colSpan={7} className="text-center py-6 text-slate-400">No open invoices</TableCell></TableRow>
                      )}
                      {invoices.map(inv => {
                        const isOverdue = inv.due_date && new Date(inv.due_date) < new Date() && inv.balance > 0;
                        const tl = typeLabel(inv.sale_type);
                        const alloc = allocations.find(a => a.invoice === inv.invoice_number);
                        return (
                          <TableRow key={inv.id} className={`table-row-hover ${alloc ? 'bg-emerald-50/50' : ''}`}>
                            <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
                            <TableCell><Badge className={`text-[10px] ${tl.cls}`}>{tl.text}</Badge></TableCell>
                            <TableCell className="text-xs">{inv.order_date}</TableCell>
                            <TableCell className={`text-xs ${isOverdue ? 'text-red-600 font-semibold' : ''}`}>{inv.due_date || '—'}</TableCell>
                            <TableCell className="text-right text-sm">{formatPHP(inv.grand_total)}</TableCell>
                            <TableCell className="text-right text-sm text-slate-500">{formatPHP(inv.amount_paid || 0)}</TableCell>
                            <TableCell className="text-right text-sm font-bold">
                              {formatPHP(inv.balance)}
                              {alloc && <span className="block text-[10px] text-emerald-600 font-medium">-{formatPHP(alloc.applied)}</span>}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      {invoices.length > 0 && (
                        <TableRow className="bg-slate-50 font-bold">
                          <TableCell colSpan={4} className="text-right text-xs uppercase text-slate-500">Totals</TableCell>
                          <TableCell className="text-right text-sm">{formatPHP(invoices.reduce((s, i) => s + (i.grand_total || 0), 0))}</TableCell>
                          <TableCell className="text-right text-sm text-slate-500">{formatPHP(invoices.reduce((s, i) => s + (i.amount_paid || 0), 0))}</TableCell>
                          <TableCell className="text-right text-sm text-red-600">{formatPHP(totalOpen)}</TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Select a customer to view their account</div>
          )}
        </div>
      </div>
    </div>
  );
}
