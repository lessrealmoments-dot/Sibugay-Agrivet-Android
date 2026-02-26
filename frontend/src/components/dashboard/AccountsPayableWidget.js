import { useState, useEffect, useCallback } from 'react';
import { api } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { formatPHP } from '../../lib/utils';
import { FileText, AlertTriangle, Clock, ChevronRight, RefreshCw } from 'lucide-react';

export default function AccountsPayableWidget({ branchId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (branchId && branchId !== 'all') params.branch_id = branchId;
      const res = await api.get('/dashboard/accounts-payable', { params });
      setData(res.data);
    } catch {}
    setLoading(false);
  }, [branchId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <Card className="border-slate-200 h-full" data-testid="ap-widget">
      <CardContent className="flex items-center justify-center h-40"><RefreshCw size={16} className="animate-spin text-slate-400" /></CardContent>
    </Card>
  );

  const d = data || {};
  const hasOverdue = d.overdue_count > 0;

  return (
    <Card className={`border-slate-200 h-full ${hasOverdue ? 'border-red-200' : ''}`} data-testid="ap-widget">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <FileText size={15} className="text-red-600" /> Accounts Payable
          </CardTitle>
          <Button variant="ghost" size="sm" className="h-7 text-xs text-slate-500" onClick={() => navigate('/pay-supplier')}>
            Pay <ChevronRight size={12} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Total */}
        <div className="text-center py-2">
          <p className="text-2xl font-bold font-mono text-red-700" style={{ fontFamily: 'Manrope' }}>{formatPHP(d.total_payable || 0)}</p>
          <p className="text-[10px] text-slate-400">Total outstanding</p>
        </div>

        {/* Breakdown */}
        <div className="grid grid-cols-3 gap-2">
          <div className={`rounded-lg p-2.5 text-center ${hasOverdue ? 'bg-red-50 border border-red-200' : 'bg-slate-50'}`}>
            <p className={`text-sm font-bold font-mono ${hasOverdue ? 'text-red-700' : 'text-slate-500'}`}>{formatPHP(d.overdue_total || 0)}</p>
            <p className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
              {hasOverdue && <AlertTriangle size={9} className="text-red-500" />}
              Overdue ({d.overdue_count || 0})
            </p>
          </div>
          <div className="rounded-lg p-2.5 text-center bg-amber-50 border border-amber-200">
            <p className="text-sm font-bold font-mono text-amber-700">{formatPHP(d.due_this_week_total || 0)}</p>
            <p className="text-[10px] text-slate-500 flex items-center justify-center gap-1">
              <Clock size={9} className="text-amber-500" />
              This Week
            </p>
          </div>
          <div className="rounded-lg p-2.5 text-center bg-slate-50">
            <p className="text-sm font-bold font-mono text-slate-700">{formatPHP(d.upcoming_total || 0)}</p>
            <p className="text-[10px] text-slate-500">Upcoming ({d.upcoming_count || 0})</p>
          </div>
        </div>

        {/* Overdue list */}
        {hasOverdue && (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold text-red-600 uppercase">Overdue</p>
            {(d.overdue || []).slice(0, 3).map(po => (
              <div key={po.po_id} className="flex items-center justify-between text-xs bg-red-50 rounded px-2.5 py-1.5">
                <div>
                  <p className="font-semibold font-mono">{po.po_number}</p>
                  <p className="text-slate-500 text-[10px]">{po.vendor}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-red-700">{formatPHP(po.balance)}</p>
                  <p className="text-red-500 text-[10px]">{Math.abs(po.days_left)}d overdue</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Due this week */}
        {(d.due_this_week || []).length > 0 && (
          <div className="space-y-1">
            <p className="text-[10px] font-semibold text-amber-600 uppercase">Due This Week</p>
            {(d.due_this_week || []).slice(0, 3).map(po => (
              <div key={po.po_id} className="flex items-center justify-between text-xs bg-amber-50 rounded px-2.5 py-1.5">
                <div>
                  <p className="font-semibold font-mono">{po.po_number}</p>
                  <p className="text-slate-500 text-[10px]">{po.vendor}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-amber-700">{formatPHP(po.balance)}</p>
                  <p className="text-amber-500 text-[10px]">{po.days_left === 0 ? 'Due today' : `${po.days_left}d left`}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {d.total_payable === 0 && (
          <p className="text-xs text-emerald-600 text-center py-3">All supplier payments are up to date</p>
        )}
      </CardContent>
    </Card>
  );
}
