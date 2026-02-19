import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  ClipboardList, TrendingUp, Lock, Printer, Calendar,
  DollarSign, ArrowDown, ArrowUp, AlertTriangle, Plus
} from 'lucide-react';
import { toast } from 'sonner';

export default function DailyLogPage() {
  const { currentBranch } = useAuth();
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [tab, setTab] = useState('log');
  const [logEntries, setLogEntries] = useState([]);
  const [report, setReport] = useState(null);
  const [closing, setClosing] = useState(null);
  const [closeForm, setCloseForm] = useState({ actual_cash: 0, bank_checks: 0, other_payment_forms: 0, cash_to_drawer: 0, cash_to_safe: 0 });
  const [expenseDialog, setExpenseDialog] = useState(false);
  const [expenseType, setExpenseType] = useState('other');
  const [expForm, setExpForm] = useState({ category: '', description: '', amount: 0, customer_id: '', tag: '', employee_id: '', employee_name: '' });
  const [customers, setCustomers] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [empDialog, setEmpDialog] = useState(false);
  const [empForm, setEmpForm] = useState({ name: '', position: '', phone: '' });

  const fetchLog = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get('/daily-log', { params: { date, branch_id: currentBranch.id } });
      setLogEntries(res.data.entries);
    } catch {}
  }, [date, currentBranch]);

  const fetchReport = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get('/daily-report', { params: { date, branch_id: currentBranch.id } });
      setReport(res.data);
    } catch {}
  }, [date, currentBranch]);

  const fetchClosing = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get(`/daily-close/${date}`, { params: { branch_id: currentBranch.id } });
      setClosing(res.data);
    } catch {}
  }, [date, currentBranch]);

  useEffect(() => { fetchLog(); fetchReport(); fetchClosing(); }, [fetchLog, fetchReport, fetchClosing]);
  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    if (currentBranch) api.get('/employees', { params: { branch_id: currentBranch.id } }).then(r => setEmployees(r.data)).catch(() => {});
  }, [currentBranch]);

  const handleClose = async () => {
    if (!window.confirm(`Close accounts for ${date}? This cannot be undone.`)) return;
    try {
      const res = await api.post('/daily-close', { ...closeForm, date, branch_id: currentBranch.id });
      toast.success(`Day closed! Extra cash: ${formatPHP(res.data.extra_cash)}`);
      setClosing(res.data);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error closing day'); }
  };

  const handleExpense = async () => {
    try {
      if (expenseType === 'farm') {
        await api.post('/expenses/farm', { ...expForm, branch_id: currentBranch?.id, date });
      } else if (expenseType === 'advance') {
        await api.post('/expenses/employee-advance', { ...expForm, branch_id: currentBranch?.id, date });
      } else {
        await api.post('/expenses', { ...expForm, branch_id: currentBranch?.id, date });
      }
      toast.success('Expense recorded');
      setExpenseDialog(false);
      fetchReport();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const handleAddEmployee = async () => {
    try {
      await api.post('/employees', { ...empForm, branch_id: currentBranch?.id });
      toast.success('Employee added');
      setEmpDialog(false);
      api.get('/employees', { params: { branch_id: currentBranch?.id } }).then(r => setEmployees(r.data));
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const isClosed = closing?.status === 'closed';
  // Expected cash = cash from invoice payments + POS cash - expenses + previous drawer (NO double-counting)
  const expectedCash = report ? round2((report.total_cash_from_invoices || 0) - report.total_expenses + (closing?.previous_cashier_balance || 0)) : 0;

  function round2(n) { return Math.round((n || 0) * 100) / 100; }

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="daily-log-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Daily Operations</h1>
          <p className="text-sm text-slate-500">{currentBranch?.name} &middot; Sales Log, Profit & Day Close</p>
        </div>
        <div className="flex items-center gap-3">
          <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-40 h-9" data-testid="daily-date-picker" />
          {isClosed && <Badge className="bg-red-100 text-red-700"><Lock size={12} className="mr-1" /> Day Closed</Badge>}
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="log" data-testid="tab-log"><ClipboardList size={14} className="mr-1" /> Sales Log</TabsTrigger>
          <TabsTrigger value="profit" data-testid="tab-profit"><TrendingUp size={14} className="mr-1" /> Daily Profit</TabsTrigger>
          <TabsTrigger value="close" data-testid="tab-close"><Lock size={14} className="mr-1" /> Close Accounts</TabsTrigger>
        </TabsList>

        {/* SEQUENTIAL SALES LOG */}
        <TabsContent value="log" className="mt-4 space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-slate-500">{logEntries.length} entries</p>
            <Button variant="outline" size="sm" onClick={() => window.print()} data-testid="print-log"><Printer size={14} className="mr-1" /> Print</Button>
          </div>
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase text-slate-500 w-12">#</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 w-20">Time</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Product</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Customer</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Invoice</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Qty</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Price</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Discount</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Total</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Running</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {logEntries.map(e => (
                    <TableRow key={e.id} className="table-row-hover text-sm">
                      <TableCell className="font-mono text-xs text-slate-400">{e.sequence}</TableCell>
                      <TableCell className="font-mono text-xs">{e.time}</TableCell>
                      <TableCell className="font-medium">{e.product_name}</TableCell>
                      <TableCell className="text-slate-500 text-xs">{e.customer_name}</TableCell>
                      <TableCell className="font-mono text-xs text-slate-400">{e.invoice_number}</TableCell>
                      <TableCell className="text-right">{e.quantity}</TableCell>
                      <TableCell className="text-right">{formatPHP(e.unit_price)}</TableCell>
                      <TableCell className="text-right">{e.discount > 0 ? formatPHP(e.discount) : '—'}</TableCell>
                      <TableCell className="text-right font-semibold">{formatPHP(e.line_total)}</TableCell>
                      <TableCell className="text-right font-bold text-[#1A4D2E]">{formatPHP(e.running_total)}</TableCell>
                    </TableRow>
                  ))}
                  {!logEntries.length && <TableRow><TableCell colSpan={10} className="text-center py-8 text-slate-400">No sales logged for {date}</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* DAILY PROFIT */}
        <TabsContent value="profit" className="mt-4 space-y-4">
          {report ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {[
                  { label: 'New Sales Today', value: report.new_sales_today, color: 'text-emerald-600', bg: 'bg-emerald-50', icon: ArrowUp },
                  { label: 'COGS', value: report.total_cogs, color: 'text-slate-600', bg: 'bg-slate-50', icon: ArrowDown },
                  { label: 'Gross Profit', value: report.gross_profit, color: report.gross_profit >= 0 ? 'text-emerald-600' : 'text-red-600', bg: 'bg-white', icon: TrendingUp },
                  { label: 'Expenses', value: report.total_expenses, color: 'text-red-600', bg: 'bg-red-50', icon: ArrowDown },
                  { label: 'Net Profit', value: report.net_profit, color: report.net_profit >= 0 ? 'text-emerald-700' : 'text-red-700', bg: report.net_profit >= 0 ? 'bg-emerald-50' : 'bg-red-50', icon: DollarSign },
                ].map((kpi, i) => (
                  <Card key={i} className="border-slate-200"><CardContent className={`p-4 ${kpi.bg}`}>
                    <div className="flex items-center gap-1 mb-1"><kpi.icon size={14} className={kpi.color} /><span className="text-xs text-slate-500 uppercase">{kpi.label}</span></div>
                    <p className={`text-xl font-bold ${kpi.color}`} style={{ fontFamily: 'Manrope' }}>{formatPHP(kpi.value)}</p>
                  </CardContent></Card>
                ))}
              </div>
              {/* Sales by Category */}
              <Card className="border-slate-200">
                <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Sales by Category</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {Object.entries(report.sales_by_category || {}).map(([cat, data]) => (
                      <div key={cat} className="flex justify-between items-center p-2 rounded bg-slate-50">
                        <span className="font-medium text-sm">{cat}</span>
                        <span className="font-bold">{formatPHP(data.total)}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
              {/* Expenses */}
              <Card className="border-slate-200">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Expenses</CardTitle>
                  {!isClosed && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => { setExpenseType('other'); setExpForm({ category: '', description: '', amount: 0 }); setExpenseDialog(true); }}><Plus size={12} className="mr-1" /> Expense</Button>
                      <Button size="sm" variant="outline" onClick={() => { setExpenseType('advance'); setExpForm({ amount: 0, employee_id: '', employee_name: '' }); setExpenseDialog(true); }}>Advance</Button>
                      <Button size="sm" variant="outline" onClick={() => { setExpenseType('farm'); setExpForm({ amount: 0, customer_id: '', tag: '' }); setExpenseDialog(true); }}>Farm</Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  {report.expenses?.length ? report.expenses.map((e, i) => (
                    <div key={i} className="flex justify-between items-center p-2 rounded bg-slate-50 mb-1">
                      <div><Badge variant="outline" className="text-[10px] mr-2">{e.category}</Badge><span className="text-sm">{e.description}</span></div>
                      <span className="font-bold text-red-600">{formatPHP(e.amount)}</span>
                    </div>
                  )) : <p className="text-sm text-slate-400">No expenses recorded</p>}
                </CardContent>
              </Card>
            </>
          ) : <p className="text-center py-8 text-slate-400">Loading report...</p>}
        </TabsContent>

        {/* CLOSE ACCOUNTS */}
        <TabsContent value="close" className="mt-4 space-y-4">
          {isClosed ? (
            /* Show closed report */
            <div className="space-y-4">
              <Card className="border-emerald-200 bg-emerald-50"><CardContent className="p-4">
                <p className="font-bold text-emerald-800">Day Closed by {closing.closed_by_name} at {new Date(closing.closed_at).toLocaleString()}</p>
              </CardContent></Card>
              <div className="grid md:grid-cols-2 gap-4">
                <Card className="border-slate-200"><CardContent className="p-4 space-y-2 text-sm">
                  <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>General Details</h3>
                  <div className="flex justify-between"><span className="text-slate-500">Safe Balance</span><span className="font-bold">{formatPHP(closing.safe_balance)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Cash to Safe Today</span><span className="font-bold">{formatPHP(closing.cash_deposited_to_safe)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Prev Drawer Balance</span><span>{formatPHP(closing.previous_cashier_balance)}</span></div>
                </CardContent></Card>
                <Card className="border-slate-200"><CardContent className="p-4 space-y-2 text-sm">
                  <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>Cash Count</h3>
                  <div className="flex justify-between"><span className="text-slate-500">Expected Cash</span><span>{formatPHP(closing.expected_cash)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Actual Cash</span><span className="font-bold">{formatPHP(closing.actual_cash)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Checks</span><span>{formatPHP(closing.bank_checks)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Other (GCash etc.)</span><span>{formatPHP(closing.other_payment_forms)}</span></div>
                  <Separator />
                  <div className="flex justify-between"><span className="text-slate-500">Extra Cash</span><span className={`font-bold ${closing.extra_cash >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{formatPHP(closing.extra_cash)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Cash to Drawer</span><span>{formatPHP(closing.cash_to_drawer)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Cash to Safe</span><span>{formatPHP(closing.cash_to_safe)}</span></div>
                </CardContent></Card>
              </div>
              <Card className="border-slate-200"><CardContent className="p-4 space-y-2 text-sm">
                <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>Sales by Category</h3>
                {Object.entries(closing.sales_by_category || {}).map(([cat, total]) => (
                  <div key={cat} className="flex justify-between"><span>{cat}</span><span className="font-bold">{formatPHP(total)}</span></div>
                ))}
                <Separator />
                <div className="flex justify-between font-bold"><span>Total Sales</span><span>{formatPHP(closing.total_sales)}</span></div>
              </CardContent></Card>
              {closing.payments_received?.length > 0 && (
                <Card className="border-slate-200"><CardContent className="p-4 text-sm">
                  <h3 className="font-bold mb-2" style={{ fontFamily: 'Manrope' }}>Payments Received</h3>
                  <Table><TableHeader><TableRow>
                    <TableHead className="text-xs">Customer</TableHead><TableHead className="text-xs">Invoice</TableHead>
                    <TableHead className="text-xs text-right">Principal</TableHead><TableHead className="text-xs text-right">Interest</TableHead>
                    <TableHead className="text-xs text-right">Total Paid</TableHead><TableHead className="text-xs text-right">Open Bal</TableHead>
                  </TableRow></TableHeader><TableBody>
                    {closing.payments_received.map((p, i) => (
                      <TableRow key={i}><TableCell>{p.customer}</TableCell><TableCell className="font-mono text-xs">{p.invoice}</TableCell>
                        <TableCell className="text-right">{formatPHP(p.principal_paid)}</TableCell>
                        <TableCell className="text-right text-amber-600">{formatPHP(p.interest_paid)}</TableCell>
                        <TableCell className="text-right font-bold">{formatPHP(p.total_paid)}</TableCell>
                        <TableCell className="text-right">{formatPHP(p.balance)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody></Table>
                </CardContent></Card>
              )}
            </div>
          ) : (
            /* Close Form */
            <div className="space-y-4">
              <Card className="border-amber-200 bg-amber-50"><CardContent className="p-4">
                <p className="text-sm text-amber-800 font-medium"><AlertTriangle size={14} className="inline mr-1" /> This will lock all transactions for {date}. New sales will go to the next day.</p>
              </CardContent></Card>
              {/* Summary */}
              {report && (
                <div className="grid md:grid-cols-3 gap-4 text-sm">
                  <Card className="border-slate-200"><CardContent className="p-4">
                    <p className="text-xs text-slate-500 uppercase mb-1">Total Sales</p>
                    <p className="text-xl font-bold text-emerald-600">{formatPHP(report.total_revenue)}</p>
                  </CardContent></Card>
                  <Card className="border-slate-200"><CardContent className="p-4">
                    <p className="text-xs text-slate-500 uppercase mb-1">Total Payments Received</p>
                    <p className="text-xl font-bold text-blue-600">{formatPHP(report.total_payments)}</p>
                  </CardContent></Card>
                  <Card className="border-slate-200"><CardContent className="p-4">
                    <p className="text-xs text-slate-500 uppercase mb-1">Total Expenses</p>
                    <p className="text-xl font-bold text-red-600">{formatPHP(report.total_expenses)}</p>
                  </CardContent></Card>
                </div>
              )}
              <Card className="border-slate-200"><CardContent className="p-5 space-y-4">
                <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>Cash Counting</h3>
                <p className="text-sm text-slate-500">Expected Cash in Drawer: <span className="font-bold text-slate-800">{formatPHP(expectedCash)}</span></p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div><Label className="text-xs">Actual Cash Count</Label><Input data-testid="actual-cash" type="number" value={closeForm.actual_cash} onChange={e => setCloseForm({ ...closeForm, actual_cash: parseFloat(e.target.value) || 0 })} className="h-10 text-lg font-bold" /></div>
                  <div><Label className="text-xs">Bank Checks</Label><Input type="number" value={closeForm.bank_checks} onChange={e => setCloseForm({ ...closeForm, bank_checks: parseFloat(e.target.value) || 0 })} className="h-10" /></div>
                  <div><Label className="text-xs">Other (GCash, etc.)</Label><Input type="number" value={closeForm.other_payment_forms} onChange={e => setCloseForm({ ...closeForm, other_payment_forms: parseFloat(e.target.value) || 0 })} className="h-10" /></div>
                  <div>
                    <Label className="text-xs">Extra Cash</Label>
                    <div className={`h-10 flex items-center px-3 rounded-md text-lg font-bold ${(closeForm.actual_cash - (expectedCash - closeForm.bank_checks - closeForm.other_payment_forms)) >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                      {formatPHP(round2(closeForm.actual_cash - (expectedCash - closeForm.bank_checks - closeForm.other_payment_forms)))}
                    </div>
                  </div>
                </div>
                <Separator />
                <h3 className="font-bold" style={{ fontFamily: 'Manrope' }}>End-of-Day Allocation</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div><Label className="text-xs">Cash Remaining in Drawer</Label><Input data-testid="cash-to-drawer" type="number" value={closeForm.cash_to_drawer} onChange={e => setCloseForm({ ...closeForm, cash_to_drawer: parseFloat(e.target.value) || 0 })} className="h-10" /></div>
                  <div><Label className="text-xs">Cash to Transfer to Safe</Label><Input data-testid="cash-to-safe" type="number" value={closeForm.cash_to_safe} onChange={e => setCloseForm({ ...closeForm, cash_to_safe: parseFloat(e.target.value) || 0 })} className="h-10" /></div>
                </div>
                <Button data-testid="close-day-btn" onClick={handleClose} className="w-full h-12 bg-red-600 hover:bg-red-700 text-white text-base">
                  <Lock size={16} className="mr-2" /> Close Accounts for {date}
                </Button>
              </CardContent></Card>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Expense Dialog */}
      <Dialog open={expenseDialog} onOpenChange={setExpenseDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>
            {expenseType === 'farm' ? 'Farm Expense' : expenseType === 'advance' ? 'Employee Cash Advance' : 'Record Expense'}
          </DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            {expenseType === 'other' && (
              <div><Label>Category</Label><Input value={expForm.category} onChange={e => setExpForm({ ...expForm, category: e.target.value })} placeholder="e.g. Utilities, Supplies" /></div>
            )}
            {expenseType === 'farm' && (
              <>
                <div><Label>Customer / Farm</Label>
                  <Select value={expForm.customer_id} onValueChange={v => setExpForm({ ...expForm, customer_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Select customer" /></SelectTrigger>
                    <SelectContent>{customers.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>Tag (purpose)</Label><Input value={expForm.tag} onChange={e => setExpForm({ ...expForm, tag: e.target.value })} placeholder="e.g. Tilling, Harvesting, Spraying" /></div>
              </>
            )}
            {expenseType === 'advance' && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Employee</Label>
                  <Button variant="ghost" size="sm" onClick={() => { setEmpForm({ name: '', position: '', phone: '' }); setEmpDialog(true); }} className="text-xs">+ Add Employee</Button>
                </div>
                <Select value={expForm.employee_id} onValueChange={v => {
                  const emp = employees.find(e => e.id === v);
                  setExpForm({ ...expForm, employee_id: v, employee_name: emp?.name || '' });
                }}>
                  <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
                  <SelectContent>{employees.map(e => (
                    <SelectItem key={e.id} value={e.id}>{e.name} {e.monthly_advance_total > 0 ? `(₱${e.monthly_advance_total} this month)` : ''}</SelectItem>
                  ))}</SelectContent>
                </Select>
              </div>
            )}
            <div><Label>Description</Label><Input value={expForm.description} onChange={e => setExpForm({ ...expForm, description: e.target.value })} /></div>
            <div><Label>Amount</Label><Input type="number" value={expForm.amount} onChange={e => setExpForm({ ...expForm, amount: parseFloat(e.target.value) || 0 })} className="h-11 text-lg font-bold" /></div>
            <Button onClick={handleExpense} className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Employee Dialog */}
      <Dialog open={empDialog} onOpenChange={setEmpDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Add Employee</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div><Label>Name</Label><Input value={empForm.name} onChange={e => setEmpForm({ ...empForm, name: e.target.value })} /></div>
            <div><Label>Position</Label><Input value={empForm.position} onChange={e => setEmpForm({ ...empForm, position: e.target.value })} /></div>
            <Button onClick={handleAddEmployee} className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white">Add</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
