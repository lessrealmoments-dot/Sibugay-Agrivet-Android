import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  DollarSign, ShoppingCart, Package, Users, AlertTriangle, 
  TrendingUp, ArrowDown, Building2, Wallet, Receipt, ArrowRight, Truck, Clock
} from 'lucide-react';
import { formatPHP } from '../lib/utils';

// Branch comparison card for owner view
function BranchCard({ branch, onSelect }) {
  const statusColor = branch.status === 'good' ? 'bg-emerald-500' : 
                      branch.status === 'warning' ? 'bg-amber-500' : 'bg-red-500';
  
  return (
    <Card 
      className="border-slate-200 hover:border-[#1A4D2E]/50 transition-all cursor-pointer hover:shadow-md"
      onClick={() => onSelect(branch.id)}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${statusColor}`}></div>
            <h3 className="font-semibold text-sm">{branch.name}</h3>
          </div>
          <ArrowRight size={14} className="text-slate-400" />
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-slate-500">Sales Today</p>
            <p className="font-bold text-emerald-600">{formatPHP(branch.today_revenue || 0)}</p>
          </div>
          <div>
            <p className="text-slate-500">Transactions</p>
            <p className="font-bold">{branch.today_sales_count || 0}</p>
          </div>
          <div>
            <p className="text-slate-500">Cash Balance</p>
            <p className="font-bold">{formatPHP(branch.cashier_balance || 0)}</p>
          </div>
          <div>
            <p className="text-slate-500">Low Stock</p>
            <p className={`font-bold ${(branch.low_stock_count || 0) > 0 ? 'text-amber-600' : 'text-slate-600'}`}>
              {branch.low_stock_count || 0}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { isConsolidatedView, switchBranch, selectedBranchId } = useAuth();
  const [stats, setStats] = useState(null);
  const [branchSummary, setBranchSummary] = useState(null);
  const [poSummary, setPoSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
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
            api.get('/dashboard/stats'),
            api.get('/purchase-orders/unpaid-summary').catch(() => ({ data: null })),
          ]);
          setStats(res.data);
          setPoSummary(poRes.data);
          setBranchSummary(null);
        }
      } catch (err) {
        console.error('Failed to load dashboard', err);
      }
      setLoading(false);
    };
    fetchData();
  }, [isConsolidatedView, selectedBranchId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading dashboard...</div>
      </div>
    );
  }

  // Owner consolidated view
  if (isConsolidatedView && branchSummary) {
    const totals = branchSummary.totals || {};
    const branches = branchSummary.branches || [];
    
    return (
      <div className="space-y-6 animate-fadeIn" data-testid="owner-dashboard">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Building2 size={20} className="text-emerald-600" />
            <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>
              Owner Dashboard
            </h1>
          </div>
          <p className="text-sm text-slate-500">Consolidated view across all {branches.length} branches</p>
        </div>

        {/* Consolidated KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="border-slate-200 bg-gradient-to-br from-emerald-50 to-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign size={18} className="text-emerald-600" />
                <span className="text-xs text-slate-500">Total Sales Today</span>
              </div>
              <p className="text-2xl font-bold text-emerald-600">{formatPHP(totals.today_revenue || 0)}</p>
            </CardContent>
          </Card>
          
          <Card className="border-slate-200 bg-gradient-to-br from-blue-50 to-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Wallet size={18} className="text-blue-600" />
                <span className="text-xs text-slate-500">Total Cash Position</span>
              </div>
              <p className="text-2xl font-bold text-blue-600">{formatPHP(totals.total_cash || 0)}</p>
            </CardContent>
          </Card>
          
          <Card className="border-slate-200 bg-gradient-to-br from-amber-50 to-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Receipt size={18} className="text-amber-600" />
                <span className="text-xs text-slate-500">Total Receivables</span>
              </div>
              <p className="text-2xl font-bold text-amber-600">{formatPHP(totals.total_receivables || 0)}</p>
            </CardContent>
          </Card>
          
          <Card className="border-slate-200 bg-gradient-to-br from-red-50 to-white">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle size={18} className="text-red-600" />
                <span className="text-xs text-slate-500">Low Stock Alerts</span>
              </div>
              <p className="text-2xl font-bold text-red-600">{totals.low_stock_count || 0}</p>
            </CardContent>
          </Card>
        </div>

        {/* Branch Comparison Grid */}
        <div>
          <h2 className="text-lg font-semibold mb-3" style={{ fontFamily: 'Manrope' }}>Branch Performance</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {branches.map(branch => (
              <BranchCard 
                key={branch.id} 
                branch={branch} 
                onSelect={(id) => switchBranch(id)}
              />
            ))}
          </div>
        </div>

        {/* Additional Insights */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Top Performing Branch */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <TrendingUp size={16} className="text-emerald-600" />
                Top Performing Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              {branches.length > 0 ? (
                <div className="space-y-3">
                  {[...branches]
                    .sort((a, b) => (b.today_revenue || 0) - (a.today_revenue || 0))
                    .slice(0, 3)
                    .map((branch, i) => (
                      <div key={branch.id} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                            i === 0 ? 'bg-emerald-100 text-emerald-700' :
                            i === 1 ? 'bg-blue-100 text-blue-700' :
                            'bg-slate-100 text-slate-700'
                          }`}>{i + 1}</span>
                          <span className="font-medium">{branch.name}</span>
                        </div>
                        <span className="font-bold text-emerald-600">{formatPHP(branch.today_revenue || 0)}</span>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No branch data available</p>
              )}
            </CardContent>
          </Card>

          {/* Alerts */}
          <Card className="border-slate-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-600" />
                Alerts & Attention Required
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {branches.filter(b => (b.low_stock_count || 0) > 0).length > 0 ? (
                  branches
                    .filter(b => (b.low_stock_count || 0) > 0)
                    .map(branch => (
                      <div key={branch.id} className="flex items-center justify-between p-2 rounded bg-amber-50 text-sm">
                        <span>{branch.name}</span>
                        <Badge variant="outline" className="bg-amber-100 text-amber-700 border-amber-200">
                          {branch.low_stock_count} low stock items
                        </Badge>
                      </div>
                    ))
                ) : (
                  <p className="text-sm text-slate-400">No alerts at this time</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity Across Branches */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold">Recent Sales Across All Branches</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.recent_sales?.length ? (
              <div className="space-y-3">
                {stats.recent_sales.map(sale => (
                  <div key={sale.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 text-sm">
                    <div>
                      <p className="font-medium">{sale.sale_number}</p>
                      <p className="text-xs text-slate-500">
                        {sale.customer_name} &middot; {sale.cashier_name}
                        {sale.branch_name && <span className="ml-2 text-blue-600">@ {sale.branch_name}</span>}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold">{formatPHP(sale.total)}</p>
                      <Badge variant="outline" className="text-[10px]">{sale.payment_method}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">No recent sales</p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Single branch view (existing dashboard)
  const kpis = [
    { label: "New Sales Today", value: formatPHP(stats?.today_revenue), icon: DollarSign, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: "Today's Sales", value: stats?.today_sales_count || 0, icon: ShoppingCart, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: "Today's Expenses", value: formatPHP(stats?.today_expenses), icon: ArrowDown, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'Total Products', value: stats?.total_products || 0, icon: Package, color: 'text-slate-600', bg: 'bg-slate-50' },
    { label: 'Low Stock Items', value: stats?.low_stock_count || 0, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'Total Customers', value: stats?.total_customers || 0, icon: Users, color: 'text-violet-600', bg: 'bg-violet-50' },
  ];

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="dashboard-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Overview of your business performance</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((kpi, i) => (
          <Card key={i} className="border-slate-200 hover:border-[#1A4D2E]/30 transition-colors" data-testid={`kpi-${kpi.label.replace(/\s+/g, '-').toLowerCase()}`}>
            <CardContent className="p-4">
              <div className={`w-9 h-9 rounded-lg ${kpi.bg} flex items-center justify-center mb-3`}>
                <kpi.icon size={18} className={kpi.color} strokeWidth={1.5} />
              </div>
              <p className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>{kpi.value}</p>
              <p className="text-xs text-slate-500 mt-1">{kpi.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Receivables */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold" style={{ fontFamily: 'Manrope' }}>Outstanding Receivables</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-amber-600" style={{ fontFamily: 'Manrope' }}>
              {formatPHP(stats?.total_receivables || 0)}
            </p>
            <p className="text-xs text-slate-500 mt-1">Total unpaid customer credit</p>
          </CardContent>
        </Card>

        {/* Unpaid POs */}
        <Card className="border-slate-200 lg:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
                <Truck size={16} className="text-red-600" /> Unpaid Purchase Orders
              </CardTitle>
              {poSummary?.total_unpaid > 0 && (
                <span className="text-sm font-bold text-red-600">{formatPHP(poSummary.total_unpaid)}</span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!poSummary || poSummary.total_count === 0 ? (
              <p className="text-sm text-slate-400">All POs paid up to date</p>
            ) : (
              <div className="space-y-2">
                {[
                  { items: poSummary.overdue, label: 'Overdue', cls: 'bg-red-100 text-red-700 border-red-200' },
                  { items: poSummary.due_soon, label: 'Due This Week', cls: 'bg-amber-100 text-amber-700 border-amber-200' },
                  { items: poSummary.later, label: 'Upcoming', cls: 'bg-slate-100 text-slate-600' },
                ].filter(g => g.items?.length > 0).slice(0, 2).map(group => (
                  <div key={group.label}>
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className={`text-[10px] ${group.cls}`}>{group.label}</Badge>
                      <span className="text-xs text-slate-400">{group.items.length} PO{group.items.length !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="space-y-1">
                      {group.items.slice(0, 3).map(po => (
                        <div key={po.id} className="flex items-center justify-between text-xs bg-slate-50 rounded px-2 py-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-blue-600">{po.po_number}</span>
                            <span className="text-slate-500 truncate max-w-[120px]">{po.vendor}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            {po.due_date && <span className={`${po.due_date < new Date().toISOString().slice(0,10) ? 'text-red-500' : 'text-slate-400'}`}>{po.due_date}</span>}
                            <span className="font-bold text-red-600">{formatPHP(po.balance)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Top Products */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <TrendingUp size={16} className="text-emerald-600" /> Top Products
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.top_products?.length ? (
              <div className="space-y-3">
                {stats.top_products.map((p, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-slate-100 text-[10px] flex items-center justify-center font-bold text-slate-500">{i + 1}</span>
                      <span className="font-medium truncate max-w-[180px]">{p.name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-slate-500">{p.quantity} sold</span>
                      <span className="ml-3 font-semibold">{p.revenue?.toLocaleString('en', { minimumFractionDigits: 2 })}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">No sales data yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Sales */}
      <Card className="border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold" style={{ fontFamily: 'Manrope' }}>Recent Sales</CardTitle>
        </CardHeader>
        <CardContent>
          {stats?.recent_sales?.length ? (
            <div className="space-y-3">
              {stats.recent_sales.map(sale => (
                <div key={sale.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 text-sm">
                  <div>
                    <p className="font-medium">{sale.sale_number}</p>
                    <p className="text-xs text-slate-500">{sale.customer_name} &middot; {sale.cashier_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{formatPHP(sale.total)}</p>
                    <Badge variant="outline" className="text-[10px]">{sale.payment_method}</Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No recent sales</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
