import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import {
  DollarSign, ShoppingCart, Package, Users, AlertTriangle,
  TrendingUp, ArrowDown, Building2, Wallet, Receipt, ArrowRight,
  Truck, Clock, CreditCard, Banknote, CheckCircle2, Calendar,
  BarChart3, RefreshCw, ArrowUpRight, ArrowDownRight, Lock
} from 'lucide-react';import { formatPHP } from '../lib/utils';

function KpiCard({ label, value, sub, icon: Icon, color, trend, testId }) {
  return (
    <Card className="border-slate-200 hover:shadow-sm transition-shadow" data-testid={testId}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-slate-500 font-medium">{label}</span>
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${color.bg}`}>
            <Icon size={14} className={color.text} strokeWidth={1.8} />
          </div>
        </div>
        <p className={`text-xl font-bold tracking-tight ${color.text}`} style={{ fontFamily: 'Manrope' }}>{value}</p>
        {sub && <p className="text-[11px] text-slate-400 mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function AgingBar({ aging }) {
  const total = aging?.total || 1;
  const pct = (n) => Math.round((n / total) * 100);
  return (
    <div className="space-y-2 text-xs">
      {[
        { label: '0–30 days', val: aging?.current || 0, color: 'bg-emerald-400', text: 'text-emerald-700' },
        { label: '31–60 days', val: aging?.days_31_60 || 0, color: 'bg-amber-400', text: 'text-amber-700' },
        { label: '61–90 days', val: aging?.days_61_90 || 0, color: 'bg-orange-400', text: 'text-orange-700' },
        { label: '90+ days', val: aging?.over_90 || 0, color: 'bg-red-500', text: 'text-red-700' },
      ].map(({ label, val, color, text }) => (
        <div key={label}>
          <div className="flex justify-between mb-0.5">
            <span className="text-slate-500">{label}</span>
            <span className={`font-semibold font-mono ${text}`}>{formatPHP(val)}</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct(val)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// Owner's branch card
function BranchCard({ branch, onSelect }) {
  const today = new Date().toISOString().slice(0, 10);
  const lastClose = branch.last_close_date;
  const daysSinceClose = lastClose
    ? Math.floor((new Date(today) - new Date(lastClose)) / 86400000) : null;
  const statusDot = branch.status === 'good' ? 'bg-emerald-400' : branch.status === 'warning' ? 'bg-amber-400' : 'bg-red-500';

  return (
    <Card className="border-slate-200 hover:border-[#1A4D2E]/40 transition-all cursor-pointer hover:shadow-md group" onClick={() => onSelect(branch.id)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${statusDot}`} />
            <h3 className="font-semibold text-sm">{branch.name}</h3>
          </div>
          <ArrowRight size={13} className="text-slate-300 group-hover:text-[#1A4D2E] transition-colors" />
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <div>
            <p className="text-slate-400">Walk-in Sales Today</p>
            <p className="font-bold text-emerald-700">{formatPHP(branch.today_cash_sales || 0)}</p>
          </div>
          <div>
            <p className="text-slate-400">New Credit</p>
            <p className="font-bold text-amber-700">{formatPHP(branch.today_new_credit || 0)}</p>
          </div>
          <div>
            <p className="text-slate-400">Cashier + Safe</p>
            <p className="font-bold text-blue-700">{formatPHP(branch.total_cash || 0)}</p>
          </div>
          <div>
            <p className="text-slate-400">AR Outstanding</p>
            <p className={`font-bold ${branch.receivables > 0 ? 'text-amber-600' : 'text-slate-400'}`}>{formatPHP(branch.receivables || 0)}</p>
          </div>
        </div>
        <Separator className="my-2" />
        {branch.inventory_value && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] py-1">
            <div>
              <span className="text-slate-400">Stock @ Capital</span>
              <p className="font-semibold text-slate-700 font-mono">{formatPHP(branch.inventory_value.capital_value)}</p>
            </div>
            <div>
              <span className="text-slate-400">Stock @ Retail</span>
              <p className="font-semibold text-emerald-700 font-mono">{formatPHP(branch.inventory_value.retail_value)}</p>
            </div>
          </div>
        )}
        <Separator className="my-2" />
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span className="flex items-center gap-1">
            <Lock size={9} />
            {lastClose
              ? daysSinceClose === 0 ? 'Closed today' : `Last close: ${lastClose}`
              : 'Never closed'}
          </span>
          {branch.low_stock_count > 0 && (
            <span className="flex items-center gap-1 text-amber-600">
              <AlertTriangle size={9} /> {branch.low_stock_count} low stock
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { isConsolidatedView, switchBranch, selectedBranchId, currentBranch } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [branchSummary, setBranchSummary] = useState(null);
  const [poSummary, setPoSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (silent = false) => {
    if (!silent) setLoading(true); else setRefreshing(true);
    try {
      if (isConsolidatedView) {
        const [summaryRes, statsRes, poRes] = await Promise.all([
          api.get('/dashboard/branch-summary'),
          api.get('/dashboard/stats'),
          api.get('/purchase-orders/unpaid-summary').catch(() => ({ data: null })),
        ]);
        setBranchSummary(summaryRes.data);
        setStats(statsRes.data);
        setPoSummary(poRes.data);
      } else {
        const [res, poRes] = await Promise.all([
          api.get('/dashboard/stats', { params: selectedBranchId !== 'all' ? { branch_id: selectedBranchId } : {} }),
          api.get('/purchase-orders/unpaid-summary').catch(() => ({ data: null })),
        ]);
        setStats(res.data);
        setPoSummary(poRes.data);
        setBranchSummary(null);
      }
    } catch (err) { console.error('Dashboard load error', err); }
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => { loadData(); }, [isConsolidatedView, selectedBranchId]); // eslint-disable-line

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <RefreshCw size={20} className="animate-spin mr-2" /> Loading dashboard...
    </div>
  );

  const today = stats?.today || new Date().toISOString().slice(0, 10);
  const dayOfWeek = stats?.day_of_week || '';
  const lastClose = stats?.last_close_date;
  const daysSinceClose = stats?.days_since_close;

  // ─── OWNER CONSOLIDATED VIEW ───────────────────────────────────────────────
  if (isConsolidatedView && branchSummary) {
    const totals = branchSummary.totals || {};
    const branches = branchSummary.branches || [];

    return (
      <div className="space-y-6 animate-fadeIn" data-testid="owner-dashboard">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Building2 size={20} className="text-[#1A4D2E]" />
              <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Owner Dashboard</h1>
            </div>
            <p className="text-sm text-slate-500 mt-0.5">
              {dayOfWeek}, {today} · {branches.length} branches
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadData(true)} disabled={refreshing}>
            <RefreshCw size={13} className={`mr-1.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>

        {/* Consolidated KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Sales Today', value: formatPHP(totals.today_revenue || 0), icon: DollarSign, color: { bg: 'bg-emerald-50', text: 'text-emerald-700' }, sub: `${branches.reduce((s, b) => s + (b.today_sales_count || 0), 0)} transactions` },
            { label: 'Total Cash Position', value: formatPHP(totals.total_cash || 0), icon: Wallet, color: { bg: 'bg-blue-50', text: 'text-blue-700' }, sub: 'Cashier + Safe (all branches)' },
            { label: 'Outstanding AR', value: formatPHP(totals.total_receivables || 0), icon: Receipt, color: { bg: 'bg-amber-50', text: 'text-amber-700' }, sub: 'Total unpaid credit' },
            { label: 'Low Stock Alerts', value: totals.low_stock_count || 0, icon: AlertTriangle, color: { bg: 'bg-red-50', text: (totals.low_stock_count || 0) > 0 ? 'text-red-600' : 'text-slate-400' }, sub: 'Products below threshold' },
          ].map(kpi => (
            <KpiCard key={kpi.label} {...kpi} testId={`kpi-${kpi.label.replace(/\s+/g, '-').toLowerCase()}`} />
          ))}
        </div>

        {/* Branch Cards */}
        <div>
          <h2 className="text-base font-semibold mb-3 flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <BarChart3 size={16} className="text-[#1A4D2E]" /> Branch Performance Today
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {branches.map(branch => (
              <BranchCard key={branch.id} branch={branch} onSelect={switchBranch} />
            ))}
          </div>
        </div>

        {/* Bottom row */}
        <div className="grid lg:grid-cols-3 gap-5">
          {/* Top branches by sales */}
          <Card className="border-slate-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <TrendingUp size={14} className="text-emerald-600" /> Top Revenue Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              {[...branches].sort((a, b) => (b.today_revenue || 0) - (a.today_revenue || 0)).map((b, i) => (
                <div key={b.id} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${i === 0 ? 'bg-emerald-100 text-emerald-700' : i === 1 ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>{i + 1}</span>
                    <span>{b.name}</span>
                  </div>
                  <span className="font-semibold text-emerald-700 font-mono">{formatPHP(b.today_revenue || 0)}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* AR alerts */}
          <Card className="border-slate-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-500" /> Alerts
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {branches.filter(b => b.low_stock_count > 0).map(b => (
                <div key={b.id} className="flex items-center justify-between p-2 rounded bg-amber-50 text-xs">
                  <span className="font-medium">{b.name}</span>
                  <Badge className="bg-amber-100 text-amber-700 text-[10px]">{b.low_stock_count} low stock</Badge>
                </div>
              ))}
              {branches.filter(b => daysSinceClose !== null && daysSinceClose > 1).map(b => (
                b.last_close_date && new Date(today) - new Date(b.last_close_date) > 86400000 ? (
                  <div key={`close-${b.id}`} className="flex items-center justify-between p-2 rounded bg-red-50 text-xs">
                    <span className="font-medium">{b.name}</span>
                    <Badge className="bg-red-100 text-red-700 text-[10px]">Unclosed day</Badge>
                  </div>
                ) : null
              ))}
              {!branches.some(b => b.low_stock_count > 0) && <p className="text-xs text-slate-400">No alerts</p>}
            </CardContent>
          </Card>

          {/* Unpaid POs */}
          <Card className="border-slate-200">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Truck size={14} className="text-red-600" /> Supplier Payables
                </CardTitle>
                {poSummary?.total_unpaid > 0 && <span className="text-xs font-bold text-red-600">{formatPHP(poSummary.total_unpaid)}</span>}
              </div>
            </CardHeader>
            <CardContent>
              {!poSummary || poSummary.total_count === 0 ? (
                <p className="text-xs text-slate-400">All POs paid</p>
              ) : (
                <div className="space-y-1">
                  {[...(poSummary.overdue || []), ...(poSummary.due_soon || [])].slice(0, 5).map(po => (
                    <div key={po.id} className="flex justify-between text-xs bg-slate-50 rounded px-2 py-1.5">
                      <div>
                        <span className="font-mono text-blue-600 mr-2">{po.po_number}</span>
                        <span className="text-slate-500 truncate max-w-[80px]">{po.vendor}</span>
                      </div>
                      <div className="text-right">
                        {po.due_date && <p className={`${po.due_date < today ? 'text-red-500 font-semibold' : 'text-amber-500'}`}>{po.due_date}</p>}
                        <p className="font-bold text-red-600">{formatPHP(po.balance)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // ─── BRANCH / SINGLE VIEW ──────────────────────────────────────────────────
  const ar = stats?.ar_aging || {};
  const todayNetCash = stats?.today_net_cash || 0;

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-2">
            <Calendar size={13} />
            {dayOfWeek}, {today}
            {lastClose && (
              <span className={`flex items-center gap-1 ${daysSinceClose > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                <Lock size={11} />
                {daysSinceClose === 0 ? 'Closed today' : `Last close: ${lastClose} (${daysSinceClose}d ago)`}
              </span>
            )}
            {!lastClose && <span className="text-red-500 flex items-center gap-1"><Lock size={11} /> Never closed</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => loadData(true)} disabled={refreshing}>
            <RefreshCw size={13} className={`mr-1.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button size="sm" onClick={() => navigate('/close-wizard')} className="bg-[#1A4D2E] text-white">
            <Lock size={13} className="mr-1.5" /> Close Wizard
          </Button>
        </div>
      </div>

      {/* Row 1: Today's performance */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Walk-in Sales', value: formatPHP(stats?.today_cash_sales), icon: DollarSign, color: { bg: 'bg-emerald-50', text: 'text-emerald-700' }, sub: 'Paid today', testId: 'kpi-cash-sales' },
          { label: 'New Credit', value: formatPHP(stats?.today_credit_sales), icon: CreditCard, color: { bg: 'bg-amber-50', text: 'text-amber-700' }, sub: 'AR created today', testId: 'kpi-new-credit' },
          { label: 'AR Collected', value: formatPHP(stats?.today_ar_collected), icon: Banknote, color: { bg: 'bg-blue-50', text: 'text-blue-700' }, sub: 'Payments received', testId: 'kpi-ar-collected' },
          { label: 'Expenses', value: formatPHP(stats?.today_expenses), icon: ArrowDown, color: { bg: 'bg-red-50', text: 'text-red-600' }, sub: 'Paid out today', testId: 'kpi-expenses' },
          { label: 'Net Cash Flow', value: (todayNetCash >= 0 ? '+' : '') + formatPHP(todayNetCash), icon: todayNetCash >= 0 ? TrendingUp : ArrowDownRight, color: { bg: todayNetCash >= 0 ? 'bg-emerald-50' : 'bg-red-50', text: todayNetCash >= 0 ? 'text-emerald-700' : 'text-red-600' }, sub: 'Cash in - out', testId: 'kpi-net-cash' },
          { label: 'Transactions', value: stats?.today_sales_count || 0, icon: ShoppingCart, color: { bg: 'bg-slate-50', text: 'text-slate-700' }, sub: 'Today', testId: 'kpi-transactions' },
        ].map(kpi => <KpiCard key={kpi.label} {...kpi} />)}
      </div>

      {/* Row 2: Cash + AR */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Cash Position */}
        <Card className="border-slate-200" data-testid="cash-position-card">          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Wallet size={15} className="text-blue-600" /> Cash Position
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              { label: 'Operating Fund', value: stats?.cashier_balance || 0, color: 'text-blue-700', bg: 'bg-blue-50' },
              { label: 'Safe', value: stats?.safe_balance || 0, color: 'text-indigo-700', bg: 'bg-indigo-50' },
              { label: 'Total Cash', value: stats?.total_cash_position || 0, color: 'text-emerald-700', bg: 'bg-emerald-50', bold: true },
            ].map(({ label, value, color, bg, bold }) => (
              <div key={label} className={`flex justify-between items-center p-2 rounded-lg ${bg}`}>
                <span className="text-xs text-slate-600">{label}</span>
                <span className={`font-mono font-${bold ? 'bold' : 'semibold'} text-sm ${color}`}>{formatPHP(value)}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* AR Overview + Aging */}
        <Card className="border-slate-200 lg:col-span-2" data-testid="ar-overview-card">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Receipt size={15} className="text-amber-600" /> Accounts Receivable
              </CardTitle>
              <div className="text-right">
                <p className="text-xl font-bold text-amber-700 font-mono">{formatPHP(ar.total || 0)}</p>
                <p className="text-[10px] text-slate-400">Total outstanding</p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <AgingBar aging={ar} />
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Top Debtors</p>
                {(stats?.top_debtors || []).length === 0
                  ? <p className="text-xs text-slate-400">No outstanding AR</p>
                  : (stats?.top_debtors || []).map((d, i) => (
                    <div key={i} className="flex justify-between text-xs py-1.5 border-b border-slate-50 last:border-0">
                      <span className="font-medium truncate max-w-[110px]">{d.customer}</span>
                      <span className="font-mono font-semibold text-amber-700">{formatPHP(d.balance)}</span>
                    </div>
                  ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 2b: Inventory Value */}
      {stats?.inventory_value && (
        <Card className="border-slate-200" data-testid="inventory-value-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Package size={15} className="text-slate-600" /> Inventory Value — {currentBranch?.name || 'Branch'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <p className="text-xs text-slate-500 mb-0.5">At Capital (Cost)</p>
                <p className="text-xl font-bold font-mono text-slate-800" data-testid="inv-capital-value">
                  {formatPHP(stats.inventory_value.capital_value)}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">{stats.inventory_value.sku_count_in_stock} SKUs in stock</p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <p className="text-xs text-emerald-600 mb-0.5">At Retail Price</p>
                <p className="text-xl font-bold font-mono text-emerald-700" data-testid="inv-retail-value">
                  {formatPHP(stats.inventory_value.retail_value)}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">If sold at retail</p>
              </div>
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                <p className="text-xs text-blue-600 mb-0.5">Potential Gross Margin</p>
                <p className="text-xl font-bold font-mono text-blue-700" data-testid="inv-potential-margin">
                  {formatPHP(stats.inventory_value.potential_margin)}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">Retail − Capital</p>
              </div>
              <div className="p-3 rounded-lg bg-violet-50 border border-violet-200">
                <p className="text-xs text-violet-600 mb-0.5">Margin %</p>
                <p className="text-xl font-bold font-mono text-violet-700" data-testid="inv-margin-pct">
                  {stats.inventory_value.margin_pct}%
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">Avg markup on cost</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Row 3: Credits today + Recent payments */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Credit customers today */}
        <Card className="border-slate-200" data-testid="credit-today-card">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <CreditCard size={15} className="text-amber-600" /> Credit Extended Today
              </CardTitle>
              <span className="text-xs font-semibold text-amber-700">{formatPHP(stats?.today_credit_sales || 0)}</span>
            </div>
          </CardHeader>
          <CardContent>
            {(stats?.credit_customers_today || []).length === 0 ? (
              <p className="text-xs text-slate-400">No new credit today</p>
            ) : (
              <div className="space-y-1.5">
                {(stats?.credit_customers_today || []).map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-amber-50 rounded px-3 py-2">
                    <div>
                      <p className="font-semibold">{c.customer_name}</p>
                      <p className="text-slate-400 font-mono">{c.invoice_number}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-amber-700">{formatPHP(c.amount)}</p>
                      <p className="text-slate-400">bal {formatPHP(c.balance)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent AR payments */}
        <Card className="border-slate-200" data-testid="recent-payments-card">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Banknote size={15} className="text-blue-600" /> AR Payments Received Today
              </CardTitle>
              <span className="text-xs font-semibold text-blue-700">{formatPHP(stats?.today_ar_collected || 0)}</span>
            </div>
          </CardHeader>
          <CardContent>
            {(stats?.recent_ar_payments || []).length === 0 ? (
              <p className="text-xs text-slate-400">No AR payments today</p>
            ) : (
              <div className="space-y-1.5">
                {(stats?.recent_ar_payments || []).map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-blue-50 rounded px-3 py-2">
                    <div>
                      <p className="font-semibold">{p.customer_name}</p>
                      <p className="text-slate-400 font-mono">{p.invoice_number}</p>
                    </div>
                    <p className="font-bold text-blue-700">{formatPHP(p.amount)}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Row 4: Unpaid POs + Top Products + Recent Sales */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Unpaid POs */}
        <Card className="border-slate-200" data-testid="unpaid-po-card">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Truck size={14} className="text-red-600" /> Supplier Payables
              </CardTitle>
              {poSummary?.total_unpaid > 0 && <span className="text-xs font-bold text-red-600">{formatPHP(poSummary.total_unpaid)}</span>}
            </div>
          </CardHeader>
          <CardContent>
            {!poSummary || poSummary.total_count === 0 ? (
              <div className="flex items-center gap-2 text-xs text-emerald-600 py-2">
                <CheckCircle2 size={14} /> All POs paid up to date
              </div>
            ) : (
              <div className="space-y-1.5">
                {[
                  { items: poSummary.overdue || [], label: 'OVERDUE', cls: 'bg-red-100 text-red-700' },
                  { items: poSummary.due_soon || [], label: 'DUE SOON', cls: 'bg-amber-100 text-amber-700' },
                  { items: poSummary.later || [], label: 'UPCOMING', cls: 'bg-slate-100 text-slate-600' },
                ].filter(g => g.items.length > 0).map(group => (
                  <div key={group.label}>
                    <p className="text-[10px] font-bold tracking-wider text-slate-400 mb-1">{group.label} ({group.items.length})</p>
                    {group.items.slice(0, 2).map(po => (
                      <div key={po.id} className="flex justify-between text-xs bg-slate-50 rounded px-2 py-1.5 mb-1">
                        <div>
                          <span className="font-mono text-blue-600">{po.po_number} </span>
                          <span className="text-slate-500">{po.vendor?.slice(0, 15)}</span>
                          {po.due_date && <p className={`text-[10px] ${po.due_date < today ? 'text-red-500 font-semibold' : 'text-amber-500'}`}>
                            Due: {po.due_date}
                          </p>}
                        </div>
                        <span className="font-bold text-red-600">{formatPHP(po.balance)}</span>
                      </div>
                    ))}
                  </div>
                ))}
                <Button variant="ghost" size="sm" className="w-full text-xs text-slate-500 h-7" onClick={() => navigate('/pay-supplier')}>
                  View all payables <ArrowRight size={11} className="ml-1" />
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Products */}
        <Card className="border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp size={14} className="text-emerald-600" /> Top Products (All-time)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(stats?.top_products || []).length === 0
              ? <p className="text-xs text-slate-400">No sales data</p>
              : (stats?.top_products || []).map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded-full bg-slate-100 flex items-center justify-center text-[9px] font-bold text-slate-500">{i + 1}</span>
                    <span className="truncate max-w-[130px]">{p.name}</span>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-emerald-700">{formatPHP(p.revenue)}</p>
                    <p className="text-slate-400">{p.quantity} sold</p>
                  </div>
                </div>
              ))}
          </CardContent>
        </Card>

        {/* Recent Sales */}
        <Card className="border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            {(stats?.recent_sales || []).length === 0
              ? <p className="text-xs text-slate-400">No recent sales</p>
              : (stats?.recent_sales || []).slice(0, 5).map(sale => (
                <div key={sale.id} className="py-1.5 border-b border-slate-50 last:border-0">
                  <div className="flex justify-between items-start text-xs">
                    <div>
                      <p className="font-semibold font-mono text-blue-600">{sale.invoice_number || sale.sale_number}</p>
                      <p className="text-slate-500">{sale.customer_name || 'Walk-in'}</p>
                      {sale.order_date && <p className="text-[10px] text-slate-400">{sale.order_date} {(sale.created_at || '').slice(11, 16)}</p>}
                    </div>
                    <div className="text-right">
                      <p className="font-bold">{formatPHP(sale.grand_total || sale.total)}</p>
                      <Badge className={`text-[9px] ${sale.payment_type === 'cash' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                        {sale.payment_type || sale.payment_method || 'cash'}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
          </CardContent>
        </Card>
      </div>

      {/* Alerts row */}
      {(stats?.low_stock_count > 0 || (daysSinceClose !== null && daysSinceClose > 0)) && (
        <div className="flex flex-wrap gap-2">
          {stats?.low_stock_count > 0 && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 cursor-pointer" onClick={() => navigate('/inventory')}>
              <AlertTriangle size={13} /> <strong>{stats.low_stock_count}</strong> products at/below reorder point
              <ArrowRight size={11} />
            </div>
          )}
          {daysSinceClose !== null && daysSinceClose > 0 && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 cursor-pointer" onClick={() => navigate('/close-wizard')}>
              <Lock size={13} /> Accounts open for <strong>{daysSinceClose} day{daysSinceClose !== 1 ? 's' : ''}</strong> — close today
              <ArrowRight size={11} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
