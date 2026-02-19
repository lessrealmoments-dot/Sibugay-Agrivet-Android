import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { DollarSign, ShoppingCart, Package, Users, AlertTriangle, TrendingUp, ArrowDown } from 'lucide-react';

export default function DashboardPage() {
  const { currentBranch } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const params = currentBranch ? { branch_id: currentBranch.id } : {};
        const res = await api.get('/dashboard/stats', { params });
        setStats(res.data);
      } catch (err) {
        console.error('Failed to load dashboard stats', err);
      }
      setLoading(false);
    };
    fetchStats();
  }, [currentBranch]);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-slate-400">Loading dashboard...</div></div>;

  const kpis = [
    { label: "Today's Revenue", value: `${(stats?.today_revenue || 0).toLocaleString('en', { minimumFractionDigits: 2 })}`, icon: DollarSign, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: "Today's Sales", value: stats?.today_sales_count || 0, icon: ShoppingCart, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: "Today's Expenses", value: `${(stats?.today_expenses || 0).toLocaleString('en', { minimumFractionDigits: 2 })}`, icon: ArrowDown, color: 'text-red-600', bg: 'bg-red-50' },
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

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Receivables */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold" style={{ fontFamily: 'Manrope' }}>Outstanding Receivables</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-amber-600" style={{ fontFamily: 'Manrope' }}>
              {(stats?.total_receivables || 0).toLocaleString('en', { minimumFractionDigits: 2 })}
            </p>
            <p className="text-xs text-slate-500 mt-1">Total unpaid customer credit</p>
          </CardContent>
        </Card>

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
                    <p className="font-semibold">{sale.total?.toLocaleString('en', { minimumFractionDigits: 2 })}</p>
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
