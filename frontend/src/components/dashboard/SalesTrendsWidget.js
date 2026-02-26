import { useState, useEffect, useCallback } from 'react';
import { api } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { formatPHP } from '../../lib/utils';
import { TrendingUp, DollarSign, ShoppingCart, Banknote, Smartphone, CreditCard, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const PERIODS = [
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'this_quarter', label: 'This Quarter' },
  { value: 'last_quarter', label: 'Last Quarter' },
  { value: 'this_year', label: 'This Year' },
  { value: 'last_year', label: 'Last Year' },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-500 capitalize">{p.dataKey}:</span>
          <span className="font-semibold">{formatPHP(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

export default function SalesTrendsWidget({ branchId, onPeriodChange }) {
  const [period, setPeriod] = useState('this_month');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period };
      if (branchId && branchId !== 'all') params.branch_id = branchId;
      const res = await api.get('/dashboard/sales-analytics', { params });
      setData(res.data);
      onPeriodChange?.(period);
    } catch {}
    setLoading(false);
  }, [period, branchId, onPeriodChange]);

  useEffect(() => { load(); }, [load]);

  const handlePeriodChange = (val) => setPeriod(val);
  const s = data?.summary || {};

  return (
    <Card className="border-slate-200 h-full" data-testid="sales-trends-widget">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <TrendingUp size={15} className="text-[#1A4D2E]" /> Sales Trends
          </CardTitle>
          <Select value={period} onValueChange={handlePeriodChange}>
            <SelectTrigger className="h-7 w-[130px] text-xs" data-testid="period-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-40"><RefreshCw size={16} className="animate-spin text-slate-400" /></div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
              {[
                { label: 'Revenue', value: formatPHP(s.total_revenue || 0), icon: DollarSign, color: 'text-emerald-700 bg-emerald-50' },
                { label: 'Cash', value: formatPHP(s.total_cash || 0), icon: Banknote, color: 'text-green-700 bg-green-50' },
                { label: 'Digital', value: formatPHP(s.total_digital || 0), icon: Smartphone, color: 'text-blue-700 bg-blue-50' },
                { label: 'Credit', value: formatPHP(s.total_credit || 0), icon: CreditCard, color: 'text-amber-700 bg-amber-50' },
              ].map(({ label, value, icon: Icon, color }) => (
                <div key={label} className={`rounded-lg p-2.5 ${color.split(' ')[1]}`}>
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <Icon size={11} className={color.split(' ')[0]} />
                    <span className="text-[10px] text-slate-500">{label}</span>
                  </div>
                  <p className={`text-sm font-bold font-mono ${color.split(' ')[0]}`}>{value}</p>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-4 text-[10px] text-slate-400 mb-2">
              <span>{s.total_transactions || 0} transactions</span>
              <span>Avg {formatPHP(s.avg_transaction || 0)}/txn</span>
              <span>{s.days_with_sales || 0} active days</span>
            </div>
            {/* Chart */}
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data?.daily || []} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#059669" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tickFormatter={d => d?.slice(5)} tick={{ fontSize: 10 }} stroke="#94a3b8" />
                  <YAxis tickFormatter={v => `${(v/1000).toFixed(0)}k`} tick={{ fontSize: 10 }} stroke="#94a3b8" width={40} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="revenue" stroke="#059669" strokeWidth={2} fill="url(#colorRevenue)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
