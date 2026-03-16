import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Package, RefreshCw, ExternalLink, AlertTriangle, Search, Clock, CheckCircle2
} from 'lucide-react';

const fmtDate = (d) => { try { return new Date(d).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return d || ''; } };

function daysSince(dateStr) {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
  } catch { return 0; }
}

export default function PendingReleasesPage() {
  const { currentBranch, branches, user } = useAuth();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [branchFilter, setBranchFilter] = useState('__all__');
  const [statusFilter, setStatusFilter] = useState('pending'); // pending | all
  const [summary, setSummary] = useState(null);

  const isAdmin = user?.role === 'admin';
  const effectiveBranch = (branchFilter === '__all__' ? '' : branchFilter) || currentBranch?.id || '';

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (effectiveBranch) params.branch_id = effectiveBranch;
      if (statusFilter === 'pending') {
        // default — only not_released and partially_released
      } else {
        params.status = 'all'; // include fully_released and expired
      }

      const [listRes, summaryRes] = await Promise.all([
        api.get('/stock-releases', { params }),
        api.get('/stock-releases/summary', { params: effectiveBranch ? { branch_id: effectiveBranch } : {} }),
      ]);
      setInvoices(listRes.data.invoices || []);
      setSummary(summaryRes.data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [effectiveBranch, statusFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = invoices.filter(inv => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      inv.invoice_number?.toLowerCase().includes(s) ||
      inv.customer_name?.toLowerCase().includes(s)
    );
  });

  const releaseStatusBadge = (s) => {
    const map = {
      not_released: 'bg-amber-100 text-amber-700',
      partially_released: 'bg-blue-100 text-blue-700',
      fully_released: 'bg-emerald-100 text-emerald-700',
      expired: 'bg-slate-200 text-slate-500',
    };
    const labels = {
      not_released: 'Not Released',
      partially_released: 'Partially Released',
      fully_released: 'Fully Released',
      expired: 'Expired',
    };
    return { cls: map[s] || 'bg-slate-100 text-slate-600', label: labels[s] || s };
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="pending-releases-page">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Pending Releases</h1>
          <p className="text-sm text-slate-500 mt-0.5">Track invoices with stock reserved for customer pickup</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="h-9" data-testid="refresh-releases">
          <RefreshCw size={13} className={loading ? 'animate-spin mr-1.5' : 'mr-1.5'} /> Refresh
        </Button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="border-slate-200">
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 uppercase font-medium mb-1">Pending Invoices</p>
              <p className="text-2xl font-bold" style={{ fontFamily: 'Manrope' }}>{summary.pending_invoice_count}</p>
            </CardContent>
          </Card>
          <Card className="border-slate-200">
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 uppercase font-medium mb-1">Total Reserved Qty</p>
              <p className="text-2xl font-bold text-amber-600" style={{ fontFamily: 'Manrope' }}>{summary.total_reserved_qty}</p>
              <p className="text-[10px] text-slate-400">units on hold</p>
            </CardContent>
          </Card>
          <Card className={`border-slate-200 ${summary.has_overdue ? 'border-red-200 bg-red-50/40' : ''}`}>
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 uppercase font-medium mb-1">Overdue (&gt;30 days)</p>
              <p className={`text-2xl font-bold ${summary.has_overdue ? 'text-red-600' : 'text-slate-400'}`} style={{ fontFamily: 'Manrope' }}>
                {summary.overdue_reservations}
              </p>
              {summary.has_overdue && <p className="text-[10px] text-red-500">Will auto-return to stock</p>}
            </CardContent>
          </Card>
          <Card className="border-slate-200">
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 uppercase font-medium mb-1">Showing</p>
              <p className="text-2xl font-bold" style={{ fontFamily: 'Manrope' }}>{filtered.length}</p>
              <p className="text-[10px] text-slate-400">invoices</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Overdue warning */}
      {summary?.has_overdue && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-3">
          <AlertTriangle size={16} className="text-red-500 mt-0.5 shrink-0" />
          <p className="text-sm text-red-700">
            <strong>{summary.overdue_reservations}</strong> reservation{summary.overdue_reservations !== 1 ? 's are' : ' is'} overdue (&gt;30 days).
            These will be automatically returned to available inventory at 7:30 AM.
            Contact the customers to arrange pickup.
          </p>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48 max-w-72">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search invoice # or customer..."
            className="pl-8 h-9 text-sm"
            data-testid="search-releases"
          />
        </div>
        {isAdmin && branches.length > 1 && (
          <Select value={branchFilter} onValueChange={setBranchFilter}>
            <SelectTrigger className="h-9 w-44 text-sm" data-testid="branch-filter">
              <SelectValue placeholder="All Branches" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Branches</SelectItem>
              {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-9 w-40 text-sm" data-testid="status-filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">Pending Only</SelectItem>
            <SelectItem value="all">All (incl. completed)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-slate-400">
          <RefreshCw size={20} className="animate-spin mr-2" /> Loading...
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <CheckCircle2 size={36} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium">No pending releases</p>
          <p className="text-sm mt-1">All stock has been released or no partial-release invoices found</p>
        </div>
      ) : (
        <Card className="border-slate-200">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase text-slate-500">Invoice</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Customer</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Sale Date</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Age</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Items Pending</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500text-right">Progress</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map(inv => {
                  const days = daysSince(inv.created_at);
                  const isOverdue = days >= 30;
                  const s = releaseStatusBadge(inv.stock_release_status);
                  const pct = inv.reservation_summary?.pct_released || 0;
                  const remaining = inv.reservation_summary?.total_remaining || 0;
                  const total = inv.reservation_summary?.total_ordered || 0;

                  return (
                    <TableRow
                      key={inv.id}
                      className={`cursor-pointer hover:bg-slate-50 ${isOverdue ? 'bg-red-50/30' : ''}`}
                      onClick={() => inv.doc_code && window.open(`/doc/${inv.doc_code}`, '_blank')}
                      data-testid={`release-row-${inv.id}`}
                    >
                      <TableCell>
                        <span className="font-mono text-sm text-blue-600 font-medium">{inv.invoice_number}</span>
                        {inv.doc_code && (
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{inv.doc_code}</div>
                        )}
                      </TableCell>
                      <TableCell className="text-sm font-medium">{inv.customer_name || 'Walk-in'}</TableCell>
                      <TableCell className="text-xs text-slate-500">{fmtDate(inv.created_at)}</TableCell>
                      <TableCell>
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          isOverdue ? 'bg-red-100 text-red-700' :
                          days >= 14 ? 'bg-amber-100 text-amber-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {days}d
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge className={`text-[10px] border-0 ${s.cls}`}>{s.label}</Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        <div className="space-y-0.5">
                          {(inv.reservation_summary?.total_remaining > 0) ? (
                            <span className="text-amber-700 font-medium">
                              {remaining} units remaining
                            </span>
                          ) : (
                            <span className="text-emerald-600 text-xs">All released</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {total > 0 && (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-slate-200 rounded-full h-1.5 min-w-16">
                              <div
                                className={`h-1.5 rounded-full transition-all ${pct >= 100 ? 'bg-emerald-500' : pct > 0 ? 'bg-blue-500' : 'bg-amber-400'}`}
                                style={{ width: `${Math.min(100, pct)}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-400 shrink-0">{pct.toFixed(0)}%</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {inv.doc_code ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-blue-600"
                            onClick={e => { e.stopPropagation(); window.open(`/doc/${inv.doc_code}`, '_blank'); }}
                            data-testid={`open-doc-${inv.id}`}
                          >
                            <ExternalLink size={13} />
                          </Button>
                        ) : (
                          <span className="text-[10px] text-slate-300">No QR</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
