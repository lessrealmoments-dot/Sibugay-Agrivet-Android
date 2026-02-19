import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Calculator, Plus, DollarSign, ArrowDown, ArrowUp } from 'lucide-react';
import { toast } from 'sonner';

export default function AccountingPage() {
  const { currentBranch } = useAuth();
  const [expenses, setExpenses] = useState([]);
  const [receivables, setReceivables] = useState([]);
  const [payables, setPayables] = useState([]);
  const [expenseDialog, setExpenseDialog] = useState(false);
  const [payableDialog, setPayableDialog] = useState(false);
  const [paymentDialog, setPaymentDialog] = useState(false);
  const [paymentTarget, setPaymentTarget] = useState(null);
  const [paymentType, setPaymentType] = useState('');
  const [paymentAmount, setPaymentAmount] = useState(0);
  const [expenseForm, setExpenseForm] = useState({ category: '', description: '', amount: 0, date: new Date().toISOString().slice(0, 10) });
  const [payableForm, setPayableForm] = useState({ supplier: '', description: '', amount: 0, due_date: '' });

  const fetchAll = useCallback(async () => {
    try {
      const params = currentBranch ? { branch_id: currentBranch.id } : {};
      const [expRes, recRes, payRes] = await Promise.all([
        api.get('/expenses', { params: { ...params, limit: 50 } }),
        api.get('/receivables', { params: { limit: 50 } }),
        api.get('/payables', { params: { limit: 50 } }),
      ]);
      setExpenses(expRes.data.expenses);
      setReceivables(recRes.data.receivables);
      setPayables(payRes.data.payables);
    } catch { toast.error('Failed to load accounting data'); }
  }, [currentBranch]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreateExpense = async () => {
    try {
      await api.post('/expenses', { ...expenseForm, branch_id: currentBranch?.id });
      toast.success('Expense recorded'); setExpenseDialog(false); fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleCreatePayable = async () => {
    try {
      await api.post('/payables', { ...payableForm, branch_id: currentBranch?.id });
      toast.success('Payable recorded'); setPayableDialog(false); fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openPayment = (item, type) => {
    setPaymentTarget(item);
    setPaymentType(type);
    setPaymentAmount(item.balance || 0);
    setPaymentDialog(true);
  };

  const handlePayment = async () => {
    try {
      const url = paymentType === 'receivable'
        ? `/receivables/${paymentTarget.id}/payment`
        : `/payables/${paymentTarget.id}/payment`;
      await api.post(url, { amount: paymentAmount });
      toast.success('Payment recorded'); setPaymentDialog(false); fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const deleteExpense = async (id) => {
    if (!window.confirm('Delete this expense?')) return;
    try { await api.delete(`/expenses/${id}`); toast.success('Deleted'); fetchAll(); }
    catch { toast.error('Failed'); }
  };

  const totalExpenses = expenses.reduce((s, e) => s + (e.amount || 0), 0);
  const totalReceivables = receivables.filter(r => r.status !== 'paid').reduce((s, r) => s + (r.balance || 0), 0);
  const totalPayables = payables.filter(p => p.status !== 'paid').reduce((s, p) => s + (p.balance || 0), 0);

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="accounting-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Accounting</h1>
        <p className="text-sm text-slate-500 mt-1">Expenses, Receivables & Payables</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2"><ArrowDown size={16} className="text-red-500" /><span className="text-xs text-slate-500 uppercase font-medium">Total Expenses</span></div>
            <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{totalExpenses.toLocaleString('en', { minimumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2"><ArrowUp size={16} className="text-amber-500" /><span className="text-xs text-slate-500 uppercase font-medium">Receivables</span></div>
            <p className="text-2xl font-bold text-amber-600" style={{ fontFamily: 'Manrope' }}>{totalReceivables.toLocaleString('en', { minimumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2"><DollarSign size={16} className="text-blue-500" /><span className="text-xs text-slate-500 uppercase font-medium">Payables</span></div>
            <p className="text-2xl font-bold text-blue-600" style={{ fontFamily: 'Manrope' }}>{totalPayables.toLocaleString('en', { minimumFractionDigits: 2 })}</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="expenses">
        <TabsList>
          <TabsTrigger value="expenses" data-testid="tab-expenses">Expenses</TabsTrigger>
          <TabsTrigger value="receivables" data-testid="tab-receivables">Receivables</TabsTrigger>
          <TabsTrigger value="payables" data-testid="tab-payables">Payables</TabsTrigger>
        </TabsList>

        <TabsContent value="expenses" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Button data-testid="create-expense-btn" onClick={() => { setExpenseForm({ category: '', description: '', amount: 0, date: new Date().toISOString().slice(0, 10) }); setExpenseDialog(true); }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
              <Plus size={16} className="mr-2" /> Record Expense
            </Button>
          </div>
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Date</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Category</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Description</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">By</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {expenses.map(e => (
                    <TableRow key={e.id} className="table-row-hover">
                      <TableCell className="text-sm">{e.date}</TableCell>
                      <TableCell><Badge variant="outline" className="text-[10px]">{e.category}</Badge></TableCell>
                      <TableCell className="text-sm">{e.description}</TableCell>
                      <TableCell className="text-right font-semibold text-red-600">{e.amount?.toFixed(2)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{e.created_by_name}</TableCell>
                      <TableCell><Button variant="ghost" size="sm" onClick={() => deleteExpense(e.id)} className="text-red-500">Del</Button></TableCell>
                    </TableRow>
                  ))}
                  {!expenses.length && <TableRow><TableCell colSpan={6} className="text-center py-6 text-slate-400">No expenses</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="receivables" className="mt-4">
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Customer</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Paid</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Balance</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Status</TableHead>
                  <TableHead className="w-24"></TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {receivables.map(r => (
                    <TableRow key={r.id} className="table-row-hover">
                      <TableCell className="font-medium">{r.customer_name}</TableCell>
                      <TableCell className="text-right">{r.amount?.toFixed(2)}</TableCell>
                      <TableCell className="text-right text-emerald-600">{r.paid?.toFixed(2)}</TableCell>
                      <TableCell className="text-right font-semibold text-amber-600">{r.balance?.toFixed(2)}</TableCell>
                      <TableCell><Badge className={`text-[10px] ${r.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : r.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'}`}>{r.status}</Badge></TableCell>
                      <TableCell>{r.status !== 'paid' && <Button size="sm" variant="outline" data-testid={`pay-receivable-${r.id}`} onClick={() => openPayment(r, 'receivable')}>Record Payment</Button>}</TableCell>
                    </TableRow>
                  ))}
                  {!receivables.length && <TableRow><TableCell colSpan={6} className="text-center py-6 text-slate-400">No receivables</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="payables" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Button data-testid="create-payable-btn" onClick={() => { setPayableForm({ supplier: '', description: '', amount: 0, due_date: '' }); setPayableDialog(true); }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
              <Plus size={16} className="mr-2" /> Record Payable
            </Button>
          </div>
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Supplier</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Description</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Paid</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Balance</TableHead>
                  <TableHead className="text-xs uppercase tracking-wider text-slate-500">Status</TableHead>
                  <TableHead className="w-24"></TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {payables.map(p => (
                    <TableRow key={p.id} className="table-row-hover">
                      <TableCell className="font-medium">{p.supplier}</TableCell>
                      <TableCell className="text-sm">{p.description}</TableCell>
                      <TableCell className="text-right">{p.amount?.toFixed(2)}</TableCell>
                      <TableCell className="text-right text-emerald-600">{p.paid?.toFixed(2)}</TableCell>
                      <TableCell className="text-right font-semibold text-blue-600">{p.balance?.toFixed(2)}</TableCell>
                      <TableCell><Badge className={`text-[10px] ${p.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : p.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'}`}>{p.status}</Badge></TableCell>
                      <TableCell>{p.status !== 'paid' && <Button size="sm" variant="outline" data-testid={`pay-payable-${p.id}`} onClick={() => openPayment(p, 'payable')}>Pay</Button>}</TableCell>
                    </TableRow>
                  ))}
                  {!payables.length && <TableRow><TableCell colSpan={7} className="text-center py-6 text-slate-400">No payables</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Expense Dialog */}
      <Dialog open={expenseDialog} onOpenChange={setExpenseDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Record Expense</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Category</Label><Input data-testid="expense-category" value={expenseForm.category} onChange={e => setExpenseForm({ ...expenseForm, category: e.target.value })} placeholder="e.g. Utilities" /></div>
              <div><Label>Date</Label><Input type="date" value={expenseForm.date} onChange={e => setExpenseForm({ ...expenseForm, date: e.target.value })} /></div>
            </div>
            <div><Label>Description</Label><Input data-testid="expense-description" value={expenseForm.description} onChange={e => setExpenseForm({ ...expenseForm, description: e.target.value })} /></div>
            <div><Label>Amount</Label><Input data-testid="expense-amount" type="number" value={expenseForm.amount} onChange={e => setExpenseForm({ ...expenseForm, amount: parseFloat(e.target.value) || 0 })} /></div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setExpenseDialog(false)}>Cancel</Button>
              <Button data-testid="save-expense-btn" onClick={handleCreateExpense} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Payable Dialog */}
      <Dialog open={payableDialog} onOpenChange={setPayableDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Record Payable</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div><Label>Supplier</Label><Input data-testid="payable-supplier" value={payableForm.supplier} onChange={e => setPayableForm({ ...payableForm, supplier: e.target.value })} /></div>
            <div><Label>Description</Label><Input value={payableForm.description} onChange={e => setPayableForm({ ...payableForm, description: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Amount</Label><Input data-testid="payable-amount" type="number" value={payableForm.amount} onChange={e => setPayableForm({ ...payableForm, amount: parseFloat(e.target.value) || 0 })} /></div>
              <div><Label>Due Date</Label><Input type="date" value={payableForm.due_date} onChange={e => setPayableForm({ ...payableForm, due_date: e.target.value })} /></div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setPayableDialog(false)}>Cancel</Button>
              <Button data-testid="save-payable-btn" onClick={handleCreatePayable} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Payment Dialog */}
      <Dialog open={paymentDialog} onOpenChange={setPaymentDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Record Payment</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <p className="text-sm">Outstanding Balance: <span className="font-bold">{paymentTarget?.balance?.toFixed(2)}</span></p>
            <div><Label>Payment Amount</Label><Input data-testid="payment-amount-input" type="number" value={paymentAmount} onChange={e => setPaymentAmount(parseFloat(e.target.value) || 0)} /></div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setPaymentDialog(false)}>Cancel</Button>
              <Button data-testid="confirm-payment-btn" onClick={handlePayment} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Record</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
