import { useState, useEffect, useCallback } from 'react';
import { api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { DollarSign, Search, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

export default function PaymentsPage() {
  const [customers, setCustomers] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [payDialog, setPayDialog] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [payForm, setPayForm] = useState({ amount: 0, method: 'Cash', fund_source: 'cashier', reference: '', date: new Date().toISOString().slice(0, 10) });
  const [search, setSearch] = useState('');

  useEffect(() => { api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {}); }, []);

  const loadInvoices = async (custId) => {
    try {
      const res = await api.get(`/customers/${custId}/invoices`);
      setInvoices(res.data);
    } catch { setInvoices([]); }
  };

  const selectCustomer = (c) => {
    setSelectedCustomer(c);
    loadInvoices(c.id);
  };

  const openPay = (inv) => {
    setSelectedInvoice(inv);
    setPayForm({ amount: inv.balance, method: 'Cash', fund_source: 'cashier', reference: '', date: new Date().toISOString().slice(0, 10) });
    setPayDialog(true);
  };

  const handlePay = async () => {
    try {
      const res = await api.post(`/invoices/${selectedInvoice.id}/payment`, payForm);
      toast.success(`Payment recorded! New balance: ${formatPHP(res.data.new_balance)}`);
      setPayDialog(false);
      if (selectedCustomer) loadInvoices(selectedCustomer.id);
    } catch (e) { toast.error(e.response?.data?.detail || 'Payment failed'); }
  };

  const computeInterest = async (invId) => {
    try {
      const res = await api.post(`/invoices/${invId}/compute-interest`);
      if (res.data.interest_added > 0) {
        toast.success(`Interest added: ${formatPHP(res.data.interest_added)} (${res.data.days} days overdue)`);
        if (selectedCustomer) loadInvoices(selectedCustomer.id);
      } else {
        toast(res.data.message);
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const filteredCustomers = search
    ? customers.filter(c => c.name.toLowerCase().includes(search.toLowerCase()) || c.phone?.includes(search))
    : customers;

  const totalOwed = invoices.reduce((s, i) => s + (i.balance || 0), 0);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="payments-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Receive Payments</h1>
        <p className="text-sm text-slate-500">Look up customer invoices and record payments</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Customer List */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Customers</CardTitle>
            <div className="relative mt-2">
              <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input data-testid="payment-customer-search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="pl-8 h-9" />
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

        {/* Invoices */}
        <div className="lg:col-span-2 space-y-4">
          {selectedCustomer ? (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>{selectedCustomer.name}</h2>
                  <p className="text-sm text-slate-500">Total Outstanding: <span className="font-bold text-amber-600">{formatPHP(totalOwed)}</span></p>
                </div>
              </div>
              <Card className="border-slate-200">
                <CardContent className="p-0">
                  <Table>
                    <TableHeader><TableRow className="bg-slate-50">
                      <TableHead className="text-xs uppercase text-slate-500">Invoice #</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Terms</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Due</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Original</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Interest</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 text-right">Balance</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                      <TableHead className="w-32"></TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {invoices.map(inv => {
                        const isOverdue = new Date(inv.due_date) < new Date() && inv.balance > 0;
                        return (
                          <TableRow key={inv.id} className="table-row-hover">
                            <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
                            <TableCell className="text-xs">{inv.order_date}</TableCell>
                            <TableCell className="text-xs">{inv.terms}</TableCell>
                            <TableCell className={`text-xs ${isOverdue ? 'text-red-600 font-semibold' : ''}`}>{inv.due_date}</TableCell>
                            <TableCell className="text-right text-sm">{formatPHP(inv.grand_total)}</TableCell>
                            <TableCell className="text-right text-sm text-amber-600">{inv.interest_accrued > 0 ? formatPHP(inv.interest_accrued) : '—'}</TableCell>
                            <TableCell className="text-right text-sm font-bold">{formatPHP(inv.balance)}</TableCell>
                            <TableCell>
                              <Badge className={`text-[10px] ${isOverdue ? 'bg-red-100 text-red-700' : inv.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                                {isOverdue ? 'OVERDUE' : inv.status}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-1">
                                {isOverdue && inv.interest_rate > 0 && (
                                  <Button variant="ghost" size="sm" onClick={() => computeInterest(inv.id)} title="Compute Interest" className="text-amber-600">
                                    <AlertTriangle size={12} className="mr-1" /> Interest
                                  </Button>
                                )}
                                <Button size="sm" variant="outline" data-testid={`pay-inv-${inv.id}`} onClick={() => openPay(inv)}>
                                  <DollarSign size={12} className="mr-1" /> Pay
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      {!invoices.length && <TableRow><TableCell colSpan={9} className="text-center py-6 text-slate-400">No open invoices</TableCell></TableRow>}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-400 text-sm">Select a customer to view their invoices</div>
          )}
        </div>
      </div>

      {/* Payment Dialog */}
      <Dialog open={payDialog} onOpenChange={setPayDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Record Payment</DialogTitle></DialogHeader>
          {selectedInvoice && (
            <div className="space-y-4 mt-2">
              <div className="p-3 bg-slate-50 rounded-lg text-sm space-y-1">
                <p>Invoice: <b>{selectedInvoice.invoice_number}</b></p>
                <p>Original: {formatPHP(selectedInvoice.grand_total)}</p>
                {selectedInvoice.interest_accrued > 0 && <p className="text-amber-600">Interest: {formatPHP(selectedInvoice.interest_accrued)}</p>}
                <p className="text-lg font-bold">Balance: {formatPHP(selectedInvoice.balance)}</p>
                {selectedInvoice.interest_accrued > 0 && (
                  <p className="text-xs text-slate-500">Interest & penalties will be deducted first from payment</p>
                )}
              </div>
              <div><Label>Amount</Label><Input data-testid="payment-amount" type="number" value={payForm.amount} onChange={e => setPayForm({ ...payForm, amount: parseFloat(e.target.value) || 0 })} className="text-lg font-bold h-12" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Method</Label>
                  <Select value={payForm.method} onValueChange={v => setPayForm({ ...payForm, method: v })}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Cash">Cash</SelectItem>
                      <SelectItem value="Check">Check</SelectItem>
                      <SelectItem value="Bank Transfer">Bank Transfer</SelectItem>
                      <SelectItem value="Digital Wallet">Digital Wallet</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Deposit To</Label>
                  <Select value={payForm.fund_source} onValueChange={v => setPayForm({ ...payForm, fund_source: v })}>
                    <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cashier">Cashier Drawer</SelectItem>
                      <SelectItem value="safe">Safe</SelectItem>
                      <SelectItem value="bank">Bank</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>Reference / Check #</Label><Input value={payForm.reference} onChange={e => setPayForm({ ...payForm, reference: e.target.value })} /></div>
              <div><Label>Date</Label><Input type="date" value={payForm.date} onChange={e => setPayForm({ ...payForm, date: e.target.value })} /></div>
              <Button data-testid="confirm-payment" onClick={handlePay} className="w-full h-11 bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                Record Payment of {formatPHP(payForm.amount)}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
