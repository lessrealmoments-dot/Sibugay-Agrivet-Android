import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  ShieldCheck, RefreshCw, AlertTriangle, Check, X, ChevronDown, ChevronUp,
  Printer, History, Plus, Package, Banknote, TrendingUp, Users, ArrowRight,
  RotateCcw, FileText, Clock, Building2
} from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// ─────────────────────────────────────────────────────────────────────────────
//  Severity helpers
// ─────────────────────────────────────────────────────────────────────────────
const SEV_COLORS = {
  ok: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  warning: 'text-amber-700 bg-amber-50 border-amber-200',
  critical: 'text-red-700 bg-red-50 border-red-200',
};
const SEV_ICONS = {
  ok: <Check size={16} className="text-emerald-600" />,
  warning: <AlertTriangle size={16} className="text-amber-600" />,
  critical: <AlertTriangle size={16} className="text-red-600" />,
};
const SEV_LABELS = { ok: 'Good', warning: 'Needs Review', critical: 'Critical' };
const SEV_BADGE = {
  ok: 'bg-emerald-100 text-emerald-700',
  warning: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
};

function SevBadge({ sev }) {
  return <Badge className={`text-[10px] ${SEV_BADGE[sev] || SEV_BADGE.ok}`}>{SEV_LABELS[sev] || '—'}</Badge>;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Section Card
// ─────────────────────────────────────────────────────────────────────────────
function SectionCard({ icon, title, sev, children, defaultOpen = false, data_testid }) {
  const [open, setOpen] = useState(defaultOpen || sev === 'critical');
  return (
    <Card className={`border-2 ${sev ? SEV_COLORS[sev] : 'border-slate-200'} transition-all`} data-testid={data_testid}>
      <button className="w-full flex items-center justify-between p-4 text-left" onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${sev === 'critical' ? 'bg-red-100' : sev === 'warning' ? 'bg-amber-100' : 'bg-emerald-100'}`}>
            {icon}
          </div>
          <div>
            <p className="font-semibold text-slate-800 text-sm" style={{ fontFamily: 'Manrope' }}>{title}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sev && <SevBadge sev={sev} />}
          {open ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>
      {open && (
        <CardContent className="px-4 pb-4 pt-0 border-t border-current/10">
          {children}
        </CardContent>
      )}
    </Card>
  );
}

function StatRow({ label, value, highlight, sub }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-slate-100 last:border-0">
      <span className="text-sm text-slate-600">{label}</span>
      <div className="text-right">
        <span className={`font-mono text-sm font-semibold ${highlight || ''}`}>{value}</span>
        {sub && <p className="text-[10px] text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
//  Main Audit Center Page
// ─────────────────────────────────────────────────────────────────────────────
export default function AuditCenterPage() {
  const { currentBranch, branches, user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10);

  const [tab, setTab] = useState('run');
  const [sessions, setSessions] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // ── New Audit setup ──────────────────────────────────────────────────────
  const [auditType, setAuditType] = useState('partial');
  const [auditBranchId, setAuditBranchId] = useState(currentBranch?.id || '');
  const [periodFrom, setPeriodFrom] = useState(firstOfMonth);
  const [periodTo, setPeriodTo] = useState(today);

  // ── Computed audit data ────────────────────────────────────────────────
  const [auditData, setAuditData] = useState(null);
  const [computing, setComputing] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  // ── Cash actual count entry ────────────────────────────────────────────
  const [actualCashCount, setActualCashCount] = useState('');

  useEffect(() => {
    if (currentBranch?.id) setAuditBranchId(currentBranch.id);
  }, [currentBranch?.id]);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (auditBranchId) params.set('branch_id', auditBranchId);
      const res = await api.get(`${BACKEND_URL}/api/audit/sessions?${params}`);
      setSessions(res.data.sessions || []);
    } catch { }
    setLoadingHistory(false);
  }, [auditBranchId]);

  useEffect(() => { if (tab === 'history') loadHistory(); }, [tab, loadHistory]);

  const runAudit = async () => {
    if (!auditBranchId && !isAdmin) { toast.error('Select a branch'); return; }
    setComputing(true);
    setAuditData(null);
    try {
      const params = new URLSearchParams({
        audit_type: auditType,
        period_from: periodFrom,
        period_to: periodTo,
      });
      if (auditBranchId) params.set('branch_id', auditBranchId);

      const [computeRes, sessionRes] = await Promise.all([
        api.get(`${BACKEND_URL}/api/audit/compute?${params}`),
        api.post(`${BACKEND_URL}/api/audit/sessions`, {
          audit_type: auditType,
          branch_id: auditBranchId,
          period_from: periodFrom,
          period_to: periodTo,
        }),
      ]);
      setAuditData(computeRes.data);
      setSessionId(sessionRes.data.id);
      setActualCashCount('');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Audit computation failed');
    }
    setComputing(false);
  };

  const computeOverallScore = (data) => {
    if (!data) return null;
    const sections = ['cash', 'sales', 'ar', 'payables', 'transfers', 'returns', 'activity'];
    if (data.inventory?.available) sections.push('inventory');
    const scores = sections.map(s => {
      const sev = data[s]?.severity;
      return sev === 'ok' ? 100 : sev === 'warning' ? 60 : 20;
    });
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  };

  const finalizeAudit = async () => {
    if (!sessionId || !auditData) return;
    const score = computeOverallScore(auditData);
    try {
      await api.put(`${BACKEND_URL}/api/audit/sessions/${sessionId}`, {
        overall_score: score,
        status: 'completed',
        sections_status: {
          cash: auditData.cash?.severity,
          sales: auditData.sales?.severity,
          ar: auditData.ar?.severity,
          payables: auditData.payables?.severity,
          transfers: auditData.transfers?.severity,
          returns: auditData.returns?.severity,
          activity: auditData.activity?.severity,
          inventory: auditData.inventory?.severity,
        },
      });
      toast.success(`Audit completed! Score: ${score}/100`);
      setTab('history');
      loadHistory();
    } catch { toast.error('Failed to save audit'); }
  };

  const printAuditReport = () => {
    if (!auditData) return;
    const score = computeOverallScore(auditData);
    const branch = branches?.find(b => b.id === auditBranchId)?.name || auditBranchId;
    const win = window.open('', '_blank');
    const php = (n) => '₱' + (parseFloat(n) || 0).toLocaleString('en-PH', { minimumFractionDigits: 2 });
    const sevLabel = (s) => s === 'ok' ? '✓ Good' : s === 'warning' ? '⚠ Review' : '✗ Critical';

    win.document.write(`<html><head><title>Audit Report</title>
    <style>
      body { font-family: Arial, sans-serif; font-size: 12px; padding: 24px; }
      h1 { color: #1A4D2E; margin-bottom: 4px; }
      .meta { color: #666; margin-bottom: 20px; }
      .score { font-size: 28px; font-weight: bold; color: ${score >= 80 ? '#15803d' : score >= 50 ? '#d97706' : '#dc2626'}; }
      table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
      th { background: #1A4D2E; color: white; padding: 6px 10px; text-align: left; }
      td { padding: 5px 10px; border-bottom: 1px solid #eee; }
      .ok { color: #15803d; } .warning { color: #d97706; } .critical { color: #dc2626; }
      .section-header { background: #f1f5f9; font-weight: bold; padding: 6px 10px; margin-top: 12px; }
    </style></head><body>
    <h1>AgriBooks — Audit Report</h1>
    <div class="meta">Branch: ${branch} · Period: ${periodFrom} to ${periodTo} · Type: ${auditType} · Auditor: ${user?.username}</div>
    <div>Overall Score: <span class="score">${score}/100</span></div>
    <br/>
    <table>
      <thead><tr><th>Section</th><th>Status</th><th>Key Finding</th></tr></thead>
      <tbody>
        <tr><td>Cash/Fund Reconciliation</td><td class="${auditData.cash?.severity}">${sevLabel(auditData.cash?.severity)}</td>
            <td>Expected: ${php(auditData.cash?.expected_cash)} · Discrepancy: ${php(auditData.cash?.discrepancy)}</td></tr>
        <tr><td>Sales Audit</td><td class="${auditData.sales?.severity}">${sevLabel(auditData.sales?.severity)}</td>
            <td>Total: ${php(auditData.sales?.grand_total_sales)} · Voided: ${auditData.sales?.voided_count} · Edited: ${auditData.sales?.edited_count}</td></tr>
        <tr><td>AR/Receivables</td><td class="${auditData.ar?.severity}">${sevLabel(auditData.ar?.severity)}</td>
            <td>Outstanding: ${php(auditData.ar?.total_outstanding_ar)} · Overdue: ${auditData.ar?.aging?.b90plus > 0 ? php(auditData.ar?.aging.b90plus) + ' 90+days' : 'None'}</td></tr>
        <tr><td>Payables</td><td class="${auditData.payables?.severity}">${sevLabel(auditData.payables?.severity)}</td>
            <td>Outstanding AP: ${php(auditData.payables?.total_outstanding_ap)} · Overdue: ${auditData.payables?.overdue_count}</td></tr>
        <tr><td>Branch Transfers</td><td class="${auditData.transfers?.severity}">${sevLabel(auditData.transfers?.severity)}</td>
            <td>Shortages: ${auditData.transfers?.with_shortage} · Pending: ${auditData.transfers?.pending_count}</td></tr>
        <tr><td>Returns & Losses</td><td class="${auditData.returns?.severity}">${sevLabel(auditData.returns?.severity)}</td>
            <td>Total refunded: ${php(auditData.returns?.total_refunded)} · Loss: ${php(auditData.returns?.total_loss_value)}</td></tr>
        <tr><td>User Activity</td><td class="${auditData.activity?.severity}">${sevLabel(auditData.activity?.severity)}</td>
            <td>Corrections: ${auditData.activity?.inventory_corrections_count} · Edits: ${auditData.activity?.invoice_edits_count} · Off-hours: ${auditData.activity?.off_hours_count}</td></tr>
        ${auditData.inventory?.available ? `<tr><td>Inventory (Physical)</td><td class="${auditData.inventory?.severity}">${sevLabel(auditData.inventory?.severity)}</td>
            <td>Accuracy: ${auditData.inventory?.summary?.inventory_accuracy_pct}% · Variance: ${php(auditData.inventory?.summary?.total_variance_capital)}</td></tr>` : ''}
      </tbody>
    </table>
    <p style="font-size:10px;color:#888">Generated: ${new Date().toLocaleString()} — AgriBooks Business Management</p>
    </body></html>`);
    win.document.close();
    win.print();
  };

  const overallScore = computeOverallScore(auditData);
  const scoreColor = !overallScore ? 'text-slate-400' : overallScore >= 80 ? 'text-emerald-600' : overallScore >= 50 ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="p-6 space-y-5 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#1A4D2E] flex items-center justify-center">
            <ShieldCheck size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-800" style={{ fontFamily: 'Manrope' }}>Audit Center</h1>
            <p className="text-xs text-slate-500">Comprehensive business audit — cash, inventory, sales, AR, payables, activity</p>
          </div>
        </div>
        {auditData && (
          <div className="text-center">
            <p className={`text-4xl font-bold font-mono ${scoreColor}`}>{overallScore}/100</p>
            <p className="text-xs text-slate-500 mt-0.5">Overall Audit Score</p>
          </div>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="run"><ShieldCheck size={14} className="mr-1.5" />Run Audit</TabsTrigger>
          <TabsTrigger value="history" data-testid="audit-history-tab"><History size={14} className="mr-1.5" />Audit History</TabsTrigger>
        </TabsList>

        {/* ── RUN AUDIT TAB ────────────────────────────────────────────── */}
        <TabsContent value="run" className="mt-4 space-y-4">
          {/* Setup card */}
          <Card className="border-slate-200">
            <CardContent className="p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {isAdmin && (
                  <div>
                    <Label className="text-xs text-slate-500">Audit Type</Label>
                    <Select value={auditType} onValueChange={setAuditType}>
                      <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="partial">Partial — Financial Only</SelectItem>
                        <SelectItem value="full">Full — Includes Inventory</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {isAdmin && (
                  <div>
                    <Label className="text-xs text-slate-500">Branch</Label>
                    <Select value={auditBranchId || 'all'} onValueChange={v => setAuditBranchId(v === 'all' ? '' : v)}>
                      <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Branches</SelectItem>
                        {(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div>
                  <Label className="text-xs text-slate-500">Period From</Label>
                  <Input type="date" value={periodFrom} onChange={e => setPeriodFrom(e.target.value)} className="mt-1 h-9" />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Period To</Label>
                  <Input type="date" value={periodTo} onChange={e => setPeriodTo(e.target.value)} className="mt-1 h-9" />
                </div>
              </div>

              {auditType === 'full' && (
                <div className="mt-3 p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-800">
                  <p className="font-semibold mb-0.5">Full Audit — Inventory Comparison</p>
                  <p>The system will auto-detect the last 2 completed count sheets for the selected branch and compare expected quantities (from all movements) against physical counts.</p>
                </div>
              )}

              <div className="flex gap-3 mt-4">
                <Button onClick={runAudit} disabled={computing}
                  className="bg-[#1A4D2E] hover:bg-[#14532d] text-white h-10 px-8"
                  data-testid="run-audit-btn">
                  {computing ? <RefreshCw size={16} className="animate-spin mr-2" /> : <ShieldCheck size={16} className="mr-2" />}
                  {computing ? 'Computing...' : 'Run Audit'}
                </Button>
                {auditData && (
                  <>
                    <Button variant="outline" onClick={printAuditReport} className="h-10">
                      <Printer size={14} className="mr-1.5" /> Print Report
                    </Button>
                    <Button onClick={finalizeAudit} className="bg-emerald-600 hover:bg-emerald-700 text-white h-10 ml-auto">
                      <Check size={14} className="mr-1.5" /> Finalize Audit
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {auditData && (
            <div className="space-y-3">
              {/* Score summary */}
              <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
                {[
                  { key: 'cash', label: 'Cash', icon: <Banknote size={14} /> },
                  { key: 'sales', label: 'Sales', icon: <TrendingUp size={14} /> },
                  { key: 'ar', label: 'AR', icon: <FileText size={14} /> },
                  { key: 'payables', label: 'Payables', icon: <Building2 size={14} /> },
                  { key: 'transfers', label: 'Transfers', icon: <ArrowRight size={14} /> },
                  { key: 'returns', label: 'Returns', icon: <RotateCcw size={14} /> },
                  { key: 'activity', label: 'Activity', icon: <Users size={14} /> },
                  ...(auditData.inventory?.available ? [{ key: 'inventory', label: 'Inventory', icon: <Package size={14} /> }] : []),
                ].map(s => {
                  const sev = auditData[s.key]?.severity || 'ok';
                  return (
                    <div key={s.key} className={`p-2 rounded-lg border text-center ${SEV_COLORS[sev]}`}>
                      <div className="flex justify-center mb-1">{s.icon}</div>
                      <p className="text-[10px] font-medium">{s.label}</p>
                      <p className="text-[9px] mt-0.5">{SEV_LABELS[sev]}</p>
                    </div>
                  );
                })}
              </div>

              {/* Section 2: Cash */}
              <SectionCard title="Cash & Fund Reconciliation" icon={<Banknote size={16} className="text-emerald-700" />}
                sev={auditData.cash?.severity} defaultOpen data_testid="audit-cash-section">
                <div className="space-y-1 mt-2">
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 mb-3">
                    <p className="text-[10px] text-slate-500 font-medium uppercase mb-2">Formula: Starting Float + Cash Sales + AR Collected − All Expenses = Expected Cash</p>
                    <StatRow label="Starting Float" value={formatPHP(auditData.cash.starting_float)} />
                    <StatRow label="+ Cash Sales" value={formatPHP(auditData.cash.cash_sales)} highlight="text-emerald-600" />
                    <StatRow label="+ AR Collected" value={formatPHP(auditData.cash.ar_collected)} highlight="text-emerald-600" />
                    <StatRow label="− Total Expenses" value={`-${formatPHP(auditData.cash.total_expenses)}`} highlight="text-red-600" />
                    <Separator className="my-2" />
                    <StatRow label="Expected Cash" value={formatPHP(auditData.cash.expected_cash)} highlight="font-bold text-slate-800" />
                    <StatRow label="Current Cashier Balance" value={formatPHP(auditData.cash.current_cashier_balance)} />
                    <StatRow label="Safe Balance" value={formatPHP(auditData.cash.safe_balance)} />
                  </div>
                  {/* Actual cash count entry */}
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
                    <div className="flex-1">
                      <Label className="text-xs text-amber-800 font-medium">Enter Actual Cash Count (Cashier Drawer Only)</Label>
                      <Input type="number" min={0} value={actualCashCount}
                        onChange={e => setActualCashCount(e.target.value)}
                        placeholder="0.00" className="mt-1 h-8 font-mono" />
                    </div>
                    {actualCashCount && (
                      <div className="text-right">
                        <p className="text-xs text-slate-500">Discrepancy vs Expected</p>
                        <p className={`text-lg font-bold font-mono ${parseFloat(actualCashCount) >= auditData.cash.expected_cash ? 'text-emerald-600' : 'text-red-600'}`}>
                          {parseFloat(actualCashCount) >= auditData.cash.expected_cash ? '+' : ''}{formatPHP(parseFloat(actualCashCount) - auditData.cash.expected_cash)}
                        </p>
                      </div>
                    )}
                  </div>
                  {auditData.cash.expense_breakdown?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">Expense Breakdown ({auditData.cash.expense_breakdown.length} categories)</summary>
                      <div className="mt-2 space-y-0.5">
                        {auditData.cash.expense_breakdown.map(e => (
                          <StatRow key={e.category} label={e.category} value={formatPHP(e.total)} sub={`${e.count} entries`} />
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 3: Sales */}
              <SectionCard title="Sales Audit" icon={<TrendingUp size={16} className="text-blue-600" />}
                sev={auditData.sales?.severity} data_testid="audit-sales-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Sales (period)" value={formatPHP(auditData.sales.grand_total_sales)} highlight="font-bold" />
                  <StatRow label="Total Transactions" value={auditData.sales.total_transactions} />
                  {Object.entries(auditData.sales.by_payment_type || {}).map(([type, v]) => (
                    <StatRow key={type} label={`  → ${type}`} value={formatPHP(v.total)} sub={`${v.count} txns`} />
                  ))}
                  <Separator className="my-2" />
                  <StatRow label="Voided Transactions" value={auditData.sales.voided_count}
                    highlight={auditData.sales.voided_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Edited Invoices" value={auditData.sales.edited_count}
                    highlight={auditData.sales.edited_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  {auditData.sales.edited_invoices?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-amber-700 cursor-pointer">View edited invoices ({auditData.sales.edited_count})</summary>
                      <div className="mt-2 space-y-1">
                        {auditData.sales.edited_invoices.map((e, i) => (
                          <div key={i} className="text-xs p-2 bg-amber-50 rounded">
                            <span className="font-mono">{e.invoice_number}</span>
                            <span className="text-slate-500 ml-2">{e.edited_by_name} · {e.edited_at?.slice(0, 10)}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 4: AR */}
              <SectionCard title="Accounts Receivable" icon={<FileText size={16} className="text-purple-600" />}
                sev={auditData.ar?.severity} data_testid="audit-ar-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Outstanding AR" value={formatPHP(auditData.ar.total_outstanding_ar)} highlight="font-bold" />
                  <StatRow label="Open Invoices" value={auditData.ar.open_invoices_count} />
                  <StatRow label="Collected in Period" value={formatPHP(auditData.ar.collected_in_period)} highlight="text-emerald-600" />
                  <Separator className="my-2" />
                  <p className="text-xs text-slate-500 font-medium">AR Aging Buckets</p>
                  <StatRow label="Current (0–30 days)" value={formatPHP(auditData.ar.aging?.current)} highlight="text-emerald-600" />
                  <StatRow label="31–60 days" value={formatPHP(auditData.ar.aging?.b31_60)} highlight="text-amber-600" />
                  <StatRow label="61–90 days" value={formatPHP(auditData.ar.aging?.b61_90)} highlight="text-orange-600" />
                  <StatRow label="90+ days (Critical)" value={formatPHP(auditData.ar.aging?.b90plus)}
                    highlight={auditData.ar.aging?.b90plus > 0 ? 'text-red-600 font-bold' : 'text-emerald-600'} />
                </div>
              </SectionCard>

              {/* Section 5: Payables */}
              <SectionCard title="Accounts Payable" icon={<Building2 size={16} className="text-orange-600" />}
                sev={auditData.payables?.severity} data_testid="audit-payables-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Outstanding AP" value={formatPHP(auditData.payables.total_outstanding_ap)} highlight="font-bold" />
                  <StatRow label="Unpaid POs" value={auditData.payables.unpaid_po_count} />
                  <StatRow label="Overdue POs" value={auditData.payables.overdue_count}
                    highlight={auditData.payables.overdue_count > 0 ? 'text-red-600 font-bold' : ''} />
                  <StatRow label="Overdue Value" value={formatPHP(auditData.payables.overdue_value)}
                    highlight={auditData.payables.overdue_value > 0 ? 'text-red-600' : ''} />
                </div>
              </SectionCard>

              {/* Section 6: Transfers */}
              <SectionCard title="Branch Transfers" icon={<ArrowRight size={16} className="text-blue-600" />}
                sev={auditData.transfers?.severity} data_testid="audit-transfers-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Transfers (period)" value={auditData.transfers.total_transfers} />
                  <StatRow label="Successfully Received" value={auditData.transfers.received_count} highlight="text-emerald-600" />
                  <StatRow label="With Shortage" value={auditData.transfers.with_shortage}
                    highlight={auditData.transfers.with_shortage > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="With Excess" value={auditData.transfers.with_excess}
                    highlight={auditData.transfers.with_excess > 0 ? 'text-blue-600' : ''} />
                  <StatRow label="Pending (unresolved)" value={auditData.transfers.pending_count}
                    highlight={auditData.transfers.pending_count > 0 ? 'text-amber-600' : ''} />
                  <StatRow label="Pending Stock Requests" value={auditData.transfers.pending_requests}
                    highlight={auditData.transfers.pending_requests > 0 ? 'text-slate-600' : ''} />
                  {auditData.transfers.total_shortage_value > 0 && (
                    <StatRow label="Total Shortage Value" value={formatPHP(auditData.transfers.total_shortage_value)} highlight="text-red-600 font-bold" />
                  )}
                </div>
              </SectionCard>

              {/* Section 7: Returns */}
              <SectionCard title="Returns & Losses" icon={<RotateCcw size={16} className="text-amber-600" />}
                sev={auditData.returns?.severity} data_testid="audit-returns-section">
                <div className="space-y-1 mt-2">
                  <StatRow label="Total Returns (period)" value={auditData.returns.total_returns} />
                  <StatRow label="Total Refunded" value={formatPHP(auditData.returns.total_refunded)} highlight="text-red-600" />
                  <StatRow label="Pull-out (Loss) Count" value={auditData.returns.pullout_count}
                    highlight={auditData.returns.pullout_count > 0 ? 'text-red-600 font-bold' : ''} />
                  <StatRow label="Total Loss Value (Capital)" value={formatPHP(auditData.returns.total_loss_value)}
                    highlight={auditData.returns.total_loss_value > 0 ? 'text-red-600' : ''} />
                  {auditData.returns.top_reasons?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-500 font-medium mb-1">Top Return Reasons</p>
                      {auditData.returns.top_reasons.slice(0, 3).map(r => (
                        <StatRow key={r.reason} label={r.reason} value={`${r.count} returns`} />
                      ))}
                    </div>
                  )}
                </div>
              </SectionCard>

              {/* Section 8: Activity */}
              <SectionCard title="User Activity" icon={<Users size={16} className="text-slate-600" />}
                sev={auditData.activity?.severity} data_testid="audit-activity-section">
                <div className="space-y-1 mt-2">
                  <p className="text-xs text-slate-500 font-medium mb-2">Sales by User</p>
                  {auditData.activity.sales_by_user?.map(u => (
                    <StatRow key={u.user} label={u.user} value={formatPHP(u.total)} sub={`${u.count} transactions`} />
                  ))}
                  <Separator className="my-2" />
                  <StatRow label="Inventory Corrections" value={auditData.activity.inventory_corrections_count}
                    highlight={auditData.activity.inventory_corrections_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Invoice Edits" value={auditData.activity.invoice_edits_count}
                    highlight={auditData.activity.invoice_edits_count > 0 ? 'text-amber-600 font-bold' : ''} />
                  <StatRow label="Off-hours Transactions" value={auditData.activity.off_hours_count}
                    highlight={auditData.activity.off_hours_count > 0 ? 'text-red-600 font-bold' : ''}
                    sub="Before 7am or after 10pm" />
                  {auditData.activity.off_hours_transactions?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-red-700 cursor-pointer">View off-hours transactions</summary>
                      <div className="mt-2 space-y-1">
                        {auditData.activity.off_hours_transactions.map((t, i) => (
                          <div key={i} className="text-xs p-2 bg-red-50 rounded flex justify-between">
                            <span><span className="font-mono">{t.invoice_number}</span> · {t.cashier_name}</span>
                            <span>{formatPHP(t.grand_total)} · {t.created_at?.slice(11, 16)}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </SectionCard>

              {/* Section 1: Inventory (full audit only) */}
              {auditData.inventory?.available && (
                <SectionCard title={`Inventory Physical Count (${auditData.inventory.baseline_date} → ${auditData.inventory.current_date})`}
                  icon={<Package size={16} className="text-[#1A4D2E]" />}
                  sev={auditData.inventory.severity} data_testid="audit-inventory-section">
                  <div className="space-y-2 mt-2">
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold text-emerald-600">{auditData.inventory.summary.inventory_accuracy_pct}%</p>
                        <p className="text-xs text-slate-500">Accuracy</p>
                      </div>
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold text-red-600">{auditData.inventory.summary.items_critical}</p>
                        <p className="text-xs text-slate-500">Critical Items</p>
                      </div>
                      <div className="text-center p-2 rounded bg-slate-50 border">
                        <p className="text-2xl font-bold font-mono">{formatPHP(auditData.inventory.summary.total_variance_capital)}</p>
                        <p className="text-xs text-slate-500">Variance Value</p>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 font-medium mb-1">Formula: Baseline Count + All Movements = Expected · Physical Count − Expected = Variance</p>
                    <div className="max-h-64 overflow-y-auto">
                      <table className="w-full text-xs border-collapse">
                        <thead className="sticky top-0 bg-white">
                          <tr className="border-b">
                            <th className="text-left px-2 py-1.5 text-slate-500 uppercase">Product</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Baseline</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">+Movements</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Expected</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Physical</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">Variance</th>
                            <th className="text-right px-2 py-1.5 text-slate-500 uppercase">₱ Impact</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditData.inventory.items?.filter(i => i.severity !== 'ok').map((item, idx) => (
                            <tr key={idx} className={`border-b ${item.severity === 'critical' ? 'bg-red-50' : item.severity === 'warning' ? 'bg-amber-50' : ''}`}>
                              <td className="px-2 py-1.5">
                                <p className="font-medium">{item.product_name}</p>
                                <p className="text-slate-400">{item.sku}</p>
                              </td>
                              <td className="px-2 py-1.5 text-right font-mono">{item.baseline_qty}</td>
                              <td className="px-2 py-1.5 text-right font-mono text-blue-600">{item.net_movement >= 0 ? '+' : ''}{item.net_movement}</td>
                              <td className="px-2 py-1.5 text-right font-mono">{item.expected_qty}</td>
                              <td className="px-2 py-1.5 text-right font-mono font-bold">{item.physical_count}</td>
                              <td className={`px-2 py-1.5 text-right font-mono font-bold ${item.variance < 0 ? 'text-red-600' : item.variance > 0 ? 'text-blue-600' : 'text-emerald-600'}`}>
                                {item.variance >= 0 ? '+' : ''}{item.variance}
                              </td>
                              <td className={`px-2 py-1.5 text-right font-mono ${item.variance_value_capital < 0 ? 'text-red-600' : 'text-blue-600'}`}>
                                {item.variance_value_capital >= 0 ? '+' : ''}{formatPHP(item.variance_value_capital)}
                              </td>
                            </tr>
                          ))}
                          {!auditData.inventory.items?.filter(i => i.severity !== 'ok').length && (
                            <tr><td colSpan={7} className="text-center py-4 text-emerald-600">All products within acceptable variance. Inventory accuracy is high.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </SectionCard>
              )}

              {auditData.inventory && !auditData.inventory.available && (
                <Card className="border-slate-200 bg-slate-50">
                  <CardContent className="p-4 text-center text-slate-500">
                    <Package size={24} className="mx-auto mb-2 opacity-40" />
                    <p className="text-sm">{auditData.inventory.message}</p>
                    {auditType === 'partial' && <p className="text-xs mt-1">Switch to Full Audit to include inventory comparison.</p>}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* ── HISTORY TAB ──────────────────────────────────────────────── */}
        <TabsContent value="history" className="mt-4 space-y-3">
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={loadHistory} disabled={loadingHistory}>
              <RefreshCw size={12} className={`mr-1.5 ${loadingHistory ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>
          {sessions.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <History size={32} className="mx-auto mb-2 opacity-40" />
              <p>No audits found. Run your first audit!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map(session => {
                const score = session.overall_score;
                const color = !score ? 'text-slate-400' : score >= 80 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-red-600';
                const sectionStatuses = Object.values(session.sections_status || {});
                const criticals = sectionStatuses.filter(s => s === 'critical').length;
                const warnings = sectionStatuses.filter(s => s === 'warning').length;
                return (
                  <Card key={session.id} className="border-slate-200 hover:border-slate-300 transition-colors">
                    <CardContent className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="text-center w-14">
                          <p className={`text-2xl font-bold font-mono ${color}`}>{score || '—'}</p>
                          <p className="text-[9px] text-slate-400">Score</p>
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-0.5">
                            <Badge className={`text-[10px] ${session.audit_type === 'full' ? 'bg-[#1A4D2E] text-white' : 'bg-blue-100 text-blue-700'}`}>
                              {session.audit_type === 'full' ? 'Full Audit' : 'Partial'}
                            </Badge>
                            <Badge className={`text-[10px] ${session.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                              {session.status}
                            </Badge>
                          </div>
                          <p className="font-semibold text-sm">{session.branch_name}</p>
                          <p className="text-xs text-slate-500">{session.period_from} → {session.period_to}</p>
                          <p className="text-xs text-slate-400">{session.created_by_name} · {session.created_at?.slice(0, 10)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {criticals > 0 && <Badge className="bg-red-100 text-red-700 text-[10px]">{criticals} critical</Badge>}
                        {warnings > 0 && <Badge className="bg-amber-100 text-amber-700 text-[10px]">{warnings} warnings</Badge>}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
