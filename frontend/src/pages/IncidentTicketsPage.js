import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  AlertTriangle, CheckCircle2, Clock, Search, MessageSquare, UserCheck,
  XCircle, FileText, ArrowRight, Eye, RefreshCw, ArrowLeftRight, Check
} from 'lucide-react';
import { toast } from 'sonner';
import TransferDetailModal from '../components/TransferDetailModal';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_COLORS = {
  open: 'bg-red-100 text-red-700',
  investigating: 'bg-amber-100 text-amber-700',
  resolved: 'bg-emerald-100 text-emerald-700',
  closed: 'bg-slate-100 text-slate-600',
};

const PRIORITY_COLORS = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-slate-100 text-slate-600',
};

export default function IncidentTicketsPage() {
  const { user, users, branches } = useAuth();

  // ── Main view: "tickets" or "variances" ───────────────────────────────
  const [mainTab, setMainTab] = useState('tickets');

  // ── Tickets state ─────────────────────────────────────────────────────
  const [tickets, setTickets] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('open');
  const [search, setSearch] = useState('');
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [resolveDialog, setResolveDialog] = useState(null);
  const [resolveNote, setResolveNote] = useState('');
  const [recoveryAmount, setRecoveryAmount] = useState(0);
  const [assignDialog, setAssignDialog] = useState(null);
  const [assignUserId, setAssignUserId] = useState('');
  const [teamMembers, setTeamMembers] = useState([]);

  // ── Transfer Variances state ──────────────────────────────────────────
  const [varianceData, setVarianceData] = useState(null);
  const [varianceLoading, setVarianceLoading] = useState(false);
  const [varianceViewTransfer, setVarianceViewTransfer] = useState(null);
  const [varianceViewLoading, setVarianceViewLoading] = useState(null);

  // ── Fetch tickets ─────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const statusFilter = tab === 'all' ? '' : tab;
      const [ticketsRes, summaryRes] = await Promise.all([
        api.get('/incident-tickets', { params: { status: statusFilter || undefined, limit: 100 } }),
        api.get('/incident-tickets/summary'),
      ]);
      setTickets(ticketsRes.data.tickets || []);
      setSummary(summaryRes.data || {});
    } catch { toast.error('Failed to load tickets'); }
    setLoading(false);
  }, [tab]);

  useEffect(() => { if (mainTab === 'tickets') fetchData(); }, [fetchData, mainTab]);

  // ── Fetch variances ───────────────────────────────────────────────────
  const loadVariances = useCallback(async () => {
    setVarianceLoading(true);
    try {
      const res = await api.get(`${BACKEND_URL}/api/audit/transfer-variances`);
      setVarianceData(res.data);
    } catch { setVarianceData(null); }
    setVarianceLoading(false);
  }, []);

  // Load variance summary on mount for the header cards, full data on tab switch
  useEffect(() => { loadVariances(); }, [loadVariances]);
  useEffect(() => { if (mainTab === 'variances') loadVariances(); }, [mainTab, loadVariances]);

  const openVarianceDetail = async (transferId) => {
    setVarianceViewLoading(transferId);
    try {
      const res = await api.get(`${BACKEND_URL}/api/branch-transfers/${transferId}`);
      setVarianceViewTransfer(res.data);
    } catch { toast.error('Failed to load transfer details'); }
    setVarianceViewLoading(null);
  };

  // ── Ticket actions ────────────────────────────────────────────────────
  const fetchTeam = async () => {
    try {
      const res = await api.get('/users');
      setTeamMembers(res.data || []);
    } catch { setTeamMembers([]); }
  };

  const handleAddNote = async () => {
    if (!selectedTicket || !noteText.trim()) return;
    setActionLoading(true);
    try {
      await api.put(`/incident-tickets/${selectedTicket.id}/add-note`, { note: noteText });
      toast.success('Note added');
      setNoteText('');
      const res = await api.get(`/incident-tickets/${selectedTicket.id}`);
      setSelectedTicket(res.data);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setActionLoading(false);
  };

  const handleAssign = async () => {
    if (!assignDialog || !assignUserId) return;
    const member = teamMembers.find(m => m.id === assignUserId);
    setActionLoading(true);
    try {
      await api.put(`/incident-tickets/${assignDialog.id}/assign`, {
        assigned_to_id: assignUserId,
        assigned_to_name: member?.full_name || member?.username || '',
      });
      toast.success('Ticket assigned');
      setAssignDialog(null);
      const res = await api.get(`/incident-tickets/${assignDialog.id}`);
      setSelectedTicket(res.data);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setActionLoading(false);
  };

  const handleResolve = async () => {
    if (!resolveDialog || !resolveNote.trim()) { toast.error('Resolution note required'); return; }
    setActionLoading(true);
    try {
      await api.put(`/incident-tickets/${resolveDialog.id}/resolve`, {
        resolution_note: resolveNote, recovery_amount: recoveryAmount,
      });
      toast.success('Ticket resolved');
      setResolveDialog(null);
      setSelectedTicket(null);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setActionLoading(false);
  };

  const handleClose = async (ticketId) => {
    setActionLoading(true);
    try {
      await api.put(`/incident-tickets/${ticketId}/close`, { note: 'Closed by admin' });
      toast.success('Ticket closed');
      setSelectedTicket(null);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setActionLoading(false);
  };

  const filtered = search
    ? tickets.filter(t => t.ticket_number?.toLowerCase().includes(search.toLowerCase()) ||
        t.order_number?.toLowerCase().includes(search.toLowerCase()) ||
        t.from_branch_name?.toLowerCase().includes(search.toLowerCase()))
    : tickets;

  const fmtDate = (d) => d ? new Date(d).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

  // ── Combined summary for header ───────────────────────────────────────
  const totalVariances = varianceData?.summary?.total_variance_transfers || 0;
  const totalCapLoss = varianceData?.summary?.total_capital_loss || 0;
  const openTickets = (summary.open || 0) + (summary.investigating || 0);
  const unresolvedLoss = summary.total_unresolved_capital_loss || 0;

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="incident-tickets-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
          <AlertTriangle size={22} className="text-amber-600" /> Incident Tickets & Transfer Variances
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">Track, investigate, and resolve transfer discrepancies and losses</p>
      </div>

      {/* ── Combined Summary Cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="border border-amber-200 bg-amber-50/30">
          <CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">Total Variances</p>
            <p className="text-xl font-bold text-amber-700" style={{ fontFamily: 'Manrope' }}>{totalVariances}</p>
            <p className="text-[10px] text-slate-400">transfers with discrepancies</p>
          </CardContent>
        </Card>
        <Card className="border border-red-200 bg-red-50/30">
          <CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">Capital Loss</p>
            <p className="text-xl font-bold text-red-700" style={{ fontFamily: 'Manrope' }}>{formatPHP(totalCapLoss)}</p>
            <p className="text-[10px] text-slate-400">total from variances</p>
          </CardContent>
        </Card>
        <Card className={`border ${openTickets > 0 ? 'border-red-200 bg-red-50/30' : 'border-emerald-200 bg-emerald-50/30'}`}>
          <CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">Active Tickets</p>
            <p className={`text-xl font-bold ${openTickets > 0 ? 'text-red-600' : 'text-emerald-600'}`} style={{ fontFamily: 'Manrope' }}>{openTickets}</p>
            <p className="text-[10px] text-slate-400">open + investigating</p>
          </CardContent>
        </Card>
        <Card className="border border-emerald-200 bg-emerald-50/30">
          <CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">Resolved</p>
            <p className="text-xl font-bold text-emerald-600" style={{ fontFamily: 'Manrope' }}>{(summary.resolved || 0) + (summary.closed || 0)}</p>
            <p className="text-[10px] text-slate-400">resolved + closed</p>
          </CardContent>
        </Card>
        <Card className={`border ${unresolvedLoss > 0 ? 'border-red-200 bg-red-50/30' : 'border-slate-200'}`}>
          <CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">Unresolved Loss</p>
            <p className={`text-xl font-bold ${unresolvedLoss > 0 ? 'text-red-700' : 'text-slate-400'}`} style={{ fontFamily: 'Manrope' }}>{formatPHP(unresolvedLoss)}</p>
            <p className="text-[10px] text-slate-400">capital at risk</p>
          </CardContent>
        </Card>
      </div>

      {/* ── Main Tabs: Tickets vs All Variances ── */}
      <Tabs value={mainTab} onValueChange={setMainTab}>
        <TabsList className="h-10">
          <TabsTrigger value="tickets" data-testid="tickets-main-tab" className="gap-1.5">
            <FileText size={14} /> Incident Tickets
            {openTickets > 0 && (
              <span className="ml-1 bg-red-500 text-white text-[10px] rounded-full px-1.5 py-0.5 font-bold">{openTickets}</span>
            )}
          </TabsTrigger>
          <TabsTrigger value="variances" data-testid="variances-main-tab" className="gap-1.5">
            <ArrowLeftRight size={14} /> All Transfer Variances
            {totalVariances > 0 && (
              <span className="ml-1 bg-amber-500 text-white text-[10px] rounded-full px-1.5 py-0.5 font-bold">{totalVariances}</span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ══════════════════════════════════════════════════════════════════
            TICKETS TAB
           ══════════════════════════════════════════════════════════════════ */}
        <TabsContent value="tickets" className="mt-4 space-y-4">
          {/* Status Tabs + Search */}
          <div className="flex items-center gap-3">
            <Tabs value={tab} onValueChange={setTab} className="flex-1">
              <TabsList className="h-9 bg-slate-100">
                <TabsTrigger value="open" className="text-xs">Open</TabsTrigger>
                <TabsTrigger value="investigating" className="text-xs">Investigating</TabsTrigger>
                <TabsTrigger value="resolved" className="text-xs">Resolved</TabsTrigger>
                <TabsTrigger value="closed" className="text-xs">Closed</TabsTrigger>
                <TabsTrigger value="all" className="text-xs">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="relative w-48">
              <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="pl-8 h-9 text-xs" />
            </div>
          </div>

          {/* Tickets Table */}
          <Card className="border-slate-200">
            <CardContent className="p-0">
              <Table>
                <TableHeader><TableRow className="bg-slate-50">
                  <TableHead className="text-xs uppercase text-slate-500">Ticket</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Transfer</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Route</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500 text-right">Capital Loss</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Priority</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Status</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Assigned</TableHead>
                  <TableHead className="text-xs uppercase text-slate-500">Date</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">Loading...</TableCell></TableRow>
                  ) : filtered.length === 0 ? (
                    <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">
                      {tab === 'open' ? 'No open incidents' : 'No tickets found'}
                    </TableCell></TableRow>
                  ) : filtered.map(t => (
                    <TableRow key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelectedTicket(t)}
                      data-testid={`ticket-row-${t.id}`}>
                      <TableCell className="font-mono text-xs font-bold text-blue-600">{t.ticket_number}</TableCell>
                      <TableCell>
                        <button className="font-mono text-xs text-blue-600 hover:underline"
                          onClick={(e) => { e.stopPropagation(); openVarianceDetail(t.transfer_id); }}>
                          {t.order_number}
                        </button>
                      </TableCell>
                      <TableCell className="text-xs">{t.from_branch_name} &rarr; {t.to_branch_name}</TableCell>
                      <TableCell className="text-right font-mono font-bold text-red-600">{formatPHP(t.total_capital_loss)}</TableCell>
                      <TableCell><Badge className={`text-[10px] ${PRIORITY_COLORS[t.priority]}`}>{t.priority}</Badge></TableCell>
                      <TableCell><Badge className={`text-[10px] ${STATUS_COLORS[t.status]}`}>{t.status}</Badge></TableCell>
                      <TableCell className="text-xs text-slate-500">{t.assigned_to_name || '\u2014'}</TableCell>
                      <TableCell className="text-xs text-slate-400">{fmtDate(t.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ══════════════════════════════════════════════════════════════════
            ALL VARIANCES TAB
           ══════════════════════════════════════════════════════════════════ */}
        <TabsContent value="variances" className="mt-4 space-y-4">
          {varianceLoading ? (
            <div className="text-center py-16 text-slate-400">
              <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
              Loading transfer variance data...
            </div>
          ) : !varianceData ? (
            <Card className="border-slate-200">
              <CardContent className="p-8 text-center text-slate-400">
                <ArrowLeftRight size={36} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">No transfer variance data available.</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-slate-200">
              <CardContent className="p-0">
                <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <AlertTriangle size={14} className="text-amber-600" />
                    All Transfer Variances
                    <span className="text-xs font-normal text-slate-400">
                      ({varianceData.items.length} transfers with discrepancies)
                    </span>
                  </h3>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={loadVariances}>
                    <RefreshCw size={12} className="mr-1" /> Refresh
                  </Button>
                </div>
                {varianceData.items.length === 0 ? (
                  <div className="text-center py-12 text-slate-400">
                    <Check size={24} className="mx-auto mb-2 text-emerald-400" />
                    <p className="text-sm">No transfer variances found. All transfers matched perfectly.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {varianceData.items.map((item) => (
                      <div key={item.transfer_id} className="px-4 py-3 hover:bg-slate-50 transition-colors" data-testid={`variance-row-${item.transfer_id}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-sm font-bold text-slate-700">{item.order_number}</span>
                              {item.incident_ticket_number ? (
                                <button
                                  className="inline-flex items-center gap-1 text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium hover:bg-amber-200 transition-colors"
                                  onClick={() => {
                                    setMainTab('tickets');
                                    setTab('all');
                                    setSearch(item.incident_ticket_number);
                                  }}
                                  data-testid={`variance-ticket-${item.transfer_id}`}>
                                  <AlertTriangle size={9} /> {item.incident_ticket_number}
                                </button>
                              ) : (
                                <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">No ticket</span>
                              )}
                              {item.capital_loss > 0 && (
                                <span className="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                                  Loss: {item.capital_loss.toLocaleString('en-PH', { style: 'currency', currency: 'PHP' })}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-500 mt-1">
                              {item.from_branch_name} <ArrowRight size={10} className="inline text-slate-400" /> {item.to_branch_name}
                            </p>
                            {item.dispute_note && (
                              <p className="text-[10px] text-slate-400 mt-0.5 italic">&quot;{item.dispute_note}&quot;</p>
                            )}
                          </div>
                          <div className="text-right shrink-0 ml-4">
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              {item.shortages_count > 0 && <span className="text-amber-600 font-medium">{item.shortages_count} shortage(s)</span>}
                              {item.excesses_count > 0 && <span className="text-blue-600 font-medium">{item.excesses_count} excess(es)</span>}
                            </div>
                            <p className="text-[10px] text-slate-400 mt-0.5">{item.accepted_at?.slice(0, 10)}</p>
                            {item.accepted_by_name && <p className="text-[10px] text-slate-400">by {item.accepted_by_name}</p>}
                            <Button size="sm" variant="outline" className="h-7 text-xs mt-1.5"
                              onClick={() => openVarianceDetail(item.transfer_id)} data-testid={`view-variance-${item.transfer_id}`}
                              disabled={varianceViewLoading === item.transfer_id}>
                              {varianceViewLoading === item.transfer_id
                                ? <RefreshCw size={12} className="mr-1 animate-spin" />
                                : <Eye size={12} className="mr-1" />
                              } View
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* ══════════════════════════════════════════════════════════════════
          DIALOGS
         ══════════════════════════════════════════════════════════════════ */}

      {/* Ticket Detail Dialog */}
      <Dialog open={!!selectedTicket} onOpenChange={() => setSelectedTicket(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedTicket && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
                  <FileText size={18} />
                  {selectedTicket.ticket_number}
                  <Badge className={`text-[10px] ${STATUS_COLORS[selectedTicket.status]}`}>{selectedTicket.status}</Badge>
                  <Badge className={`text-[10px] ${PRIORITY_COLORS[selectedTicket.priority]}`}>{selectedTicket.priority}</Badge>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                {/* Header info */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-slate-500">Transfer:</span>{' '}
                    <button className="font-mono font-bold text-blue-600 hover:underline cursor-pointer" data-testid="ticket-transfer-link"
                      onClick={() => { setSelectedTicket(null); openVarianceDetail(selectedTicket.transfer_id); }}>
                      {selectedTicket.order_number}
                    </button>
                  </div>
                  <div><span className="text-slate-500">Route:</span> {selectedTicket.from_branch_name} &rarr; {selectedTicket.to_branch_name}</div>
                  <div><span className="text-slate-500">Capital Loss:</span> <span className="font-bold text-red-600">{formatPHP(selectedTicket.total_capital_loss)}</span></div>
                  <div><span className="text-slate-500">Retail Loss:</span> <span className="font-bold text-red-600">{formatPHP(selectedTicket.total_retail_loss)}</span></div>
                  {selectedTicket.assigned_to_name && <div><span className="text-slate-500">Assigned:</span> {selectedTicket.assigned_to_name}</div>}
                  {selectedTicket.recovery_amount > 0 && <div><span className="text-slate-500">Recovered:</span> <span className="text-emerald-600 font-bold">{formatPHP(selectedTicket.recovery_amount)}</span></div>}
                </div>

                {/* Variance Items */}
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Product</th>
                        <th className="text-right px-3 py-2 font-medium">Sent</th>
                        <th className="text-right px-3 py-2 font-medium">Received</th>
                        <th className="text-right px-3 py-2 font-medium">Variance</th>
                        <th className="text-right px-3 py-2 font-medium">Loss</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {(selectedTicket.items || []).map((item, i) => (
                        <tr key={i} className={item.type === 'shortage' ? 'bg-red-50/40' : 'bg-blue-50/40'}>
                          <td className="px-3 py-2 font-medium">{item.product_name} <span className="text-slate-400 text-[10px]">{item.sku}</span></td>
                          <td className="px-3 py-2 text-right font-mono">{item.qty_ordered}</td>
                          <td className="px-3 py-2 text-right font-mono font-bold">{item.qty_received}</td>
                          <td className={`px-3 py-2 text-right font-mono font-bold ${item.type === 'shortage' ? 'text-red-600' : 'text-blue-600'}`}>
                            {item.type === 'shortage' ? `-${item.variance}` : `+${Math.abs(item.variance)}`}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-red-600">{formatPHP(item.capital_variance)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Timeline */}
                <div>
                  <h3 className="text-sm font-semibold mb-2 flex items-center gap-1"><Clock size={14} /> Timeline</h3>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {(selectedTicket.timeline || []).map((event, i) => (
                      <div key={i} className="flex gap-3 text-xs bg-slate-50 rounded-lg p-2.5">
                        <div className="shrink-0 mt-0.5">
                          {event.action === 'created' && <AlertTriangle size={12} className="text-red-500" />}
                          {event.action === 'assigned' && <UserCheck size={12} className="text-blue-500" />}
                          {event.action === 'note' && <MessageSquare size={12} className="text-slate-500" />}
                          {event.action === 'resolved' && <CheckCircle2 size={12} className="text-emerald-500" />}
                          {event.action === 'closed' && <XCircle size={12} className="text-slate-400" />}
                        </div>
                        <div className="flex-1">
                          <p className="text-slate-700">{event.detail}</p>
                          <p className="text-[10px] text-slate-400 mt-0.5">{event.by_name} &middot; {fmtDate(event.at)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Add Note */}
                {['open', 'investigating'].includes(selectedTicket.status) && (
                  <div className="flex gap-2">
                    <Input value={noteText} onChange={e => setNoteText(e.target.value)}
                      placeholder="Add investigation note..." className="flex-1 h-9 text-sm" data-testid="ticket-note-input" />
                    <Button size="sm" onClick={handleAddNote} disabled={actionLoading || !noteText.trim()}
                      className="bg-[#1A4D2E] text-white" data-testid="add-note-btn">
                      <MessageSquare size={12} className="mr-1" /> Add Note
                    </Button>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 flex-wrap pt-2 border-t">
                  {['open', 'investigating'].includes(selectedTicket.status) && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => { setAssignDialog(selectedTicket); fetchTeam(); setAssignUserId(''); }}
                        className="text-xs" data-testid="assign-btn">
                        <UserCheck size={12} className="mr-1" /> Assign
                      </Button>
                      <Button size="sm" onClick={() => { setResolveDialog(selectedTicket); setResolveNote(''); setRecoveryAmount(0); }}
                        className="text-xs bg-emerald-600 text-white" data-testid="resolve-btn">
                        <CheckCircle2 size={12} className="mr-1" /> Resolve
                      </Button>
                    </>
                  )}
                  {selectedTicket.status === 'resolved' && user?.role === 'admin' && (
                    <Button size="sm" variant="outline" onClick={() => handleClose(selectedTicket.id)}
                      disabled={actionLoading} className="text-xs" data-testid="close-btn">
                      <XCircle size={12} className="mr-1" /> Close Ticket
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Assign Dialog */}
      <Dialog open={!!assignDialog} onOpenChange={() => setAssignDialog(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Assign Investigator</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Select value={assignUserId} onValueChange={setAssignUserId}>
              <SelectTrigger data-testid="assign-user-select"><SelectValue placeholder="Select team member..." /></SelectTrigger>
              <SelectContent>
                {teamMembers.filter(m => m.active !== false).map(m => (
                  <SelectItem key={m.id} value={m.id}>{m.full_name || m.username} ({m.role})</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAssignDialog(null)}>Cancel</Button>
              <Button onClick={handleAssign} disabled={!assignUserId || actionLoading}
                className="bg-[#1A4D2E] text-white" data-testid="confirm-assign-btn">Assign</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Resolve Dialog */}
      <Dialog open={!!resolveDialog} onOpenChange={() => setResolveDialog(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Resolve Incident</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Resolution Note *</label>
              <textarea value={resolveNote} onChange={e => setResolveNote(e.target.value)}
                placeholder="e.g. Driver compensated for shortage, packaging damage claimed from supplier..."
                rows={3} className="w-full text-sm border border-slate-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-300 resize-none"
                data-testid="resolve-note-input" />
            </div>
            <div>
              <label className="text-xs text-slate-500 font-medium block mb-1">Recovery Amount (optional)</label>
              <Input type="number" value={recoveryAmount} onChange={e => setRecoveryAmount(parseFloat(e.target.value) || 0)}
                placeholder="0.00" className="h-9" data-testid="recovery-amount-input" />
              <p className="text-[10px] text-slate-400 mt-1">Amount recovered from driver/supplier/insurance</p>
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => setResolveDialog(null)}>Cancel</Button>
              <Button onClick={handleResolve} disabled={!resolveNote.trim() || actionLoading}
                className="bg-emerald-600 text-white" data-testid="confirm-resolve-btn">
                <CheckCircle2 size={12} className="mr-1" /> Resolve
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Transfer Detail Modal (shared read-only view) */}
      <TransferDetailModal
        transfer={varianceViewTransfer}
        open={!!varianceViewTransfer}
        onOpenChange={(open) => { if (!open) setVarianceViewTransfer(null); }}
        branches={branches || []}
      />
    </div>
  );
}
