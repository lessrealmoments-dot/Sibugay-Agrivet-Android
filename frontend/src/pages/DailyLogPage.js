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
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  ClipboardList, TrendingUp, Lock, Printer, Calendar,
  DollarSign, ArrowDown, ArrowUp, AlertTriangle, Plus, CheckCircle, FileWarning,
  Archive, Eye, RefreshCw, Building2
} from 'lucide-react';
import { toast } from 'sonner';

// ── Small helper components ───────────────────────────────────────────────────
function SectionCard({ title, children, accent = 'slate', note }) {
  const borders = { emerald: 'border-emerald-200', blue: 'border-blue-200', red: 'border-red-200', amber: 'border-amber-200', slate: 'border-slate-200', indigo: 'border-indigo-200' };
  const headers = { emerald: 'bg-emerald-50 text-emerald-800', blue: 'bg-blue-50 text-blue-800', red: 'bg-red-50 text-red-800', amber: 'bg-amber-50 text-amber-800', slate: 'bg-slate-50 text-slate-700', indigo: 'bg-indigo-50 text-indigo-800' };
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
          <InfoRow label="Opening Float" value={formatPHP(data.starting_float)} bold className="text-emerald-700" />
        </SectionCard>
        <SectionCard title="Cash Reconciliation">
          <InfoRow label="Expected in Counter" value={formatPHP(data.expected_counter)} />
          <InfoRow label="Actual Cash Counted" value={formatPHP(data.actual_cash)} bold />
          <Separator className="my-1" />
          <InfoRow label={data.over_short >= 0 ? 'Cash Over' : 'Cash Short'}
            value={`${data.over_short >= 0 ? '+' : ''}${formatPHP(data.over_short)}`}
            bold className={data.over_short >= 0 ? 'text-emerald-600' : 'text-red-600'} />
          <InfoRow label="Transferred to Vault" value={formatPHP(data.cash_to_safe)} />
          <InfoRow label="Opening Float (Next Day)" value={formatPHP(data.cash_to_drawer)} bold className="text-emerald-600" />
        </SectionCard>
      </div>

      <SectionCard title={`Walk-in Sales — ${formatPHP(data.total_cash_sales)}`} accent="emerald">
        {Object.entries(data.sales_by_category || {}).map(([cat, total]) => (
          <div key={cat} className="flex justify-between text-sm py-1 border-b border-slate-100 last:border-0">
            <span>{cat}</span><span className="font-semibold font-mono">{formatPHP(total)}</span>
          </div>
        ))}
      </SectionCard>

      {/* New Credit Extended Today */}
      {((data.credit_sales_today?.length > 0) || (data.ar_credits_today?.length > 0)) && (
        <SectionCard title={`New Credit Extended Today — ${formatPHP(data.total_new_credit || 0)}`} accent="amber" note="Not counted as cash received — added to AR">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="bg-amber-50 text-xs text-slate-500 border-b">
                <th className="px-3 py-1.5 text-left">Customer</th>
                <th className="px-3 py-1.5 text-left">Invoice</th>
                <th className="px-3 py-1.5 text-right">Amount</th>
                <th className="px-3 py-1.5 text-right">Balance</th>
                <th className="px-3 py-1.5 text-center">Type</th>
              </tr></thead>
              <tbody>
                {(data.credit_sales_today || []).map((c, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="px-3 py-1.5 font-medium">{c.customer_name}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-blue-600">{c.invoice_number}</td>
                    <td className="px-3 py-1.5 text-right font-mono font-semibold text-amber-700">{formatPHP(c.grand_total)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-slate-500">{formatPHP(c.balance)}</td>
                    <td className="px-3 py-1.5 text-center"><Badge className="text-[9px] bg-amber-100 text-amber-700">Credit</Badge></td>
                  </tr>
                ))}
                {(data.ar_credits_today || []).map((c, i) => (
                  <tr key={`arc-${i}`} className="border-b border-slate-100 last:border-0">
                    <td className="px-3 py-1.5 font-medium">{c.customer_name}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-blue-600">{c.invoice_number}</td>
                    <td className="px-3 py-1.5 text-right font-mono font-semibold text-blue-700">{formatPHP(c.grand_total)}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-slate-500">—</td>
                    <td className="px-3 py-1.5 text-center">
                      <Badge className={`text-[9px] ${c.type === 'cash_advance' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                        {c.type === 'cash_advance' ? 'Cash-out' : 'Farm'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

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

      {/* AR Running Total at Close */}
      {data.total_ar_at_close !== undefined && (
        <SectionCard title="AR Balance at Close" accent="indigo">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-600">Total Outstanding Accounts Receivable at close of {data.date}</p>
              <p className="text-xs text-slate-400 mt-0.5">All unpaid credit invoices across all customers for this branch</p>
            </div>
            <p className="text-2xl font-bold text-indigo-700 font-mono">{formatPHP(data.total_ar_at_close)}</p>
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
  const { currentBranch, branches, hasPerm } = useAuth();
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [tab, setTab] = useState('log');
  const [logEntries, setLogEntries] = useState([]);
  const [cashEntries, setCashEntries] = useState([]);
  const [creditInvoices, setCreditInvoices] = useState([]);
  const [logSummary, setLogSummary] = useState(null);
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

  // ── Z-Report Archive state ────────────────────────────────────────────────
  const [archiveRecords, setArchiveRecords] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveBranch, setArchiveBranch] = useState('all'); // 'all' or branch id
  const [archiveSearch, setArchiveSearch] = useState('');   // filter by date string
  const [zreportDialog, setZreportDialog] = useState(false);
  const [zreportData, setZreportData] = useState(null);
  const [zreportLoading, setZreportLoading] = useState(false);

  const fetchArchive = useCallback(async (branchId = 'all') => {
    setArchiveLoading(true);
    try {
      const params = { limit: 120 };
      if (branchId !== 'all') params.branch_id = branchId;
      const res = await api.get('/daily-variance-history', { params });
      setArchiveRecords(res.data.records || []);
    } catch { toast.error('Failed to load Z-report archive'); }
    setArchiveLoading(false);
  }, []);

  const openZreport = async (record) => {
    setZreportData(null);
    setZreportDialog(true);
    setZreportLoading(true);
    try {
      const res = await api.get(`/daily-close/${record.date}`, {
        params: { branch_id: record.branch_id }
      });
      setZreportData(res.data?.status === 'open' ? null : res.data);
    } catch { toast.error('Failed to load Z-report'); }
    setZreportLoading(false);
  };

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
      setLogEntries(res.data.entries || []);
      setCashEntries(res.data.cash_entries || []);
      setCreditInvoices(res.data.credit_invoices || []);
      setLogSummary(res.data.summary || null);
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
  useEffect(() => { if (tab === 'variance') fetchVarianceHistory(); }, [tab, fetchVarianceHistory]);
  useEffect(() => {
    if (tab === 'archive') {
      const bid = currentBranch ? currentBranch.id : 'all';
      setArchiveBranch(bid);
      fetchArchive(bid);
    }
  }, [tab]); // eslint-disable-line
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
          <TabsTrigger value="variance" data-testid="tab-variance"><FileWarning size={14} className="mr-1" /> Variance Log</TabsTrigger>
          <TabsTrigger value="archive" data-testid="tab-archive"><Archive size={14} className="mr-1" /> Z-Report Archive</TabsTrigger>
        </TabsList>

        {/* ═══ SEQUENTIAL SALES LOG — Notebook Style ═══════════════ */}
        <TabsContent value="log" className="mt-4 space-y-0 print:mt-0" data-testid="sales-log-tab">
          {/* Header bar */}
          <div className="flex items-center justify-between mb-4 print:hidden">
            <div>
              <p className="text-sm text-slate-500">
                <span className="font-medium text-slate-700">{cashEntries.length}</span> cash sales
                {creditInvoices.length > 0 && <> · <span className="font-medium text-amber-600">{creditInvoices.length}</span> credit</>}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => window.print()} data-testid="print-log">
              <Printer size={14} className="mr-1" /> Print
            </Button>
          </div>

          {/* ── SECTION 1: CASH SALES ──────────────────────────────── */}
          <div className="border border-slate-200 rounded-xl overflow-hidden print:border-black print:rounded-none">
            {/* Section header */}
            <div className="bg-[#1A4D2E] text-white px-4 py-2.5 flex items-center justify-between print:bg-black">
              <div>
                <span className="font-bold text-sm tracking-wide uppercase">Walk-in Sales</span>
                <span className="text-emerald-200 text-xs ml-3">{currentBranch?.name} · {date}</span>
              </div>
              {logSummary && (
                <span className="font-mono font-bold text-emerald-200 text-sm">
                  {cashEntries.length} transactions
                </span>
              )}
            </div>

            {/* Cash sales table */}
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs uppercase text-slate-500 tracking-wide">
                  <th className="px-3 py-2 text-center w-10 font-semibold">#</th>
                  <th className="px-3 py-2 text-left w-16 font-semibold">Time</th>
                  <th className="px-3 py-2 text-left font-semibold">Product</th>
                  <th className="px-3 py-2 text-left font-semibold">Customer</th>
                  <th className="px-3 py-2 text-left font-semibold">Invoice</th>
                  <th className="px-3 py-2 text-right w-12 font-semibold">Qty</th>
                  <th className="px-3 py-2 text-right w-24 font-semibold">Unit Price</th>
                  <th className="px-3 py-2 text-right w-20 font-semibold">Disc</th>
                  <th className="px-3 py-2 text-right w-24 font-semibold">Total</th>
                  <th className="px-3 py-2 text-right w-28 font-semibold text-[#1A4D2E]">Running Total</th>
                </tr>
              </thead>
              <tbody>
                {cashEntries.length === 0 && (
                  <tr>
                    <td colSpan={10} className="text-center py-10 text-slate-400 italic">
                      No cash sales recorded for {date}
                    </td>
                  </tr>
                )}
                {cashEntries.map((e, idx) => (
                  <tr key={e.id || idx}
                    className={`border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors ${idx % 2 === 0 ? '' : 'bg-slate-50/30'}`}>
                    <td className="px-3 py-2 text-center font-mono text-xs text-slate-400 font-medium">{e.sequence}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-500">{e.time}</td>
                    <td className="px-3 py-2 font-medium text-slate-800">{e.product_name}</td>
                    <td className="px-3 py-2 text-slate-500 text-xs">{e.customer_name || 'Walk-in'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-400">{e.invoice_number}</td>
                    <td className="px-3 py-2 text-right text-slate-600">{e.quantity} <span className="text-slate-400 text-xs">{e.unit || ''}</span></td>
                    <td className="px-3 py-2 text-right font-mono">{formatPHP(e.unit_price)}</td>
                    <td className="px-3 py-2 text-right text-slate-400 text-xs">{e.discount > 0 ? formatPHP(e.discount) : '—'}</td>
                    <td className="px-3 py-2 text-right font-semibold font-mono">{formatPHP(e.line_total)}</td>
                    <td className="px-3 py-2 text-right font-bold font-mono text-[#1A4D2E]">{formatPHP(e.cash_running_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Cash subtotals by category + grand total */}
            {logSummary && cashEntries.length > 0 && (
              <div className="border-t-2 border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex flex-wrap gap-x-6 gap-y-1 mb-2">
                  {Object.entries(logSummary.cash_by_category || {}).map(([cat, total]) => (
                    <div key={cat} className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500">{cat}:</span>
                      <span className="font-semibold font-mono">{formatPHP(total)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between items-center border-t border-slate-200 pt-2">
                  <span className="text-sm font-bold text-slate-700 uppercase tracking-wide">Total Walk-in Sales</span>
                  <span className="font-mono font-bold text-lg text-[#1A4D2E]">{formatPHP(logSummary.total_cash)}</span>
                </div>
              </div>
            )}
          </div>

          {/* ── SECTION 2: ACCOUNTS RECEIVABLE ─────────────────────── */}
          {creditInvoices.length > 0 && (
            <div className="border border-amber-200 rounded-xl overflow-hidden mt-4 print:border-black print:rounded-none print:mt-6">
              {/* AR section header */}
              <div className="bg-amber-600 text-white px-4 py-2.5 flex items-center justify-between print:bg-black">
                <div>
                  <span className="font-bold text-sm tracking-wide uppercase">Accounts Receivable — New Credit Today</span>
                  <span className="text-amber-100 text-xs ml-3">{creditInvoices.length} customer{creditInvoices.length !== 1 ? 's' : ''}</span>
                </div>
                <span className="font-mono font-bold text-amber-100 text-sm">
                  {formatPHP(logSummary?.total_credit || 0)}
                </span>
              </div>

              {/* Per-customer credit details */}
              <div className="divide-y divide-amber-100">
                {creditInvoices.map((inv, ci) => {
                  const items = inv.items || [];
                  const invoiceTotal = parseFloat(inv.grand_total || 0);
                  const amountPaid = parseFloat(inv.amount_paid || 0);
                  const balance = parseFloat(inv.balance || invoiceTotal - amountPaid);
                  return (
                    <div key={inv.id || ci} className="p-4">
                      {/* Customer header */}
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <span className="font-bold text-slate-800 text-base">{inv.customer_name || 'Unknown Customer'}</span>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="font-mono text-xs text-slate-400">{inv.invoice_number}</span>
                            <Badge className={`text-[9px] border-0 ${inv.payment_type === 'partial' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                              {inv.payment_type === 'partial' ? 'PARTIAL PAYMENT' : 'FULL CREDIT'}
                            </Badge>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono font-bold text-slate-800">{formatPHP(invoiceTotal)}</div>
                          {amountPaid > 0 && (
                            <div className="text-xs text-slate-500">Paid: {formatPHP(amountPaid)} · Balance: <span className="text-red-600 font-semibold">{formatPHP(balance)}</span></div>
                          )}
                        </div>
                      </div>

                      {/* Items list — notebook style */}
                      <div className="ml-2">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-xs text-slate-400 border-b border-slate-100">
                              <th className="pb-1 text-left w-6 font-normal">#</th>
                              <th className="pb-1 text-left font-normal">Product</th>
                              <th className="pb-1 text-right w-16 font-normal">Qty</th>
                              <th className="pb-1 text-right w-24 font-normal">Unit Price</th>
                              <th className="pb-1 text-right w-20 font-normal">Disc</th>
                              <th className="pb-1 text-right w-24 font-normal">Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {items.map((item, ii) => (
                              <tr key={ii} className="border-b border-slate-50 last:border-0">
                                <td className="py-1 text-slate-300 text-xs">{ii + 1}.</td>
                                <td className="py-1 font-medium text-slate-700">{item.product_name}</td>
                                <td className="py-1 text-right text-slate-600">{item.quantity}</td>
                                <td className="py-1 text-right font-mono">{formatPHP(item.rate || item.price || 0)}</td>
                                <td className="py-1 text-right text-slate-400 text-xs">
                                  {parseFloat(item.discount_amount || 0) > 0 ? formatPHP(item.discount_amount) : '—'}
                                </td>
                                <td className="py-1 text-right font-semibold font-mono">{formatPHP(item.total)}</td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="border-t border-amber-200 bg-amber-50/50">
                              <td colSpan={5} className="pt-1.5 text-sm font-semibold text-amber-800">
                                Total Credit — {inv.customer_name}
                              </td>
                              <td className="pt-1.5 text-right font-bold font-mono text-amber-800">{formatPHP(invoiceTotal)}</td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* AR grand total */}
              <div className="border-t-2 border-amber-200 bg-amber-50 px-4 py-3 flex justify-between items-center">
                <span className="text-sm font-bold text-amber-800 uppercase tracking-wide">Total New Credit Today</span>
                <span className="font-mono font-bold text-lg text-amber-700">{formatPHP(logSummary?.total_credit || 0)}</span>
              </div>
            </div>
          )}

          {/* ── SUMMARY STRIP ──────────────────────────────────────── */}
          {logSummary && (cashEntries.length > 0 || creditInvoices.length > 0) && (
            <div className="mt-4 bg-slate-800 text-white rounded-xl px-5 py-4 flex flex-wrap gap-6 items-center justify-between print:bg-black">
              <div className="flex gap-6">
                <div>
                  <div className="text-xs text-slate-400 uppercase tracking-wide">Walk-in Sales</div>
                  <div className="font-mono font-bold text-emerald-400">{formatPHP(logSummary.total_cash)}</div>
                </div>
                {logSummary.total_credit > 0 && (
                  <div>
                    <div className="text-xs text-slate-400 uppercase tracking-wide">New Credit</div>
                    <div className="font-mono font-bold text-amber-400">{formatPHP(logSummary.total_credit)}</div>
                  </div>
                )}
              </div>
              <div className="text-right">
                <div className="text-xs text-slate-400 uppercase tracking-wide">Total Sales Today</div>
                <div className="font-mono font-bold text-xl">{formatPHP(logSummary.grand_total)}</div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {cashEntries.length === 0 && creditInvoices.length === 0 && (
            <div className="text-center py-16 text-slate-400">
              <ClipboardList size={40} className="mx-auto mb-3 opacity-30" />
              <p>No sales recorded for {date}</p>
              <p className="text-xs mt-1">Sales will appear here as they are made</p>
            </div>
          )}
        </TabsContent>

        {/* DAILY PROFIT */}
        <TabsContent value="profit" className="mt-4 space-y-4">
          {report ? (
            <>
              {/* KPI row */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {[
                  { label: 'New Sales Today', value: report.new_sales_today, color: 'text-emerald-600', bg: 'bg-emerald-50', icon: ArrowUp },
                  { label: 'COGS', value: report.total_cogs, color: 'text-slate-600', bg: 'bg-slate-50', icon: ArrowDown },
                  { label: 'Gross Profit', value: report.gross_profit, color: report.gross_profit >= 0 ? 'text-emerald-600' : 'text-red-600', bg: 'bg-white', icon: TrendingUp },
                  { label: 'Real Expenses', value: report.total_expenses, color: 'text-red-600', bg: 'bg-red-50', icon: ArrowDown,
                    sub: report.total_all_expenses !== report.total_expenses
                      ? `(₱${(report.total_all_expenses - report.total_expenses).toLocaleString()} in credits excluded)` : null },
                  { label: 'Net Profit', value: report.net_profit, color: report.net_profit >= 0 ? 'text-emerald-700' : 'text-red-700', bg: report.net_profit >= 0 ? 'bg-emerald-50' : 'bg-red-50', icon: DollarSign },
                ].map((kpi, i) => (
                  <Card key={i} className="border-slate-200"><CardContent className={`p-4 ${kpi.bg}`}>
                    <div className="flex items-center gap-1 mb-1"><kpi.icon size={14} className={kpi.color} /><span className="text-xs text-slate-500 uppercase">{kpi.label}</span></div>
                    <p className={`text-xl font-bold ${kpi.color}`} style={{ fontFamily: 'Manrope' }}>{formatPHP(kpi.value)}</p>
                    {kpi.sub && <p className="text-[10px] text-slate-400 mt-0.5">{kpi.sub}</p>}
                  </CardContent></Card>
                ))}
              </div>

              {/* Formula explanation */}
              <div className="px-4 py-2 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
                <span>Net Profit =</span>
                <span className="text-emerald-600 font-medium">Sales {formatPHP(report.new_sales_today)}</span>
                <span>−</span>
                <span className="text-slate-600 font-medium">COGS {formatPHP(report.total_cogs)}</span>
                <span>−</span>
                <span className="text-red-600 font-medium">Expenses {formatPHP(report.total_expenses)}</span>
                <span>=</span>
                <span className={`font-bold ${report.net_profit >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>{formatPHP(report.net_profit)}</span>
                <span className="ml-1 text-slate-400">· Credits {formatPHP(report.total_credit_expenses || 0)} excluded (AR)</span>
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

              {/* Real Expenses (P&L) */}
              <Card className="border-slate-200">
                <CardHeader className="pb-2 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>Expenses (P&L)</CardTitle>
                    <p className="text-[10px] text-slate-400 mt-0.5">Actual cash outflows — included in Net Profit calculation</p>
                  </div>
                  {!isClosed && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="outline" onClick={() => { setExpenseType('other'); setExpForm({ category: '', description: '', amount: 0 }); setExpenseDialog(true); }}><Plus size={12} className="mr-1" /> Expense</Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  {report.expenses?.length ? report.expenses.map((e, i) => (
                    <div key={i} className="flex justify-between items-center p-2 rounded bg-slate-50 mb-1">
                      <div><Badge variant="outline" className="text-[10px] mr-2">{e.category}</Badge><span className="text-sm">{e.description}</span></div>
                      <span className="font-bold text-red-600">{formatPHP(e.amount)}</span>
                    </div>
                  )) : <p className="text-sm text-slate-400">No operational expenses today</p>}
                  {report.expenses?.length > 0 && (
                    <div className="flex justify-between font-bold text-sm pt-2 border-t border-slate-200 mt-2">
                      <span>Total Expenses</span>
                      <span className="text-red-600">{formatPHP(report.total_expenses)}</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Credits Extended Today — AR section, NOT included in P&L */}
              {((report.credit_expenses?.length > 0) || (report.advance_expenses?.length > 0)) && (
                <Card className="border-blue-200 bg-blue-50/30">
                  <CardHeader className="pb-2 flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-semibold text-blue-800" style={{ fontFamily: 'Manrope' }}>
                        Credits Extended Today
                      </CardTitle>
                      <p className="text-[10px] text-blue-600 mt-0.5">
                        Money out that comes BACK — these are receivables/assets, NOT included in Net Profit
                      </p>
                    </div>
                    {!isClosed && (
                      <div className="flex gap-1">
                        <Button size="sm" variant="outline" className="border-blue-200 text-blue-700"
                          onClick={() => { setExpenseType('advance'); setExpForm({ amount: 0, employee_id: '', employee_name: '' }); setExpenseDialog(true); }}>
                          CA
                        </Button>
                        <Button size="sm" variant="outline" className="border-blue-200 text-blue-700"
                          onClick={() => { setExpenseType('farm'); setExpForm({ amount: 0, customer_id: '', tag: '' }); setExpenseDialog(true); }}>
                          Farm
                        </Button>
                      </div>
                    )}
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Customer Credits (Cash Out + Farm Expense) */}
                    {report.credit_expenses?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-blue-700 mb-1 uppercase tracking-wide">Customer Credits (AR)</p>
                        {report.credit_expenses.map((e, i) => (
                          <div key={i} className="flex justify-between items-center p-2 rounded bg-white border border-blue-100 mb-1">
                            <div>
                              <Badge className="text-[10px] mr-2 bg-blue-100 text-blue-700 border-0">{e.category}</Badge>
                              <span className="text-sm">{e.description}</span>
                            </div>
                            <div className="text-right">
                              <span className="font-bold text-blue-700">{formatPHP(e.amount)}</span>
                              <p className="text-[10px] text-blue-400">Owed back</p>
                            </div>
                          </div>
                        ))}
                        <div className="flex justify-between text-sm font-medium text-blue-700 pt-1 border-t border-blue-200">
                          <span>Total Customer Credits</span>
                          <span>{formatPHP(report.total_credit_expenses)}</span>
                        </div>
                      </div>
                    )}
                    {/* Employee Advances */}
                    {report.advance_expenses?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-blue-700 mb-1 uppercase tracking-wide">Employee Advances (Asset)</p>
                        {report.advance_expenses.map((e, i) => (
                          <div key={i} className="flex justify-between items-center p-2 rounded bg-white border border-blue-100 mb-1">
                            <div>
                              <Badge className="text-[10px] mr-2 bg-indigo-100 text-indigo-700 border-0">{e.category}</Badge>
                              <span className="text-sm">{e.description || e.employee_name}</span>
                            </div>
                            <div className="text-right">
                              <span className="font-bold text-indigo-700">{formatPHP(e.amount)}</span>
                              <p className="text-[10px] text-indigo-400">Salary deduction</p>
                            </div>
                          </div>
                        ))}
                        <div className="flex justify-between text-sm font-medium text-indigo-700 pt-1 border-t border-blue-200">
                          <span>Total Advances</span>
                          <span>{formatPHP(report.total_advance_expenses)}</span>
                        </div>
                      </div>
                    )}
                    {/* Total */}
                    <div className="flex justify-between font-bold text-sm pt-2 border-t-2 border-blue-200">
                      <span className="text-blue-800">Total Credits Extended</span>
                      <span className="text-blue-700">{formatPHP((report.total_credit_expenses || 0) + (report.total_advance_expenses || 0))}</span>
                    </div>
                  </CardContent>
                </Card>
              )}
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

        {/* ═══ VARIANCE LOG ════════════════════════════════════════════ */}
        <TabsContent value="variance" className="mt-4 space-y-4" data-testid="variance-tab">
          <div>
            <h2 className="text-base font-semibold" style={{ fontFamily: 'Manrope' }}>Cash Variance Log</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Permanent record of daily over/short. Extra cash may indicate unrecorded sales.
              Short cash may indicate errors or missing expense records. Used during stock audits.
            </p>
          </div>

          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Branch</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Expected</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Actual</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500 text-right">Over / Short</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Notes</TableHead>
                    <TableHead className="text-xs uppercase text-slate-500">Closed By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {varianceHistory.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-10 text-slate-400">
                        <FileWarning size={32} className="mx-auto mb-2 opacity-30" />
                        No closed days yet. Variance records will appear here after each day close.
                      </TableCell>
                    </TableRow>
                  )}
                  {varianceHistory.map((r, i) => {
                    const os = r.over_short || 0;
                    return (
                      <TableRow key={r.id || i} className={os !== 0 ? (os > 0 ? 'bg-emerald-50/30' : 'bg-red-50/30') : ''}>
                        <TableCell className="font-mono text-sm font-medium">{r.date}</TableCell>
                        <TableCell className="text-sm text-slate-500">{r.branch_name}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{formatPHP(r.expected_counter)}</TableCell>
                        <TableCell className="text-right font-mono text-sm">{formatPHP(r.actual_cash)}</TableCell>
                        <TableCell className="text-right">
                          <span className={`font-mono font-bold text-sm ${os > 0 ? 'text-emerald-600' : os < 0 ? 'text-red-600' : 'text-slate-400'}`}>
                            {os > 0 ? '+' : ''}{formatPHP(os)}
                          </span>
                          {os !== 0 && (
                            <Badge className={`ml-2 text-[9px] border-0 ${os > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                              {os > 0 ? 'OVER' : 'SHORT'}
                            </Badge>
                          )}
                          {os === 0 && <span className="text-slate-300 text-xs ml-1">Balanced</span>}
                        </TableCell>
                        <TableCell className="text-sm text-slate-600 italic max-w-[200px] truncate">
                          {r.variance_notes || <span className="text-slate-300">—</span>}
                        </TableCell>
                        <TableCell className="text-sm text-slate-500">{r.closed_by_name}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Summary stats */}
          {varianceHistory.length > 0 && (
            <div className="grid grid-cols-3 gap-4">
              {(() => {
                const overDays = varianceHistory.filter(r => (r.over_short || 0) > 0);
                const shortDays = varianceHistory.filter(r => (r.over_short || 0) < 0);
                const totalOver = overDays.reduce((s, r) => s + (r.over_short || 0), 0);
                const totalShort = shortDays.reduce((s, r) => s + (r.over_short || 0), 0);
                return (<>
                  <Card className="border-emerald-200 bg-emerald-50">
                    <CardContent className="p-3">
                      <div className="text-xs text-emerald-600 font-medium">Days Over</div>
                      <div className="text-xl font-bold text-emerald-700">{overDays.length}</div>
                      <div className="text-xs text-emerald-500">Total +{formatPHP(totalOver)}</div>
                    </CardContent>
                  </Card>
                  <Card className="border-red-200 bg-red-50">
                    <CardContent className="p-3">
                      <div className="text-xs text-red-600 font-medium">Days Short</div>
                      <div className="text-xl font-bold text-red-700">{shortDays.length}</div>
                      <div className="text-xs text-red-500">Total {formatPHP(totalShort)}</div>
                    </CardContent>
                  </Card>
                  <Card className="border-slate-200">
                    <CardContent className="p-3">
                      <div className="text-xs text-slate-500 font-medium">Net Variance</div>
                      <div className={`text-xl font-bold ${(totalOver + totalShort) >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                        {formatPHP(totalOver + totalShort)}
                      </div>
                      <div className="text-xs text-slate-400">Across {varianceHistory.length} closed days</div>
                    </CardContent>
                  </Card>
                </>);
              })()}
            </div>
          )}
        </TabsContent>

        {/* ═══ Z-REPORT ARCHIVE ═══════════════════════════════════════ */}
        <TabsContent value="archive" className="mt-4 space-y-4" data-testid="archive-tab">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[180px]">
              <div className="relative">
                <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  placeholder="Filter by date (e.g. 2026-02)"
                  value={archiveSearch}
                  onChange={e => setArchiveSearch(e.target.value)}
                  className="pl-8 h-9 text-sm"
                  data-testid="archive-date-filter"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Building2 size={14} className="text-slate-400 shrink-0" />
              <Select
                value={archiveBranch}
                onValueChange={v => { setArchiveBranch(v); fetchArchive(v); }}
              >
                <SelectTrigger className="h-9 w-44 text-sm" data-testid="archive-branch-filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Branches</SelectItem>
                  {branches.map(b => (
                    <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="outline" size="sm"
              onClick={() => fetchArchive(archiveBranch)}
              disabled={archiveLoading}
              data-testid="archive-refresh-btn"
            >
              {archiveLoading
                ? <RefreshCw size={13} className="animate-spin" />
                : <RefreshCw size={13} />}
            </Button>
          </div>

          {/* Summary stats */}
          {archiveRecords.length > 0 && (() => {
            const filtered = archiveRecords.filter(r =>
              !archiveSearch || r.date.includes(archiveSearch) || (r.branch_name || '').toLowerCase().includes(archiveSearch.toLowerCase())
            );
            const totalSales   = filtered.reduce((s, r) => s + (r.total_cash_sales || 0), 0);
            const totalAR      = filtered.reduce((s, r) => s + (r.total_ar_received || 0), 0);
            const totalExp     = filtered.reduce((s, r) => s + (r.total_expenses || 0), 0);
            const totalOS      = filtered.reduce((s, r) => s + (r.over_short || 0), 0);
            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Closed Days', value: filtered.length, mono: false, color: 'slate' },
                  { label: 'Total Cash Sales', value: formatPHP(totalSales), mono: true, color: 'emerald' },
                  { label: 'Total AR Collected', value: formatPHP(totalAR), mono: true, color: 'blue' },
                  { label: 'Net Over / Short', value: (totalOS >= 0 ? '+' : '') + formatPHP(totalOS), mono: true, color: totalOS >= 0 ? 'emerald' : 'red' },
                ].map(({ label, value, mono, color }) => (
                  <Card key={label} className="border-slate-200">
                    <CardContent className="p-3">
                      <p className={`text-xs text-${color}-500 uppercase font-medium mb-0.5`}>{label}</p>
                      <p className={`text-xl font-bold text-${color}-700 ${mono ? 'font-mono' : ''}`}>{value}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            );
          })()}

          {/* Archive table */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <ScrollArea className="h-[450px]">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50 sticky top-0">
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Date</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Branch</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">Cash Sales</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">AR Collected</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">Expenses</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium text-right">Over / Short</TableHead>
                      <TableHead className="text-xs uppercase text-slate-500 font-medium">Closed By</TableHead>
                      <TableHead className="w-20"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {archiveLoading ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-10 text-slate-400">
                          <RefreshCw size={18} className="animate-spin mx-auto" />
                        </TableCell>
                      </TableRow>
                    ) : (() => {
                      const filtered = archiveRecords.filter(r =>
                        !archiveSearch || r.date.includes(archiveSearch) || (r.branch_name || '').toLowerCase().includes(archiveSearch.toLowerCase())
                      );
                      if (filtered.length === 0) return (
                        <TableRow>
                          <TableCell colSpan={8} className="text-center py-10 text-slate-400">
                            {archiveRecords.length === 0 ? 'No closed days yet.' : 'No results match your filter.'}
                          </TableCell>
                        </TableRow>
                      );
                      return filtered.map((r, i) => {
                        const os = r.over_short || 0;
                        return (
                          <TableRow key={r.id || i} className="table-row-hover">
                            <TableCell className="font-mono text-sm font-semibold">{r.date}</TableCell>
                            <TableCell className="text-sm text-slate-600">{r.branch_name || '—'}</TableCell>
                            <TableCell className="text-right font-mono text-emerald-700">{formatPHP(r.total_cash_sales || 0)}</TableCell>
                            <TableCell className="text-right font-mono text-blue-700">{formatPHP(r.total_ar_received || 0)}</TableCell>
                            <TableCell className="text-right font-mono text-red-600">{formatPHP(r.total_expenses || 0)}</TableCell>
                            <TableCell className="text-right font-mono">
                              <span className={os > 0 ? 'text-emerald-600 font-semibold' : os < 0 ? 'text-red-600 font-semibold' : 'text-slate-400'}>
                                {os > 0 ? '+' : ''}{formatPHP(os)}
                              </span>
                            </TableCell>
                            <TableCell className="text-sm text-slate-500">{r.closed_by_name}</TableCell>
                            <TableCell>
                              <Button
                                variant="outline" size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => openZreport(r)}
                                data-testid={`view-zreport-${r.date}`}
                              >
                                <Eye size={12} className="mr-1" /> View
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      });
                    })()}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── Z-Report Viewer Dialog ─────────────────────────────────── */}
      <Dialog open={zreportDialog} onOpenChange={setZreportDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader className="shrink-0 print:hidden">
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Archive size={18} className="text-[#1A4D2E]" />
              {zreportData ? `Z-Report — ${zreportData.date} · ${zreportData.branch_name || ''}` : 'Loading Z-Report...'}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="flex-1 overflow-auto">
            <div className="pr-2 py-1">
              {zreportLoading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw size={22} className="animate-spin text-slate-400" />
                </div>
              ) : zreportData ? (
                <ZReport
                  data={zreportData}
                  branchName={zreportData.branch_name || currentBranch?.name}
                  onPrint={() => window.print()}
                />
              ) : (
                <p className="text-center py-8 text-slate-400">Could not load Z-report data.</p>
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
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
