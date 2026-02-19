import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, DollarSign, ArrowDown, ArrowUp, Search, Filter, Edit2, Tractor, FileText, Banknote } from 'lucide-react';
import { toast } from 'sonner';

const EXPENSE_CATEGORIES = [
  "Utilities", "Rent", "Supplies", "Transportation", "Fuel/Gas",
  "Employee Advance", "Farm Expense", "Customer Cash Out", "Repairs & Maintenance",
  "Marketing", "Salaries & Wages", "Communication", "Insurance",
  "Professional Fees", "Taxes & Licenses", "Office Supplies",
  "Equipment", "Miscellaneous"
];

const PAYMENT_METHODS = ["Cash", "Check", "Bank Transfer", "GCash", "Maya", "Credit Card"];

export default function AccountingPage() {
  const { currentBranch } = useAuth();
  const [expenses, setExpenses] = useState([]);
  const [receivables, setReceivables] = useState([]);
  const [payables, setPayables] = useState([]);
  const [customers, setCustomers] = useState([]);
  
  // Dialog states
  const [expenseDialog, setExpenseDialog] = useState(false);
  const [farmExpenseDialog, setFarmExpenseDialog] = useState(false);
  const [cashOutDialog, setCashOutDialog] = useState(false);
  const [payableDialog, setPayableDialog] = useState(false);
  const [paymentDialog, setPaymentDialog] = useState(false);
  const [paymentTarget, setPaymentTarget] = useState(null);
  const [paymentType, setPaymentType] = useState('');
  const [paymentAmount, setPaymentAmount] = useState(0);
  const [editMode, setEditMode] = useState(false);
  
  // Forms
  const [expenseForm, setExpenseForm] = useState({
    category: 'Miscellaneous', description: '', notes: '', amount: 0,
    payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10)
  });
  const [farmExpenseForm, setFarmExpenseForm] = useState({
    description: '', notes: '', amount: 0, customer_id: '',
    payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10),
    due_date: '', terms: ''
  });
  const [cashOutForm, setCashOutForm] = useState({
    description: '', notes: '', amount: 0, customer_id: '',
    payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10),
    due_date: '', terms: ''
  });
  const [payableForm, setPayableForm] = useState({ supplier: '', description: '', amount: 0, due_date: '' });
  
  // Filters
  const [filters, setFilters] = useState({
    category: '', payment_method: '', date_from: '', date_to: '', search: ''
  });
  const [showFilters, setShowFilters] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const params = currentBranch ? { branch_id: currentBranch.id, limit: 100 } : { limit: 100 };
      // Add filters
      if (filters.category) params.category = filters.category;
      if (filters.payment_method) params.payment_method = filters.payment_method;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.search) params.search = filters.search;
      
      const [expRes, recRes, payRes, custRes] = await Promise.all([
        api.get('/expenses', { params }),
        api.get('/receivables', { params: { limit: 100 } }),
        api.get('/payables', { params: { limit: 100 } }),
        api.get('/customers', { params: { limit: 500 } }),
      ]);
      setExpenses(expRes.data.expenses);
      setReceivables(recRes.data.receivables);
      setPayables(payRes.data.payables);
      setCustomers(custRes.data.customers || []);
    } catch { toast.error('Failed to load accounting data'); }
  }, [currentBranch, filters]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openNewExpense = () => {
    setEditMode(false);
    setExpenseForm({
      category: 'Miscellaneous', description: '', notes: '', amount: 0,
      payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10)
    });
    setExpenseDialog(true);
  };

  const openEditExpense = (expense) => {
    setEditMode(true);
    setExpenseForm({
      id: expense.id,
      category: expense.category || 'Miscellaneous',
      description: expense.description || '',
      notes: expense.notes || '',
      amount: expense.amount || 0,
      payment_method: expense.payment_method || 'Cash',
      reference_number: expense.reference_number || '',
      date: expense.date || new Date().toISOString().slice(0, 10)
    });
    setExpenseDialog(true);
  };

  const openFarmExpense = () => {
    setFarmExpenseForm({
      description: '', notes: '', amount: 0, customer_id: '',
      payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10),
      due_date: '', terms: ''
    });
    setFarmExpenseDialog(true);
  };

  const openCashOut = () => {
    setCashOutForm({
      description: '', notes: '', amount: 0, customer_id: '',
      payment_method: 'Cash', reference_number: '', date: new Date().toISOString().slice(0, 10),
      due_date: '', terms: ''
    });
    setCashOutDialog(true);
  };

  const handleSaveExpense = async () => {
    if (!expenseForm.amount || expenseForm.amount <= 0) {
      toast.error('Amount must be greater than 0');
      return;
    }
    try {
      if (editMode && expenseForm.id) {
        await api.put(`/expenses/${expenseForm.id}`, expenseForm);
        toast.success('Expense updated');
      } else {
        await api.post('/expenses', { ...expenseForm, branch_id: currentBranch?.id });
        toast.success('Expense recorded');
      }
      setExpenseDialog(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error saving expense'); }
  };

  const handleCreateFarmExpense = async () => {
    if (!farmExpenseForm.customer_id) {
      toast.error('Please select a customer to bill');
      return;
    }
    if (!farmExpenseForm.amount || farmExpenseForm.amount <= 0) {
      toast.error('Amount must be greater than 0');
      return;
    }
    try {
      const res = await api.post('/expenses/farm', { ...farmExpenseForm, branch_id: currentBranch?.id });
      toast.success(res.data.message);
      setFarmExpenseDialog(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating farm expense'); }
  };

  const handleCreateCashOut = async () => {
    if (!cashOutForm.customer_id) {
      toast.error('Please select a customer');
      return;
    }
    if (!cashOutForm.amount || cashOutForm.amount <= 0) {
      toast.error('Amount must be greater than 0');
      return;
    }
    try {
      const res = await api.post('/expenses/customer-cashout', { ...cashOutForm, branch_id: currentBranch?.id });
      toast.success(res.data.message);
      setCashOutDialog(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error creating cash out'); }
  };

  const handleCreatePayable = async () => {
    try {
      await api.post('/payables', { ...payableForm, branch_id: currentBranch?.id });
      toast.success('Payable recorded');
      setPayableDialog(false);
      fetchAll();
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
      toast.success('Payment recorded');
      setPaymentDialog(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const deleteExpense = async (id) => {
    if (!window.confirm('Delete this expense? This will refund the amount to cashier wallet.')) return;
    try {
      await api.delete(`/expenses/${id}`);
      toast.success('Expense deleted');
      fetchAll();
    } catch { toast.error('Failed to delete'); }
  };

  const clearFilters = () => {
    setFilters({ category: '', payment_method: '', date_from: '', date_to: '', search: '' });
  };

  const totalExpenses = expenses.reduce((s, e) => s + (e.amount || 0), 0);
  const totalReceivables = receivables.filter(r => r.status !== 'paid').reduce((s, r) => s + (r.balance || 0), 0);
  const totalPayables = payables.filter(p => p.status !== 'paid').reduce((s, p) => s + (p.balance || 0), 0);

  const paymentMethodBadge = (method) => {
    const colors = {
      'Cash': 'bg-emerald-100 text-emerald-700',
      'Check': 'bg-blue-100 text-blue-700',
      'Bank Transfer': 'bg-purple-100 text-purple-700',
      'GCash': 'bg-sky-100 text-sky-700',
      'Maya': 'bg-green-100 text-green-700',
    };
    return colors[method] || 'bg-slate-100 text-slate-700';
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="accounting-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Accounting</h1>
        <p className="text-sm text-slate-500 mt-1">Expenses, Receivables & Payables</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDown size={16} className="text-red-500" />
              <span className="text-xs text-slate-500 uppercase font-medium">Total Expenses</span>
            </div>
            <p className="text-2xl font-bold text-red-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalExpenses)}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowUp size={16} className="text-amber-500" />
              <span className="text-xs text-slate-500 uppercase font-medium">Receivables</span>
            </div>
            <p className="text-2xl font-bold text-amber-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalReceivables)}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign size={16} className="text-blue-500" />
              <span className="text-xs text-slate-500 uppercase font-medium">Payables</span>
            </div>
            <p className="text-2xl font-bold text-blue-600" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalPayables)}</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="expenses">
        <TabsList>
          <TabsTrigger value="expenses" data-testid="tab-expenses">Expenses</TabsTrigger>
          <TabsTrigger value="receivables" data-testid="tab-receivables">Receivables</TabsTrigger>
          <TabsTrigger value="payables" data-testid="tab-payables">Payables</TabsTrigger>
        </TabsList>

        {/* EXPENSES TAB */}
        <TabsContent value="expenses" className="mt-4 space-y-4">
          {/* Action Buttons */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
                <Filter size={14} className="mr-1" /> Filters
              </Button>
              {(filters.category || filters.payment_method || filters.date_from || filters.date_to || filters.search) && (
                <Button variant="ghost" size="sm" onClick={clearFilters} className="text-slate-500">
                  Clear filters
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button onClick={openCashOut} variant="outline" className="border-blue-300 text-blue-700 hover:bg-blue-50" data-testid="cashout-btn">
                <Banknote size={16} className="mr-2" /> Customer Cash Out
              </Button>
              <Button onClick={openFarmExpense} variant="outline" className="border-amber-300 text-amber-700 hover:bg-amber-50" data-testid="farm-expense-btn">
                <Tractor size={16} className="mr-2" /> Farm Expense
              </Button>
              <Button onClick={openNewExpense} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="create-expense-btn">
                <Plus size={16} className="mr-2" /> Record Expense
              </Button>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <Card className="border-slate-200 bg-slate-50">
              <CardContent className="p-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div>
                    <Label className="text-xs">Category</Label>
                    <Select value={filters.category || "__all__"} onValueChange={v => setFilters(f => ({ ...f, category: v === "__all__" ? "" : v }))}>
                      <SelectTrigger className="h-9"><SelectValue placeholder="All categories" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__all__">All categories</SelectItem>
                        {EXPENSE_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">Payment Method</Label>
                    <Select value={filters.payment_method || "__all__"} onValueChange={v => setFilters(f => ({ ...f, payment_method: v === "__all__" ? "" : v }))}>
                      <SelectTrigger className="h-9"><SelectValue placeholder="All methods" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__all__">All methods</SelectItem>
                        {PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">From Date</Label>
                    <Input type="date" className="h-9" value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-xs">To Date</Label>
                    <Input type="date" className="h-9" value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-xs">Search</Label>
                    <div className="relative">
                      <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                      <Input
                        className="h-9 pl-8"
                        placeholder="Description, ref..."
                        value={filters.search}
                        onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Expenses Table */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Date</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Category</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Description</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Payment</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Ref #</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">By</TableHead>
                    <TableHead className="w-20"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {expenses.map(e => (
                    <TableRow key={e.id} className="table-row-hover">
                      <TableCell className="text-sm">{e.date}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-[10px] ${
                          e.category === 'Farm Expense' ? 'bg-amber-50 text-amber-700 border-amber-200' : 
                          e.category === 'Customer Cash Out' ? 'bg-blue-50 text-blue-700 border-blue-200' : ''
                        }`}>
                          {e.category === 'Farm Expense' && <Tractor size={10} className="mr-1" />}
                          {e.category === 'Customer Cash Out' && <Banknote size={10} className="mr-1" />}
                          {e.category}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        <div>{e.description}</div>
                        {e.notes && <div className="text-xs text-slate-400">{e.notes}</div>}
                        {e.customer_name && (
                          <div className={`text-xs ${e.category === 'Customer Cash Out' ? 'text-blue-600' : 'text-amber-600'}`}>
                            {e.category === 'Customer Cash Out' ? 'Loaned to: ' : 'Billed to: '}{e.customer_name}
                          </div>
                        )}
                        {e.linked_invoice_number && (
                          <div className="text-xs text-blue-600 flex items-center gap-1">
                            <FileText size={10} /> Invoice: {e.linked_invoice_number}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${paymentMethodBadge(e.payment_method)}`}>{e.payment_method || 'Cash'}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-500 font-mono">{e.reference_number || '-'}</TableCell>
                      <TableCell className="text-right font-semibold text-red-600">{formatPHP(e.amount)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{e.created_by_name}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEditExpense(e)} className="text-slate-500 h-7 px-2">
                            <Edit2 size={12} />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => deleteExpense(e.id)} className="text-red-500 h-7 px-2">Del</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!expenses.length && (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-slate-400">
                        No expenses found
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* RECEIVABLES TAB */}
        <TabsContent value="receivables" className="mt-4">
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Customer</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Description</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Paid</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Balance</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Status</TableHead>
                    <TableHead className="w-28"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {receivables.map(r => (
                    <TableRow key={r.id} className="table-row-hover">
                      <TableCell className="font-medium">{r.customer_name}</TableCell>
                      <TableCell className="text-sm text-slate-600">{r.description || '-'}</TableCell>
                      <TableCell className="text-right">{formatPHP(r.amount)}</TableCell>
                      <TableCell className="text-right text-emerald-600">{formatPHP(r.paid)}</TableCell>
                      <TableCell className="text-right font-semibold text-amber-600">{formatPHP(r.balance)}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${r.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : r.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'}`}>
                          {r.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {r.status !== 'paid' && (
                          <Button size="sm" variant="outline" onClick={() => openPayment(r, 'receivable')}>
                            Record Payment
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!receivables.length && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-slate-400">No receivables</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* PAYABLES TAB */}
        <TabsContent value="payables" className="mt-4 space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => { setPayableForm({ supplier: '', description: '', amount: 0, due_date: '' }); setPayableDialog(true); }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="create-payable-btn">
              <Plus size={16} className="mr-2" /> Record Payable
            </Button>
          </div>
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Supplier</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Description</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Amount</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Paid</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500 text-right">Balance</TableHead>
                    <TableHead className="text-xs uppercase tracking-wider text-slate-500">Status</TableHead>
                    <TableHead className="w-28"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payables.map(p => (
                    <TableRow key={p.id} className="table-row-hover">
                      <TableCell className="font-medium">{p.supplier}</TableCell>
                      <TableCell className="text-sm text-slate-600">{p.description || '-'}</TableCell>
                      <TableCell className="text-right">{formatPHP(p.amount)}</TableCell>
                      <TableCell className="text-right text-emerald-600">{formatPHP(p.paid)}</TableCell>
                      <TableCell className="text-right font-semibold text-blue-600">{formatPHP(p.balance)}</TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] ${p.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : p.status === 'partial' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'}`}>
                          {p.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {p.status !== 'paid' && (
                          <Button size="sm" variant="outline" onClick={() => openPayment(p, 'payable')}>
                            Record Payment
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!payables.length && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-slate-400">No payables</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* REGULAR EXPENSE DIALOG */}
      <Dialog open={expenseDialog} onOpenChange={setExpenseDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>{editMode ? 'Edit Expense' : 'Record Expense'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Category</Label>
                <Select value={expenseForm.category} onValueChange={v => setExpenseForm({ ...expenseForm, category: v })}>
                  <SelectTrigger className="h-10" data-testid="expense-category">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {EXPENSE_CATEGORIES.filter(c => c !== 'Farm Expense').map(c => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Date</Label>
                <Input type="date" className="h-10" value={expenseForm.date} onChange={e => setExpenseForm({ ...expenseForm, date: e.target.value })} />
              </div>
            </div>
            <div>
              <Label className="text-xs text-slate-500">Description</Label>
              <Input data-testid="expense-description" className="h-10" value={expenseForm.description} onChange={e => setExpenseForm({ ...expenseForm, description: e.target.value })} placeholder="What is this expense for?" />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Notes (optional)</Label>
              <Input className="h-10" value={expenseForm.notes} onChange={e => setExpenseForm({ ...expenseForm, notes: e.target.value })} placeholder="Additional details..." />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Amount (₱)</Label>
                <Input data-testid="expense-amount" type="number" className="h-10" value={expenseForm.amount} onChange={e => setExpenseForm({ ...expenseForm, amount: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Payment Method</Label>
                <Select value={expenseForm.payment_method} onValueChange={v => setExpenseForm({ ...expenseForm, payment_method: v })}>
                  <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs text-slate-500">Reference # (Check/Receipt/OR)</Label>
              <Input className="h-10" value={expenseForm.reference_number} onChange={e => setExpenseForm({ ...expenseForm, reference_number: e.target.value })} placeholder="Optional reference number" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setExpenseDialog(false)}>Cancel</Button>
              <Button onClick={handleSaveExpense} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="save-expense-btn">
                {editMode ? 'Update Expense' : 'Save Expense'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* FARM EXPENSE DIALOG */}
      <Dialog open={farmExpenseDialog} onOpenChange={setFarmExpenseDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Tractor size={20} className="text-amber-600" />
              Farm Expense
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              This will record a farm expense and automatically create an invoice for the selected customer.
            </div>
            
            <div>
              <Label className="text-xs text-slate-500">Service Description *</Label>
              <Input
                className="h-10"
                value={farmExpenseForm.description}
                onChange={e => setFarmExpenseForm({ ...farmExpenseForm, description: e.target.value })}
                placeholder="e.g. Tilling, Plowing, Harvesting"
                data-testid="farm-expense-description"
              />
            </div>
            
            <div>
              <Label className="text-xs text-slate-500">Notes (Tilling, Labor, Gas, etc.)</Label>
              <Input
                className="h-10"
                value={farmExpenseForm.notes}
                onChange={e => setFarmExpenseForm({ ...farmExpenseForm, notes: e.target.value })}
                placeholder="e.g. 2 hours tilling + 5L gas + 2 workers"
                data-testid="farm-expense-notes"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Amount (₱) *</Label>
                <Input
                  type="number"
                  className="h-10"
                  value={farmExpenseForm.amount}
                  onChange={e => setFarmExpenseForm({ ...farmExpenseForm, amount: parseFloat(e.target.value) || 0 })}
                  data-testid="farm-expense-amount"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Date</Label>
                <Input
                  type="date"
                  className="h-10"
                  value={farmExpenseForm.date}
                  onChange={e => setFarmExpenseForm({ ...farmExpenseForm, date: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Payment Method</Label>
                <Select value={farmExpenseForm.payment_method} onValueChange={v => setFarmExpenseForm({ ...farmExpenseForm, payment_method: v })}>
                  <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Reference #</Label>
                <Input
                  className="h-10"
                  value={farmExpenseForm.reference_number}
                  onChange={e => setFarmExpenseForm({ ...farmExpenseForm, reference_number: e.target.value })}
                  placeholder="Optional"
                />
              </div>
            </div>

            <div className="border-t pt-4 mt-4">
              <Label className="text-xs text-slate-500 font-semibold">Bill to Customer *</Label>
              <p className="text-xs text-slate-400 mb-2">An invoice will be automatically created for this customer</p>
              <Select value={farmExpenseForm.customer_id} onValueChange={v => setFarmExpenseForm({ ...farmExpenseForm, customer_id: v })}>
                <SelectTrigger className="h-10" data-testid="farm-expense-customer">
                  <SelectValue placeholder="Select customer to bill" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map(c => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Invoice Due Date</Label>
                <Input
                  type="date"
                  className="h-10"
                  value={farmExpenseForm.due_date}
                  onChange={e => setFarmExpenseForm({ ...farmExpenseForm, due_date: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Payment Terms</Label>
                <Input
                  className="h-10"
                  value={farmExpenseForm.terms}
                  onChange={e => setFarmExpenseForm({ ...farmExpenseForm, terms: e.target.value })}
                  placeholder="e.g. Net 30"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setFarmExpenseDialog(false)}>Cancel</Button>
              <Button
                onClick={handleCreateFarmExpense}
                className="bg-amber-600 hover:bg-amber-700 text-white"
                data-testid="save-farm-expense-btn"
              >
                <Tractor size={14} className="mr-2" />
                Create Expense & Invoice
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* CUSTOMER CASH OUT DIALOG */}
      <Dialog open={cashOutDialog} onOpenChange={setCashOutDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <Banknote size={20} className="text-blue-600" />
              Customer Cash Out
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
              This will release cash to a customer and automatically create an invoice for the amount owed.
            </div>
            
            <div>
              <Label className="text-xs text-slate-500">Select Customer *</Label>
              <p className="text-xs text-slate-400 mb-2">An invoice will be automatically created for this customer</p>
              <Select value={cashOutForm.customer_id} onValueChange={v => setCashOutForm({ ...cashOutForm, customer_id: v })}>
                <SelectTrigger className="h-10" data-testid="cashout-customer">
                  <SelectValue placeholder="Select customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map(c => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Amount (₱) *</Label>
                <Input
                  type="number"
                  className="h-10"
                  value={cashOutForm.amount}
                  onChange={e => setCashOutForm({ ...cashOutForm, amount: parseFloat(e.target.value) || 0 })}
                  data-testid="cashout-amount"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Date</Label>
                <Input
                  type="date"
                  className="h-10"
                  value={cashOutForm.date}
                  onChange={e => setCashOutForm({ ...cashOutForm, date: e.target.value })}
                />
              </div>
            </div>
            
            <div>
              <Label className="text-xs text-slate-500">Purpose / Description</Label>
              <Input
                className="h-10"
                value={cashOutForm.description}
                onChange={e => setCashOutForm({ ...cashOutForm, description: e.target.value })}
                placeholder="e.g. Cash Advance, Loan, etc."
                data-testid="cashout-description"
              />
            </div>
            
            <div>
              <Label className="text-xs text-slate-500">Notes (optional)</Label>
              <Input
                className="h-10"
                value={cashOutForm.notes}
                onChange={e => setCashOutForm({ ...cashOutForm, notes: e.target.value })}
                placeholder="Additional details..."
                data-testid="cashout-notes"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Payment Method</Label>
                <Select value={cashOutForm.payment_method} onValueChange={v => setCashOutForm({ ...cashOutForm, payment_method: v })}>
                  <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Reference #</Label>
                <Input
                  className="h-10"
                  value={cashOutForm.reference_number}
                  onChange={e => setCashOutForm({ ...cashOutForm, reference_number: e.target.value })}
                  placeholder="Optional"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Invoice Due Date</Label>
                <Input
                  type="date"
                  className="h-10"
                  value={cashOutForm.due_date}
                  onChange={e => setCashOutForm({ ...cashOutForm, due_date: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Payment Terms</Label>
                <Input
                  className="h-10"
                  value={cashOutForm.terms}
                  onChange={e => setCashOutForm({ ...cashOutForm, terms: e.target.value })}
                  placeholder="e.g. Net 30"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setCashOutDialog(false)}>Cancel</Button>
              <Button
                onClick={handleCreateCashOut}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="save-cashout-btn"
              >
                <Banknote size={14} className="mr-2" />
                Release Cash & Create Invoice
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* PAYABLE DIALOG */}
      <Dialog open={payableDialog} onOpenChange={setPayableDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Record Payable</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-xs text-slate-500">Supplier</Label>
              <Input data-testid="payable-supplier" className="h-10" value={payableForm.supplier} onChange={e => setPayableForm({ ...payableForm, supplier: e.target.value })} />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Description</Label>
              <Input className="h-10" value={payableForm.description} onChange={e => setPayableForm({ ...payableForm, description: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-slate-500">Amount (₱)</Label>
                <Input data-testid="payable-amount" type="number" className="h-10" value={payableForm.amount} onChange={e => setPayableForm({ ...payableForm, amount: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Due Date</Label>
                <Input type="date" className="h-10" value={payableForm.due_date} onChange={e => setPayableForm({ ...payableForm, due_date: e.target.value })} />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setPayableDialog(false)}>Cancel</Button>
              <Button onClick={handleCreatePayable} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="save-payable-btn">Save</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* PAYMENT DIALOG */}
      <Dialog open={paymentDialog} onOpenChange={setPaymentDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Record Payment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <p className="text-sm">Outstanding Balance: <span className="font-bold">{formatPHP(paymentTarget?.balance || 0)}</span></p>
            <div>
              <Label className="text-xs text-slate-500">Payment Amount (₱)</Label>
              <Input data-testid="payment-amount-input" type="number" className="h-10" value={paymentAmount} onChange={e => setPaymentAmount(parseFloat(e.target.value) || 0)} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setPaymentDialog(false)}>Cancel</Button>
              <Button onClick={handlePayment} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white" data-testid="confirm-payment-btn">Record Payment</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
