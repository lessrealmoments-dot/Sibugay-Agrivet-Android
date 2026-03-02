import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import {
  BarChart3, ChevronDown, ChevronRight, Printer,
  TrendingUp, AlertCircle, DollarSign, Calendar, RefreshCw, Filter
} from 'lucide-react';
import { toast } from 'sonner';
import InvoiceDetailModal from '../components/InvoiceDetailModal';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function KpiCard({ label, value, sub, accent = 'slate' }) {
  const colors = {
    slate: 'bg-slate-50 border-slate-200 text-slate-700',
    red: 'bg-red-50 border-red-200 text-red-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
  };
  return (
    <Card className={`border ${colors[accent]}`}>
      <CardContent className="p-4">
        <p className="text-xs font-medium text-current opacity-70 mb-1">{label}</p>
        <p className="text-2xl font-bold font-mono">{value}</p>
        {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function PrintButton({ onClick }) {
  return (
    <Button variant="outline" size="sm" onClick={onClick} data-testid="report-print-btn">
      <Printer size={14} className="mr-1.5" /> Print
    </Button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  AR AGING TAB
// ─────────────────────────────────────────────────────────────────────────────
function ArAgingReport({ branches, selectedBranchId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [branchFilter, setBranchFilter] = useState(selectedBranchId || 'all');
  const [expandedRows, setExpandedRows] = useState({});
  const { canViewAllBranches } = useAuth();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (branchFilter && branchFilter !== 'all') params.set('branch_id', branchFilter);
      const res = await api.get(`${BACKEND_URL}/api/reports/ar-aging?${params}`);
      setData(res.data);
    } catch (e) {
      toast.error('Failed to load AR aging data');
    } finally {
      setLoading(false);
    }
  }, [branchFilter]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = () => {
    const win = window.open('', '_blank');
    const totals = data?.totals || {};
    const rows = data?.rows || [];
    win.document.write(`
      <html><head><title>AR Aging Report</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 12px; padding: 20px; }
        h2 { color: #1A4D2E; margin-bottom: 4px; }
        .sub { color: #666; margin-bottom: 16px; font-size: 11px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th { background: #1A4D2E; color: white; padding: 6px 10px; text-align: left; font-size: 11px; }
        td { padding: 5px 10px; border-bottom: 1px solid #e5e7eb; font-size: 11px; }
        tr:nth-child(even) td { background: #f9fafb; }
        .num { text-align: right; font-family: monospace; }
        .total-row td { font-weight: bold; background: #f1f5f9; border-top: 2px solid #94a3b8; }
        .badge-current { color: #15803d; } .badge-31 { color: #b45309; } .badge-61 { color: #c2410c; } .badge-90 { color: #b91c1c; }
      </style></head><body>
      <h2>AgriBooks — AR Aging Report</h2>
      <div class="sub">As of ${data?.as_of_date || ''}</div>
      <table>
        <thead><tr>
          <th>Customer</th>
          <th class="num">Current (0–30d)</th>
          <th class="num">31–60 days</th>
          <th class="num">61–90 days</th>
          <th class="num">90+ days</th>
          <th class="num">Total</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `<tr>
            <td>${r.customer_name}</td>
            <td class="num">${r.current > 0 ? '₱' + r.current.toLocaleString('en-PH', {minimumFractionDigits:2}) : '—'}</td>
            <td class="num">${r.b31_60 > 0 ? '₱' + r.b31_60.toLocaleString('en-PH', {minimumFractionDigits:2}) : '—'}</td>
            <td class="num">${r.b61_90 > 0 ? '₱' + r.b61_90.toLocaleString('en-PH', {minimumFractionDigits:2}) : '—'}</td>
            <td class="num">${r.b90plus > 0 ? '₱' + r.b90plus.toLocaleString('en-PH', {minimumFractionDigits:2}) : '—'}</td>
            <td class="num">₱${r.total.toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
          </tr>`).join('')}
          <tr class="total-row">
            <td>TOTAL</td>
            <td class="num">₱${(totals.current||0).toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
            <td class="num">₱${(totals.b31_60||0).toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
            <td class="num">₱${(totals.b61_90||0).toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
            <td class="num">₱${(totals.b90plus||0).toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
            <td class="num">₱${(totals.total||0).toLocaleString('en-PH', {minimumFractionDigits:2})}</td>
          </tr>
        </tbody>
      </table>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  const toggleRow = (cid) => setExpandedRows(p => ({ ...p, [cid]: !p[cid] }));

  const bucketLabel = {
    current: { label: '0–30 days', color: 'text-emerald-600' },
    b31_60: { label: '31–60 days', color: 'text-amber-600' },
    b61_90: { label: '61–90 days', color: 'text-orange-600' },
    b90plus: { label: '90+ days', color: 'text-red-600' },
  };

  const totals = data?.totals || {};

  return (
    <div className="space-y-4" data-testid="ar-aging-tab">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {canViewAllBranches && (
          <Select value={branchFilter} onValueChange={setBranchFilter}>
            <SelectTrigger className="w-44 h-8 text-xs" data-testid="ar-branch-filter">
              <SelectValue placeholder="All Branches" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Branches</SelectItem>
              {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <Button size="sm" variant="outline" onClick={load} disabled={loading} data-testid="ar-refresh-btn">
          <RefreshCw size={13} className={`mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
        <div className="ml-auto">
          <PrintButton onClick={handlePrint} />
        </div>
      </div>

      {/* KPI Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Current (0–30d)" value={formatPHP(totals.current || 0)} accent="emerald" />
        <KpiCard label="31–60 days" value={formatPHP(totals.b31_60 || 0)} accent="amber" />
        <KpiCard label="61–90 days" value={formatPHP(totals.b61_90 || 0)} accent="amber" />
        <KpiCard label="90+ days (Critical)" value={formatPHP(totals.b90plus || 0)} accent="red" />
      </div>
      <KpiCard label="Total Outstanding AR" value={formatPHP(totals.total || 0)} accent="blue"
        sub={`As of ${data?.as_of_date || '—'} · ${data?.rows?.length || 0} customers`} />

      {/* Table */}
      <Card>
        <CardHeader className="py-3 px-4 bg-slate-50 border-b">
          <CardTitle className="text-sm font-semibold text-slate-700">Customer Aging Detail</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table data-testid="ar-aging-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="w-8"></TableHead>
                <TableHead>Customer</TableHead>
                <TableHead className="text-right text-emerald-700">0–30d</TableHead>
                <TableHead className="text-right text-amber-700">31–60d</TableHead>
                <TableHead className="text-right text-orange-700">61–90d</TableHead>
                <TableHead className="text-right text-red-700">90+d</TableHead>
                <TableHead className="text-right font-bold">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.rows || []).map(row => (
                <>
                  <TableRow
                    key={row.customer_id}
                    className="cursor-pointer hover:bg-slate-50"
                    onClick={() => toggleRow(row.customer_id)}
                  >
                    <TableCell className="w-8 text-slate-400">
                      {expandedRows[row.customer_id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </TableCell>
                    <TableCell className="font-medium">{row.customer_name}</TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {row.current > 0 ? <span className="text-emerald-600">{formatPHP(row.current)}</span> : <span className="text-slate-300">—</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {row.b31_60 > 0 ? <span className="text-amber-600">{formatPHP(row.b31_60)}</span> : <span className="text-slate-300">—</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {row.b61_90 > 0 ? <span className="text-orange-600">{formatPHP(row.b61_90)}</span> : <span className="text-slate-300">—</span>}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {row.b90plus > 0 ? <span className="text-red-600 font-semibold">{formatPHP(row.b90plus)}</span> : <span className="text-slate-300">—</span>}
                    </TableCell>
                    <TableCell className="text-right font-bold font-mono">{formatPHP(row.total)}</TableCell>
                  </TableRow>
                  {expandedRows[row.customer_id] && (row.invoices || []).map(inv => (
                    <TableRow key={inv.invoice_number} className="bg-slate-50/50 text-xs">
                      <TableCell />
                      <TableCell className="pl-8 text-slate-500">
                        {inv.invoice_number}
                        <span className="ml-2 text-slate-400">{inv.invoice_date}</span>
                        <span className={`ml-2 font-medium ${bucketLabel[inv.bucket]?.color}`}>
                          {inv.days_old}d old
                        </span>
                      </TableCell>
                      <TableCell colSpan={4} className="text-slate-500">
                        Grand: {formatPHP(inv.grand_total)} · Paid: {formatPHP(inv.amount_paid)} · Due: {inv.due_date}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium text-slate-700">{formatPHP(inv.balance)}</TableCell>
                    </TableRow>
                  ))}
                </>
              ))}
              {/* Totals row */}
              {data?.rows?.length > 0 && (
                <TableRow className="bg-slate-100 font-bold border-t-2 border-slate-300">
                  <TableCell />
                  <TableCell>TOTAL</TableCell>
                  <TableCell className="text-right font-mono text-emerald-700">{formatPHP(totals.current || 0)}</TableCell>
                  <TableCell className="text-right font-mono text-amber-700">{formatPHP(totals.b31_60 || 0)}</TableCell>
                  <TableCell className="text-right font-mono text-orange-700">{formatPHP(totals.b61_90 || 0)}</TableCell>
                  <TableCell className="text-right font-mono text-red-700">{formatPHP(totals.b90plus || 0)}</TableCell>
                  <TableCell className="text-right font-mono">{formatPHP(totals.total || 0)}</TableCell>
                </TableRow>
              )}
              {!loading && data?.rows?.length === 0 && (
                <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-10">No outstanding receivables found.</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  SALES REPORT TAB
// ─────────────────────────────────────────────────────────────────────────────
function SalesReport({ branches, selectedBranchId }) {
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const todayStr = today.toISOString().slice(0, 10);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dateFrom, setDateFrom] = useState(firstOfMonth);
  const [dateTo, setDateTo] = useState(todayStr);
  const [branchFilter, setBranchFilter] = useState(selectedBranchId || 'all');
  const [view, setView] = useState('summary'); // summary | transactions
  const { canViewAllBranches } = useAuth();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
      if (branchFilter && branchFilter !== 'all') params.set('branch_id', branchFilter);
      const res = await api.get(`${BACKEND_URL}/api/reports/sales?${params}`);
      setData(res.data);
    } catch (e) {
      toast.error('Failed to load sales data');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, branchFilter]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = () => {
    const win = window.open('', '_blank');
    const cats = data?.categories || [];
    win.document.write(`
      <html><head><title>Sales Report</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 12px; padding: 20px; }
        h2 { color: #1A4D2E; margin-bottom: 4px; }
        .sub { color: #666; margin-bottom: 16px; font-size: 11px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th { background: #1A4D2E; color: white; padding: 6px 10px; text-align: left; font-size: 11px; }
        td { padding: 5px 10px; border-bottom: 1px solid #e5e7eb; font-size: 11px; }
        tr:nth-child(even) td { background: #f9fafb; }
        .num { text-align: right; font-family: monospace; }
        .total-row td { font-weight: bold; background: #f1f5f9; border-top: 2px solid #94a3b8; }
      </style></head><body>
      <h2>AgriBooks — Sales Report</h2>
      <div class="sub">Period: ${data?.date_from || ''} to ${data?.date_to || ''} &nbsp;|&nbsp; Total: ₱${(data?.grand_total||0).toLocaleString('en-PH',{minimumFractionDigits:2})}</div>
      <h3 style="font-size:12px;margin-bottom:6px;">Sales by Category</h3>
      <table>
        <thead><tr><th>Category</th><th class="num">Qty</th><th class="num">Amount</th><th class="num">% of Total</th></tr></thead>
        <tbody>
          ${cats.map(c => `<tr>
            <td>${c.category}</td>
            <td class="num">${c.qty}</td>
            <td class="num">₱${c.total.toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
            <td class="num">${data?.grand_total > 0 ? ((c.total/data.grand_total)*100).toFixed(1)+'%' : '—'}</td>
          </tr>`).join('')}
          <tr class="total-row">
            <td>TOTAL</td>
            <td class="num">${cats.reduce((s,c)=>s+c.qty,0)}</td>
            <td class="num">₱${(data?.grand_total||0).toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
            <td class="num">100%</td>
          </tr>
        </tbody>
      </table>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  const paymentTotals = data?.payment_totals || {};
  const cashTotal = paymentTotals['cash'] || 0;
  const creditTotal = paymentTotals['credit'] || 0;

  return (
    <div className="space-y-4" data-testid="sales-report-tab">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-slate-400" />
          <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="h-8 text-xs w-36" data-testid="sales-date-from" />
          <span className="text-slate-400 text-xs">to</span>
          <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="h-8 text-xs w-36" data-testid="sales-date-to" />
        </div>
        {canViewAllBranches && (
          <Select value={branchFilter} onValueChange={setBranchFilter}>
            <SelectTrigger className="w-40 h-8 text-xs" data-testid="sales-branch-filter">
              <SelectValue placeholder="All Branches" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Branches</SelectItem>
              {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <Button size="sm" onClick={load} disabled={loading} className="bg-[#1A4D2E] hover:bg-[#15402A] text-white" data-testid="sales-run-btn">
          <Filter size={13} className="mr-1.5" /> Run Report
        </Button>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw size={13} className={`mr-1.5 ${loading ? 'animate-spin' : ''}`} />
        </Button>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant={view === 'summary' ? 'default' : 'outline'} onClick={() => setView('summary')} data-testid="sales-summary-view">Summary</Button>
          <Button size="sm" variant={view === 'transactions' ? 'default' : 'outline'} onClick={() => setView('transactions')} data-testid="sales-transactions-view">Transactions</Button>
          <PrintButton onClick={handlePrint} />
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Total Sales" value={formatPHP(data?.grand_total || 0)} accent="emerald"
          sub={`${data?.date_from} → ${data?.date_to}`} />
        <KpiCard label="Walk-in (Cash)" value={formatPHP(cashTotal)} accent="blue" />
        <KpiCard label="Credit Sales" value={formatPHP(creditTotal)} accent="amber" />
        <KpiCard label="Categories Sold" value={data?.categories?.length || 0} accent="slate"
          sub={`${data?.transactions?.length || 0} transactions`} />
      </div>

      {view === 'summary' && (
        <>
          {/* Category Breakdown */}
          <Card>
            <CardHeader className="py-3 px-4 bg-slate-50 border-b">
              <CardTitle className="text-sm font-semibold text-slate-700">Sales by Category</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table data-testid="sales-category-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">% of Total</TableHead>
                    <TableHead className="text-right">Cash</TableHead>
                    <TableHead className="text-right">Credit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data?.categories || []).map(cat => (
                    <TableRow key={cat.category}>
                      <TableCell className="font-medium">{cat.category}</TableCell>
                      <TableCell className="text-right font-mono text-sm">{cat.qty}</TableCell>
                      <TableCell className="text-right font-mono text-sm font-semibold">{formatPHP(cat.total)}</TableCell>
                      <TableCell className="text-right text-sm text-slate-500">
                        {data?.grand_total > 0 ? ((cat.total / data.grand_total) * 100).toFixed(1) + '%' : '—'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm text-emerald-600">
                        {cat.by_payment?.cash ? formatPHP(cat.by_payment.cash) : '—'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm text-amber-600">
                        {cat.by_payment?.credit ? formatPHP(cat.by_payment.credit) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {(data?.categories?.length || 0) > 0 && (
                    <TableRow className="bg-slate-100 font-bold border-t-2 border-slate-300">
                      <TableCell>TOTAL</TableCell>
                      <TableCell className="text-right font-mono">{(data?.categories || []).reduce((s, c) => s + c.qty, 0)}</TableCell>
                      <TableCell className="text-right font-mono">{formatPHP(data?.grand_total || 0)}</TableCell>
                      <TableCell className="text-right">100%</TableCell>
                      <TableCell className="text-right font-mono text-emerald-700">{formatPHP(cashTotal)}</TableCell>
                      <TableCell className="text-right font-mono text-amber-700">{formatPHP(creditTotal)}</TableCell>
                    </TableRow>
                  )}
                  {!loading && (data?.categories?.length || 0) === 0 && (
                    <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-10">No sales data found for the selected period.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Daily Breakdown */}
          {(data?.daily?.length || 0) > 0 && (
            <Card>
              <CardHeader className="py-3 px-4 bg-slate-50 border-b">
                <CardTitle className="text-sm font-semibold text-slate-700">Daily Sales</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Transactions</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(data?.daily || []).map(d => (
                      <TableRow key={d.date}>
                        <TableCell>{d.date}</TableCell>
                        <TableCell className="text-right text-sm">{d.count}</TableCell>
                        <TableCell className="text-right font-mono text-sm font-semibold">{formatPHP(d.total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {view === 'transactions' && (
        <Card>
          <CardHeader className="py-3 px-4 bg-slate-50 border-b">
            <CardTitle className="text-sm font-semibold text-slate-700">
              Transactions ({data?.transactions?.length || 0})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table data-testid="sales-transactions-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Cashier</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">Paid</TableHead>
                  <TableHead className="text-right">Balance</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.transactions || []).map(t => (
                  <TableRow key={t.invoice_number}>
                    <TableCell className="font-mono text-xs">{t.invoice_number}</TableCell>
                    <TableCell className="text-sm">{t.date}</TableCell>
                    <TableCell className="text-sm">{t.customer_name}</TableCell>
                    <TableCell className="text-sm text-slate-500">{t.cashier_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={t.payment_type === 'cash' ? 'border-emerald-200 text-emerald-700' : 'border-amber-200 text-amber-700'}>
                        {t.payment_type === 'cash' ? 'Walk-in' : t.payment_type === 'credit' ? 'Credit' : 'Partial'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">{formatPHP(t.grand_total)}</TableCell>
                    <TableCell className="text-right font-mono text-sm">{formatPHP(t.amount_paid)}</TableCell>
                    <TableCell className="text-right font-mono text-sm text-red-600">{t.balance > 0 ? formatPHP(t.balance) : '—'}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={
                        t.status === 'paid' ? 'border-emerald-200 text-emerald-700' :
                        t.status === 'partial' ? 'border-blue-200 text-blue-700' :
                        'border-amber-200 text-amber-700'
                      }>{t.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && (data?.transactions?.length || 0) === 0 && (
                  <TableRow><TableCell colSpan={9} className="text-center text-slate-400 py-10">No transactions found.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  EXPENSE REPORT TAB
// ─────────────────────────────────────────────────────────────────────────────
function ExpenseReport({ branches, selectedBranchId }) {
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const todayStr = today.toISOString().slice(0, 10);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dateFrom, setDateFrom] = useState(firstOfMonth);
  const [dateTo, setDateTo] = useState(todayStr);
  const [branchFilter, setBranchFilter] = useState(selectedBranchId || 'all');
  const [catFilter, setCatFilter] = useState('all');
  const [view, setView] = useState('summary');
  const { canViewAllBranches } = useAuth();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
      if (branchFilter && branchFilter !== 'all') params.set('branch_id', branchFilter);
      if (catFilter && catFilter !== 'all') params.set('category', catFilter);
      const res = await api.get(`${BACKEND_URL}/api/reports/expenses?${params}`);
      setData(res.data);
    } catch (e) {
      toast.error('Failed to load expense data');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, branchFilter, catFilter]);

  useEffect(() => { load(); }, [load]);

  const handlePrint = () => {
    const win = window.open('', '_blank');
    const cats = data?.categories || [];
    win.document.write(`
      <html><head><title>Expense Report</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 12px; padding: 20px; }
        h2 { color: #1A4D2E; margin-bottom: 4px; }
        .sub { color: #666; margin-bottom: 16px; font-size: 11px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th { background: #1A4D2E; color: white; padding: 6px 10px; text-align: left; font-size: 11px; }
        td { padding: 5px 10px; border-bottom: 1px solid #e5e7eb; font-size: 11px; }
        tr:nth-child(even) td { background: #f9fafb; }
        .num { text-align: right; font-family: monospace; }
        .total-row td { font-weight: bold; background: #f1f5f9; border-top: 2px solid #94a3b8; }
      </style></head><body>
      <h2>AgriBooks — Expense Report</h2>
      <div class="sub">Period: ${data?.date_from||''} to ${data?.date_to||''} &nbsp;|&nbsp; Total: ₱${(data?.grand_total||0).toLocaleString('en-PH',{minimumFractionDigits:2})}</div>
      <h3 style="font-size:12px;margin-bottom:6px;">Expenses by Category</h3>
      <table>
        <thead><tr><th>Category</th><th class="num">Count</th><th class="num">Amount</th><th class="num">% of Total</th></tr></thead>
        <tbody>
          ${cats.map(c => `<tr>
            <td>${c.category}</td>
            <td class="num">${c.count}</td>
            <td class="num">₱${c.total.toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
            <td class="num">${data?.grand_total > 0 ? ((c.total/data.grand_total)*100).toFixed(1)+'%' : '—'}</td>
          </tr>`).join('')}
          <tr class="total-row">
            <td>TOTAL</td>
            <td class="num">${cats.reduce((s,c)=>s+c.count,0)}</td>
            <td class="num">₱${(data?.grand_total||0).toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
            <td class="num">100%</td>
          </tr>
        </tbody>
      </table>
      <h3 style="font-size:12px;margin-bottom:6px;">Transaction Detail</h3>
      <table>
        <thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Recorded By</th><th class="num">Amount</th></tr></thead>
        <tbody>
          ${(data?.expenses||[]).map(e => `<tr>
            <td>${e.date}</td><td>${e.category}</td>
            <td>${e.description||'—'}</td>
            <td>${e.created_by_name||'—'}</td>
            <td class="num">₱${(e.amount||0).toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
          </tr>`).join('')}
        </tbody>
      </table>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  const topCat = data?.categories?.[0];

  return (
    <div className="space-y-4" data-testid="expense-report-tab">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-slate-400" />
          <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="h-8 text-xs w-36" data-testid="expense-date-from" />
          <span className="text-slate-400 text-xs">to</span>
          <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="h-8 text-xs w-36" data-testid="expense-date-to" />
        </div>
        {canViewAllBranches && (
          <Select value={branchFilter} onValueChange={setBranchFilter}>
            <SelectTrigger className="w-40 h-8 text-xs" data-testid="expense-branch-filter">
              <SelectValue placeholder="All Branches" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Branches</SelectItem>
              {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <Select value={catFilter} onValueChange={setCatFilter}>
          <SelectTrigger className="w-44 h-8 text-xs" data-testid="expense-cat-filter">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {(data?.categories || []).map(c => <SelectItem key={c.category} value={c.category}>{c.category}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" onClick={load} disabled={loading} className="bg-[#1A4D2E] hover:bg-[#15402A] text-white" data-testid="expense-run-btn">
          <Filter size={13} className="mr-1.5" /> Run Report
        </Button>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw size={13} className={`mr-1.5 ${loading ? 'animate-spin' : ''}`} />
        </Button>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant={view === 'summary' ? 'default' : 'outline'} onClick={() => setView('summary')} data-testid="expense-summary-view">Summary</Button>
          <Button size="sm" variant={view === 'detail' ? 'default' : 'outline'} onClick={() => setView('detail')} data-testid="expense-detail-view">Detail</Button>
          <PrintButton onClick={handlePrint} />
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Total Expenses" value={formatPHP(data?.grand_total || 0)} accent="red"
          sub={`${data?.date_from} → ${data?.date_to}`} />
        <KpiCard label="Transactions" value={data?.expenses?.length || 0} accent="slate" />
        <KpiCard label="Categories" value={data?.categories?.length || 0} accent="slate" />
        <KpiCard label="Largest Category"
          value={topCat ? topCat.category : '—'}
          sub={topCat ? formatPHP(topCat.total) : ''}
          accent="amber" />
      </div>

      {view === 'summary' && (
        <>
          {/* Category Breakdown */}
          <Card>
            <CardHeader className="py-3 px-4 bg-slate-50 border-b">
              <CardTitle className="text-sm font-semibold text-slate-700">Expenses by Category</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table data-testid="expense-category-table">
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Count</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">% of Total</TableHead>
                    <TableHead className="w-32">Share</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data?.categories || []).map(cat => {
                    const pct = data?.grand_total > 0 ? (cat.total / data.grand_total) * 100 : 0;
                    return (
                      <TableRow key={cat.category}>
                        <TableCell className="font-medium">{cat.category}</TableCell>
                        <TableCell className="text-right text-sm">{cat.count}</TableCell>
                        <TableCell className="text-right font-mono text-sm font-semibold">{formatPHP(cat.total)}</TableCell>
                        <TableCell className="text-right text-sm text-slate-500">{pct.toFixed(1)}%</TableCell>
                        <TableCell>
                          <div className="w-full bg-slate-100 rounded-full h-1.5">
                            <div className="bg-[#1A4D2E] h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {(data?.categories?.length || 0) > 0 && (
                    <TableRow className="bg-slate-100 font-bold border-t-2 border-slate-300">
                      <TableCell>TOTAL</TableCell>
                      <TableCell className="text-right font-mono">{(data?.expenses || []).length}</TableCell>
                      <TableCell className="text-right font-mono">{formatPHP(data?.grand_total || 0)}</TableCell>
                      <TableCell className="text-right">100%</TableCell>
                      <TableCell />
                    </TableRow>
                  )}
                  {!loading && (data?.categories?.length || 0) === 0 && (
                    <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-10">No expenses found for the selected period.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Daily Breakdown */}
          {(data?.daily?.length || 0) > 0 && (
            <Card>
              <CardHeader className="py-3 px-4 bg-slate-50 border-b">
                <CardTitle className="text-sm font-semibold text-slate-700">Daily Expenses</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(data?.daily || []).map(d => (
                      <TableRow key={d.date}>
                        <TableCell>{d.date}</TableCell>
                        <TableCell className="text-right text-sm">{d.count}</TableCell>
                        <TableCell className="text-right font-mono text-sm font-semibold">{formatPHP(d.total)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {view === 'detail' && (
        <Card>
          <CardHeader className="py-3 px-4 bg-slate-50 border-b">
            <CardTitle className="text-sm font-semibold text-slate-700">
              Expense Transactions ({data?.expenses?.length || 0})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table data-testid="expense-detail-table">
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead>Date</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Employee</TableHead>
                  <TableHead>Recorded By</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(data?.expenses || []).map((exp, i) => (
                  <TableRow key={exp.id || i}>
                    <TableCell className="text-sm">{exp.date}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">{exp.category}</Badge>
                    </TableCell>
                    <TableCell className="text-sm max-w-xs truncate">{exp.description || '—'}</TableCell>
                    <TableCell className="text-sm text-slate-500">{exp.employee_name || '—'}</TableCell>
                    <TableCell className="text-sm text-slate-500">{exp.created_by_name || '—'}</TableCell>
                    <TableCell className="text-right font-mono text-sm font-semibold">{formatPHP(exp.amount)}</TableCell>
                  </TableRow>
                ))}
                {!loading && (data?.expenses?.length || 0) === 0 && (
                  <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-10">No expenses found.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function ReportsPage() {
  const { branches, selectedBranchId } = useAuth();

  return (
    <div className="p-6 space-y-5 max-w-7xl mx-auto">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-[#1A4D2E] flex items-center justify-center">
          <BarChart3 size={20} className="text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-800" style={{ fontFamily: 'Manrope' }}>Reports</h1>
          <p className="text-xs text-slate-500">AR Aging · Sales · Expenses</p>
        </div>
      </div>

      <Tabs defaultValue="ar-aging" className="space-y-4">
        <TabsList className="bg-slate-100">
          <TabsTrigger value="ar-aging" data-testid="tab-ar-aging" className="text-sm">
            <AlertCircle size={14} className="mr-1.5" /> AR Aging
          </TabsTrigger>
          <TabsTrigger value="sales" data-testid="tab-sales" className="text-sm">
            <TrendingUp size={14} className="mr-1.5" /> Sales Report
          </TabsTrigger>
          <TabsTrigger value="expenses" data-testid="tab-expenses" className="text-sm">
            <DollarSign size={14} className="mr-1.5" /> Expense Report
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ar-aging">
          <ArAgingReport branches={branches || []} selectedBranchId={selectedBranchId} />
        </TabsContent>

        <TabsContent value="sales">
          <SalesReport branches={branches || []} selectedBranchId={selectedBranchId} />
        </TabsContent>

        <TabsContent value="expenses">
          <ExpenseReport branches={branches || []} selectedBranchId={selectedBranchId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
