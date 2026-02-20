import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  ClipboardList, TrendingUp, Lock, Printer, Calendar,
  DollarSign, ArrowDown, ArrowUp, AlertTriangle, Plus, CheckCircle
} from 'lucide-react';
import { toast } from 'sonner';

// ── Small helper components ───────────────────────────────────────────────────
function SectionCard({ title, children, accent = 'slate', note }) {
  const borders = { emerald: 'border-emerald-200', blue: 'border-blue-200', red: 'border-red-200', amber: 'border-amber-200', slate: 'border-slate-200' };
  const headers = { emerald: 'bg-emerald-50 text-emerald-800', blue: 'bg-blue-50 text-blue-800', red: 'bg-red-50 text-red-800', amber: 'bg-amber-50 text-amber-800', slate: 'bg-slate-50 text-slate-700' };
  return (
    <Card className={`border ${borders[accent]}`}>
      <CardHeader className={`py-2.5 px-4 ${headers[accent]} border-b ${borders[accent]}`}>
        <CardTitle className="text-sm font-semibold flex items-center justify-between">
          <span>{title}</span>
          {note && <span className="text-[10px] font-normal opacity-70 italic">{note}</span>}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">{children}</CardContent>
    </Card>
  );
}

function InfoRow({ label, value, bold, className = '' }) {
  return (
    <div className="flex justify-between items-center text-sm py-0.5">
      <span className="text-slate-500">{label}</span>
      <span className={`font-mono ${bold ? 'font-bold' : ''} ${className}`}>{value}</span>
    </div>
  );
}

function ZReport({ data, branchName, onPrint }) {
  if (!data) return null;
  const r2 = n => Math.round((parseFloat(n) || 0) * 100) / 100;
  return (
    <div className="space-y-4 print:space-y-3">
      <div className="flex items-center justify-between print:hidden">
        <Card className="border-emerald-200 bg-emerald-50 flex-1 mr-3"><CardContent className="p-3">
          <p className="font-bold text-emerald-800">
            <CheckCircle size={14} className="inline mr-1" />
            Day closed by {data.closed_by_name} · {new Date(data.closed_at).toLocaleString()}
          </p>
        </CardContent></Card>
        <Button variant="outline" size="sm" onClick={onPrint}><Printer size={14} className="mr-1" /> Print</Button>
      </div>

      {/* Print header */}
      <div className="hidden print:block border-b-2 border-black pb-3 mb-3">
        <h1 className="text-xl font-bold">DAILY CLOSE REPORT — {branchName}</h1>
        <p>Date: {data.date} · Closed by: {data.closed_by_name}</p>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <SectionCard title="Opening">
          <InfoRow label="Safe Balance" value={formatPHP(data.safe_balance)} bold />
          <InfoRow label="Starting Cashier Float" value={formatPHP(data.starting_float)} bold className="text-emerald-700" />
        </SectionCard>
        <SectionCard title="Cash Reconciliation">
          <InfoRow label="Expected in Counter" value={formatPHP(data.expected_counter)} />
          <InfoRow label="Actual Cash Counted" value={formatPHP(data.actual_cash)} bold />
          <Separator className="my-1" />
          <InfoRow label={data.over_short >= 0 ? 'Cash Over' : 'Cash Short'}
            value={`${data.over_short >= 0 ? '+' : ''}${formatPHP(data.over_short)}`}
            bold className={data.over_short >= 0 ? 'text-emerald-600' : 'text-red-600'} />
          <InfoRow label="Transferred to Safe" value={formatPHP(data.cash_to_safe)} />
          <InfoRow label="Left in Register (tomorrow's float)" value={formatPHP(data.cash_to_drawer)} bold className="text-emerald-600" />
        </SectionCard>
      </div>

      <SectionCard title={`Cash Sales — ${formatPHP(data.total_cash_sales)}`} accent="emerald">
        {Object.entries(data.sales_by_category || {}).map(([cat, total]) => (
          <div key={cat} className="flex justify-between text-sm py-1 border-b border-slate-100 last:border-0">
            <span>{cat}</span><span className="font-semibold font-mono">{formatPHP(total)}</span>
          </div>
        ))}
      </SectionCard>

      {data.credit_collections?.length > 0 && (
        <SectionCard title={`AR Payments Received — ${formatPHP(data.total_ar_received)}`} accent="blue">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="bg-slate-50 text-xs text-slate-500 border-b">
                <th className="px-3 py-1.5 text-left">Customer</th>
                <th className="px-3 py-1.5 text-right">Bal Before</th>
                <th className="px-3 py-1.5 text-right">Interest</th>
                <th className="px-3 py-1.5 text-right">Penalty</th>
                <th className="px-3 py-1.5 text-right">Cash Paid</th>
                <th className="px-3 py-1.5 text-right">Remaining</th>
              </tr></thead>
              <tbody>
                {data.credit_collections.map((p, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="px-3 py-1.5">{p.customer}<div className="text-[10px] text-slate-400 font-mono">{p.invoice}</div></td>
                    <td className="px-3 py-1.5 text-right font-mono">{formatPHP(p.balance_before)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-amber-600">{p.interest_paid > 0 ? formatPHP(p.interest_paid) : '—'}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-red-500">{p.penalty_paid > 0 ? formatPHP(p.penalty_paid) : '—'}</td>
                    <td className="px-3 py-1.5 text-right font-mono font-bold text-blue-700">{formatPHP(p.total_paid)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-slate-500">{formatPHP(p.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <SectionCard title={`Expenses — ${formatPHP(data.total_expenses)}`} accent="red">
        {(data.expenses || []).map((e, i) => (
          <div key={i} className="py-1.5 border-b border-slate-100 last:border-0">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px]">{e.category}</Badge>
                <span className="text-sm">{e.description || e.employee_name || ''}</span>
              </div>
              <span className="font-semibold text-red-600 font-mono">{formatPHP(e.amount)}</span>
            </div>
            {e.category === 'Employee Advance' && e.monthly_ca_total !== undefined && (
              <div className="text-[10px] text-amber-600 ml-1 mt-0.5">
                {e.employee_name || 'Employee'} — monthly CA total: <span className="font-semibold">{formatPHP(e.monthly_ca_total)}</span>
              </div>
            )}
          </div>
        ))}
      </SectionCard>
    </div>
  );
}

export default function DailyLogPage() {
  const { currentBranch } = useAuth();
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [tab, setTab] = useState('log');
  const [logEntries, setLogEntries] = useState([]);
  const [report, setReport] = useState(null);
  const [closing, setClosing] = useState(null);
  const [preview, setPreview] = useState(null);  // Z-Report preview
  const [expenseDialog, setExpenseDialog] = useState(false);
  const [expenseType, setExpenseType] = useState('other');
  const [expForm, setExpForm] = useState({ category: '', description: '', amount: 0, customer_id: '', tag: '', employee_id: '', employee_name: '' });
  const [customers, setCustomers] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [empDialog, setEmpDialog] = useState(false);
  const [empForm, setEmpForm] = useState({ name: '', position: '', phone: '' });

  // Close form state
  const [actualCash, setActualCash] = useState('');
  const [cashToSafe, setCashToSafe] = useState('');
  const [cashToDrawer, setCashToDrawer] = useState('');
  const [adminPin, setAdminPin] = useState('');
  const [varianceNotes, setVarianceNotes] = useState('');
  const [closing_loading, setClosingLoading] = useState(false);
  const [varianceHistory, setVarianceHistory] = useState([]);

  const fetchVarianceHistory = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get('/daily-variance-history', { params: { branch_id: currentBranch.id, limit: 60 } });
      setVarianceHistory(res.data.records || []);
    } catch {}
  }, [currentBranch]);

  function r2(n) { return Math.round((parseFloat(n) || 0) * 100) / 100; }

  // Computed values
  const expectedCounter = preview?.expected_counter || 0;
  const actualNum = r2(actualCash);
  const overShort = actualCash !== '' ? r2(actualNum - expectedCounter) : null;
  const cashToDrawerNum = r2(cashToDrawer);
  const cashToSafeNum = r2(cashToSafe);

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

  const fetchPreview = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get('/daily-close-preview', { params: { date, branch_id: currentBranch.id } });
      setPreview(res.data);
    } catch {}
  }, [date, currentBranch]);

  const fetchClosing = useCallback(async () => {
    if (!currentBranch) return;
    try {
      const res = await api.get(`/daily-close/${date}`, { params: { branch_id: currentBranch.id } });
      setClosing(res.data);
    } catch {}
  }, [date, currentBranch]);

  useEffect(() => { fetchLog(); fetchReport(); fetchClosing(); fetchPreview(); }, [fetchLog, fetchReport, fetchClosing, fetchPreview]);
  useEffect(() => {
    api.get('/customers', { params: { limit: 500 } }).then(r => setCustomers(r.data.customers)).catch(() => {});
    if (currentBranch) api.get('/employees', { params: { branch_id: currentBranch.id } }).then(r => setEmployees(r.data)).catch(() => {});
  }, [currentBranch]);

  const handleClose = async () => {
    if (actualCash === '') { toast.error('Enter the actual cash count first'); return; }
    if (!cashToDrawer && cashToDrawer !== 0) { toast.error('Enter how much stays in the register'); return; }
    if (r2(cashToDrawerNum + cashToSafeNum) > r2(actualNum) + 0.01) {
      toast.error('Cash to safe + register cannot exceed actual cash count'); return;
    }
    if (!window.confirm(`Close accounts for ${date}? This cannot be undone.`)) return;
    setClosingLoading(true);
    try {
      const res = await api.post('/daily-close', {
        date, branch_id: currentBranch.id,
        actual_cash: actualNum,
        cash_to_safe: cashToSafeNum,
        cash_to_drawer: cashToDrawerNum,
        admin_pin: adminPin,
        variance_notes: varianceNotes,
      });
      toast.success('Day closed successfully!');
      setClosing(res.data);
      setAdminPin('');
    } catch (e) { toast.error(e.response?.data?.detail || 'Error closing day'); }
    setClosingLoading(false);
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

        {/* ═══ CLOSE ACCOUNTS / Z-REPORT ═══════════════════════════════ */}
        <TabsContent value="close" className="mt-4 space-y-0 print:mt-0">
          {isClosed ? (
            /* ── CLOSED: Show the Z-Report ── */
            <ZReport data={closing} branchName={currentBranch?.name} onPrint={() => window.print()} />
          ) : (
            /* ── OPEN: Cash Reconciliation Form ── */
            <div className="space-y-4">
              {!preview && <p className="text-center py-8 text-slate-400">Loading day data...</p>}
              {preview && (
                <>
                  {/* ── OPENING ─────────────────────────────────── */}
                  <SectionCard title="Opening">
                    <div className="grid grid-cols-2 gap-3">
                      <InfoRow label="Total Amount in Safe" value={formatPHP(preview.safe_balance)} bold className="text-slate-500" />
                      <InfoRow label="Starting Cashier Float" value={formatPHP(preview.starting_float)} bold className="text-emerald-600" />
                    </div>
                  </SectionCard>

                  {/* ── CASH SALES BY CATEGORY ──────────────────── */}
                  <SectionCard title={`Cash Sales Today — ${formatPHP(preview.total_cash_sales)}`} accent="emerald">
                    {preview.cash_sales_by_category?.length ? (
                      <div className="space-y-1">
                        {preview.cash_sales_by_category.map(c => (
                          <div key={c.category} className="flex justify-between text-sm py-1 border-b border-slate-100 last:border-0">
                            <span className="text-slate-600">{c.category}</span>
                            <span className="font-semibold font-mono">{formatPHP(c.total)}</span>
                          </div>
                        ))}
                        {preview.total_partial_cash > 0 && (
                          <div className="flex justify-between text-sm py-1">
                            <span className="text-slate-500 italic">Partial payments received today</span>
                            <span className="font-semibold font-mono">{formatPHP(preview.total_partial_cash)}</span>
                          </div>
                        )}
                        <div className="flex justify-between font-bold text-sm pt-1 border-t border-slate-200">
                          <span>Total Cash Received from Sales</span>
                          <span className="text-emerald-700">{formatPHP(r2(preview.total_cash_sales + preview.total_partial_cash))}</span>
                        </div>
                      </div>
                    ) : <p className="text-sm text-slate-400">No cash sales today</p>}
                  </SectionCard>

                  {/* ── NEW CREDIT TODAY (info only) ─────────────── */}
                  {preview.credit_sales_today?.length > 0 && (
                    <SectionCard title={`New Credit Sales Today — ${formatPHP(preview.total_credit_today)}`} accent="amber" note="Info only — not counted as cash received">
                      <div className="space-y-1">
                        {preview.credit_sales_today.map((c, i) => (
                          <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-slate-100 last:border-0">
                            <div>
                              <span className="font-medium">{c.customer_name}</span>
                              <span className="text-slate-400 text-xs ml-2">{c.invoice_number}</span>
                            </div>
                            <span className="font-mono text-amber-700">{formatPHP(c.grand_total)}</span>
                          </div>
                        ))}
                      </div>
                    </SectionCard>
                  )}

                  {/* ── AR PAYMENTS RECEIVED ─────────────────────── */}
                  <SectionCard title={`AR Payments Received Today — ${formatPHP(preview.total_ar_received)}`} accent="blue">
                    {preview.ar_payments?.length ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead><tr className="bg-slate-50 border-b border-slate-200 text-xs uppercase text-slate-500">
                            <th className="px-3 py-2 text-left">Customer</th>
                            <th className="px-3 py-2 text-right">Bal Before</th>
                            <th className="px-3 py-2 text-right">Interest</th>
                            <th className="px-3 py-2 text-right">Penalty</th>
                            <th className="px-3 py-2 text-right font-semibold text-blue-600">Cash Paid</th>
                            <th className="px-3 py-2 text-right">Remaining</th>
                          </tr></thead>
                          <tbody>
                            {preview.ar_payments.map((p, i) => (
                              <tr key={i} className="border-b border-slate-100 last:border-0">
                                <td className="px-3 py-2">
                                  <div className="font-medium">{p.customer_name}</div>
                                  <div className="text-xs text-slate-400 font-mono">{p.invoice_number}</div>
                                </td>
                                <td className="px-3 py-2 text-right font-mono">{formatPHP(p.balance_before)}</td>
                                <td className="px-3 py-2 text-right font-mono text-amber-600">{p.interest_paid > 0 ? formatPHP(p.interest_paid) : '—'}</td>
                                <td className="px-3 py-2 text-right font-mono text-red-500">{p.penalty_paid > 0 ? formatPHP(p.penalty_paid) : '—'}</td>
                                <td className="px-3 py-2 text-right font-mono font-bold text-blue-700">{formatPHP(p.amount_paid)}</td>
                                <td className="px-3 py-2 text-right font-mono text-slate-500">{formatPHP(p.remaining_balance)}</td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="border-t-2 border-blue-200 bg-blue-50/50">
                              <td className="px-3 py-2 font-bold text-blue-800" colSpan={4}>Total AR Cash Received</td>
                              <td className="px-3 py-2 text-right font-bold text-blue-700 font-mono">{formatPHP(preview.total_ar_received)}</td>
                              <td></td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    ) : <p className="text-sm text-slate-400">No AR payments received today</p>}
                  </SectionCard>

                  {/* ── EXPENSES ─────────────────────────────────── */}
                  <SectionCard title={`Expenses Today — ${formatPHP(preview.total_expenses)}`} accent="red">
                    {preview.expenses?.length ? (
                      <div className="space-y-1">
                        {preview.expenses.map((e, i) => (
                          <div key={i} className="py-1.5 border-b border-slate-100 last:border-0">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-[10px]">{e.category}</Badge>
                                <span className="text-sm">{e.description || e.employee_name || ''}</span>
                              </div>
                              <span className="font-semibold text-red-600 font-mono">{formatPHP(e.amount)}</span>
                            </div>
                            {/* Employee CA monthly running total */}
                            {e.category === 'Employee Advance' && e.monthly_ca_total !== undefined && (
                              <div className="text-[11px] text-amber-600 ml-1 mt-0.5">
                                {e.employee_name || 'Employee'} — running CA total this month: <span className="font-semibold">{formatPHP(e.monthly_ca_total)}</span>
                              </div>
                            )}
                          </div>
                        ))}
                        <div className="flex justify-between font-bold text-sm pt-1 border-t border-slate-200">
                          <span>Total Expenses</span>
                          <span className="text-red-600">{formatPHP(preview.total_expenses)}</span>
                        </div>
                      </div>
                    ) : <p className="text-sm text-slate-400">No expenses recorded today</p>}
                  </SectionCard>

                  {/* ── EXPECTED COUNTER ─────────────────────────── */}
                  <div className="bg-slate-800 text-white rounded-xl p-5">
                    <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Expected Money in Counter</div>
                    <div className="text-xs text-slate-400 mb-3">
                      Starting Float ({formatPHP(preview.starting_float)}) + Cash Sales ({formatPHP(r2(preview.total_cash_sales + preview.total_partial_cash))}) + AR Received ({formatPHP(preview.total_ar_received)}) − Expenses ({formatPHP(preview.total_expenses)})
                    </div>
                    <div className="text-3xl font-bold" style={{ fontFamily: 'Manrope' }}>{formatPHP(expectedCounter)}</div>
                  </div>

                  {/* ── ACTUAL CASH COUNT ────────────────────────── */}
                  <SectionCard title="Cash Count & Reconciliation">
                    <div className="space-y-4">
                      <div>
                        <Label className="font-semibold mb-1.5 block">Actual Cash in Counter <span className="text-red-500">*</span></Label>
                        <Input type="number" min={0} step="0.01"
                          value={actualCash}
                          onChange={e => {
                            setActualCash(e.target.value);
                            // Auto-fill cash to safe and drawer if not yet touched
                            const a = parseFloat(e.target.value) || 0;
                            if (!cashToDrawer && !cashToSafe) {
                              setCashToSafe(String(r2(a - 2000 > 0 ? a - 2000 : 0)));
                              setCashToDrawer(String(r2(Math.min(a, 2000))));
                            }
                          }}
                          className="h-12 text-xl font-bold font-mono"
                          placeholder="Enter actual cash counted"
                          data-testid="actual-cash-input" />
                      </div>

                      {actualCash !== '' && (
                        <div className={`p-4 rounded-lg flex items-center justify-between ${overShort >= 0 ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`}>
                          <div>
                            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                              {overShort >= 0 ? 'Cash Over (extra)' : 'Cash Short (deficit)'}
                            </div>
                            <div className="text-xs text-slate-400">Actual {formatPHP(actualNum)} − Expected {formatPHP(expectedCounter)}</div>
                          </div>
                          <div className={`text-2xl font-bold font-mono ${overShort >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                            {overShort >= 0 ? '+' : ''}{formatPHP(overShort)}
                          </div>
                        </div>
                      )}

                      {/* Variance notes — shown when there IS a discrepancy */}
                      {actualCash !== '' && overShort !== null && overShort !== 0 && (
                        <div>
                          <Label className="mb-1.5 block font-semibold">
                            {overShort > 0
                              ? 'Explain the extra cash (for audit trail)'
                              : 'Explain the shortage (for audit trail)'}
                            {' '}<span className="text-slate-400 font-normal text-xs">— stored permanently</span>
                          </Label>
                          <Textarea
                            value={varianceNotes}
                            onChange={e => setVarianceNotes(e.target.value)}
                            placeholder={overShort > 0
                              ? 'e.g. "Unrecorded walk-in sale of pesticide" or "Customer rounded up payment"'
                              : 'e.g. "Gave change for large bill" or "Cashier error on item #12"'}
                            className="text-sm resize-none"
                            rows={2}
                            data-testid="variance-notes-input"
                          />
                        </div>
                      )}

                      <Separator />
                      <div className="text-sm font-semibold text-slate-700">Distribution of Actual Cash</div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="mb-1.5 block">Transfer to Safe</Label>
                          <Input type="number" min={0} step="0.01" value={cashToSafe}
                            onChange={e => {
                              setCashToSafe(e.target.value);
                              setCashToDrawer(String(r2(actualNum - (parseFloat(e.target.value) || 0))));
                            }}
                            className="h-10 font-mono" data-testid="cash-to-safe-input" />
                        </div>
                        <div>
                          <Label className="mb-1.5 block">
                            Stays in Register
                            <span className="text-xs text-slate-400 font-normal ml-1">(= tomorrow's starting float)</span>
                          </Label>
                          <Input type="number" min={0} step="0.01" value={cashToDrawer}
                            onChange={e => {
                              setCashToDrawer(e.target.value);
                              setCashToSafe(String(r2(actualNum - (parseFloat(e.target.value) || 0))));
                            }}
                            className="h-10 font-mono font-bold bg-emerald-50 border-emerald-300" data-testid="cash-to-drawer-input" />
                          <p className="text-[10px] text-emerald-600 mt-0.5">This becomes the starting float for tomorrow</p>
                        </div>
                      </div>

                      {actualCash !== '' && cashToDrawer !== '' && (
                        <div className="text-xs text-slate-500 text-right">
                          Safe: {formatPHP(cashToSafeNum)} + Register: {formatPHP(cashToDrawerNum)} = {formatPHP(r2(cashToSafeNum + cashToDrawerNum))}
                          {Math.abs(r2(cashToSafeNum + cashToDrawerNum) - actualNum) > 0.01 && (
                            <span className="text-red-500 ml-2">⚠ Does not match actual cash</span>
                          )}
                        </div>
                      )}

                      <Separator />
                      <div>
                        <Label className="mb-1.5 block">Admin PIN to Confirm Close <span className="text-red-500">*</span></Label>
                        <Input type="password" value={adminPin} onChange={e => setAdminPin(e.target.value)}
                          placeholder="Enter admin PIN" maxLength={6} className="max-w-xs"
                          data-testid="admin-pin-close" />
                      </div>

                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
                        <AlertTriangle size={12} className="inline mr-1" />
                        Closing the day locks all transactions for {date}. New sales will roll to the next day.
                      </div>

                      <Button onClick={handleClose} disabled={closing_loading || actualCash === '' || !adminPin}
                        className="w-full h-12 bg-red-600 hover:bg-red-700 text-white text-base"
                        data-testid="close-day-btn">
                        {closing_loading
                          ? <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />Closing...</>
                          : <><Lock size={16} className="mr-2" /> Close Accounts for {date}</>}
                      </Button>
                    </div>
                  </SectionCard>
                </>
              )}
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
