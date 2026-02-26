import { useState, useEffect, useCallback } from 'react';
import { api } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { formatPHP } from '../../lib/utils';
import { BarChart3, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const COLORS = ['#059669', '#0891b2', '#7c3aed', '#ea580c', '#dc2626', '#2563eb', '#ca8a04', '#64748b'];

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{d?.name}</p>
      <p className="text-emerald-700 font-mono font-bold">{formatPHP(d?.revenue || 0)}</p>
      <p className="text-slate-400">{d?.count || 0} transactions</p>
    </div>
  );
};

export default function BranchComparisonWidget({ period = 'this_month', branchId }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [metric, setMetric] = useState('revenue');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { period };
      if (branchId && branchId !== 'all') params.branch_id = branchId;
      const res = await api.get('/dashboard/sales-analytics', { params });
      setData(res.data.branches || []);
    } catch {}
    setLoading(false);
  }, [period, branchId]);

  useEffect(() => { load(); }, [load]);

  // Abbreviate long branch names
  const chartData = data.slice(0, 10).map(b => ({
    ...b,
    shortName: b.name.length > 12 ? b.name.slice(0, 11) + '…' : b.name,
  }));

  return (
    <Card className="border-slate-200 h-full" data-testid="branch-comparison-widget">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <BarChart3 size={15} className="text-blue-600" /> Branch Comparison
          </CardTitle>
          <Select value={metric} onValueChange={setMetric}>
            <SelectTrigger className="h-7 w-[100px] text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="revenue">Revenue</SelectItem>
              <SelectItem value="count">Transactions</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-40"><RefreshCw size={16} className="animate-spin text-slate-400" /></div>
        ) : chartData.length === 0 ? (
          <p className="text-xs text-slate-400 text-center py-8">No branch data for this period</p>
        ) : (
          <>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }} barSize={28}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="shortName" tick={{ fontSize: 9 }} stroke="#94a3b8" interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis
                    tickFormatter={metric === 'revenue' ? v => `${(v/1000).toFixed(0)}k` : v => v}
                    tick={{ fontSize: 10 }} stroke="#94a3b8" width={45}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey={metric} radius={[4, 4, 0, 0]}>
                    {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Leaderboard */}
            <div className="mt-3 space-y-1">
              {data.slice(0, 5).map((b, i) => (
                <div key={b.branch_id} className="flex items-center justify-between text-xs py-1 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white`}
                      style={{ background: COLORS[i % COLORS.length] }}>{i + 1}</span>
                    <span className="font-medium truncate max-w-[140px]">{b.name}</span>
                  </div>
                  <div className="text-right">
                    <span className="font-mono font-semibold text-slate-800">{formatPHP(b.revenue)}</span>
                    <span className="text-slate-400 ml-2">{b.count} txn</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
