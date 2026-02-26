import { useState, useEffect, useCallback } from 'react';
import { api } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { formatPHP } from '../../lib/utils';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, ArrowRight, RefreshCw } from 'lucide-react';

const PERIODS = [
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'quarter', label: 'This Quarter' },
  { value: 'year', label: 'This Year' },
];

export default function InternalProfitWidget() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('this_month');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/internal-invoices/profitability', { params: { period } });
      setData(res.data);
    } catch {}
    setLoading(false);
  }, [period]);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <Card className="border-slate-200 h-full" data-testid="internal-profit-widget">
      <CardContent className="flex items-center justify-center h-40">
        <RefreshCw size={16} className="animate-spin text-slate-400" />
      </CardContent>
    </Card>
  );

  if (!data || !data.branches?.length) return (
    <Card className="border-slate-200 h-full" data-testid="internal-profit-widget">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <TrendingUp size={14} className="text-[#1A4D2E]" /> Internal Profitability
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-slate-400 py-4 text-center">No internal transfers this period</p>
      </CardContent>
    </Card>
  );

  const chartData = data.branches.map(b => ({
    name: b.branch_name?.length > 12 ? b.branch_name.slice(0, 12) + '...' : b.branch_name,
    fullName: b.branch_name,
    revenue: b.revenue,
    cost: b.cost,
    profit: b.profit,
  }));

  return (
    <Card className="border-slate-200 h-full" data-testid="internal-profit-widget">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp size={14} className="text-[#1A4D2E]" /> Internal Profitability
          </CardTitle>
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="h-7 w-32 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PERIODS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Summary row */}
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center p-2 rounded-lg bg-emerald-50">
            <p className="text-[9px] text-emerald-600 uppercase font-semibold tracking-wider">Revenue</p>
            <p className="text-sm font-bold text-emerald-700 font-mono">{formatPHP(data.totals.revenue)}</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-red-50">
            <p className="text-[9px] text-red-600 uppercase font-semibold tracking-wider">Cost</p>
            <p className="text-sm font-bold text-red-700 font-mono">{formatPHP(data.totals.cost)}</p>
          </div>
          <div className={`text-center p-2 rounded-lg ${data.totals.net >= 0 ? 'bg-blue-50' : 'bg-amber-50'}`}>
            <p className="text-[9px] text-blue-600 uppercase font-semibold tracking-wider">Net</p>
            <p className={`text-sm font-bold font-mono ${data.totals.net >= 0 ? 'text-blue-700' : 'text-amber-700'}`}>
              {data.totals.net >= 0 ? '+' : ''}{formatPHP(data.totals.net)}
            </p>
          </div>
        </div>

        {/* Chart */}
        {chartData.length > 0 && (
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 9 }} interval={0} />
                <YAxis tick={{ fontSize: 9 }} tickFormatter={v => `₱${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  formatter={(value, name) => [formatPHP(value), name === 'revenue' ? 'Revenue (supplied)' : name === 'cost' ? 'Cost (received)' : 'Profit']}
                  labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
                  contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e2e8f0' }}
                />
                <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.profit >= 0 ? '#059669' : '#dc2626'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Branch list */}
        <div className="space-y-1">
          {data.branches.slice(0, 5).map((b, i) => (
            <div key={b.branch_id} className="flex items-center justify-between py-1 border-b border-slate-50 last:border-0 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${i === 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{i + 1}</span>
                <span className="truncate">{b.branch_name}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-emerald-600 font-mono">{formatPHP(b.revenue)}</span>
                <span className="text-slate-300">-</span>
                <span className="text-red-500 font-mono">{formatPHP(b.cost)}</span>
                <span className="text-slate-300">=</span>
                <span className={`font-bold font-mono ${b.profit >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                  {b.profit >= 0 ? '+' : ''}{formatPHP(b.profit)}
                </span>
              </div>
            </div>
          ))}
        </div>

        <button onClick={() => navigate('/internal-invoices')}
          className="text-[10px] text-[#1A4D2E] hover:underline flex items-center gap-1">
          View all invoices <ArrowRight size={10} />
        </button>
      </CardContent>
    </Card>
  );
}
