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
import { AlertTriangle, CheckCircle2, Clock, Search, MessageSquare, UserCheck, XCircle, FileText } from 'lucide-react';
import { toast } from 'sonner';

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
  const { user, users } = useAuth();
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

  useEffect(() => { fetchData(); }, [fetchData]);

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

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="incident-tickets-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Incident Tickets</h1>
        <p className="text-sm text-slate-500">Investigate and resolve transfer variances and losses</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Open', count: summary.open || 0, color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
          { label: 'Investigating', count: summary.investigating || 0, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
          { label: 'Resolved', count: summary.resolved || 0, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
          { label: 'Closed', count: summary.closed || 0, color: 'text-slate-500', bg: 'bg-slate-50 border-slate-200' },
          { label: 'Unresolved Loss', count: null, color: 'text-red-700', bg: 'bg-red-50 border-red-200',
            value: formatPHP(summary.total_unresolved_capital_loss || 0) },
        ].map(s => (
          <Card key={s.label} className={`border ${s.bg}`}><CardContent className="p-3">
            <p className="text-[10px] uppercase font-medium text-slate-500">{s.label}</p>
            <p className={`text-xl font-bold ${s.color}`} style={{ fontFamily: 'Manrope' }}>
              {s.value ?? s.count}
            </p>
          </CardContent></Card>
        ))}
      </div>

      {/* Tabs + Search */}
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
                    <a href="/branch-transfers" className="font-mono text-xs text-blue-600 hover:underline">{t.order_number}</a>
                  </TableCell>
                  <TableCell className="text-xs">{t.from_branch_name} → {t.to_branch_name}</TableCell>
                  <TableCell className="text-right font-mono font-bold text-red-600">{formatPHP(t.total_capital_loss)}</TableCell>
                  <TableCell><Badge className={`text-[10px] ${PRIORITY_COLORS[t.priority]}`}>{t.priority}</Badge></TableCell>
                  <TableCell><Badge className={`text-[10px] ${STATUS_COLORS[t.status]}`}>{t.status}</Badge></TableCell>
                  <TableCell className="text-xs text-slate-500">{t.assigned_to_name || '—'}</TableCell>
                  <TableCell className="text-xs text-slate-400">{fmtDate(t.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

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
                    <a href="/branch-transfers" className="font-mono font-bold text-blue-600 hover:underline cursor-pointer" data-testid="ticket-transfer-link">
                      {selectedTicket.order_number}
                    </a>
                  </div>
                  <div><span className="text-slate-500">Route:</span> {selectedTicket.from_branch_name} → {selectedTicket.to_branch_name}</div>
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
                          <p className="text-[10px] text-slate-400 mt-0.5">{event.by_name} · {fmtDate(event.at)}</p>
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
    </div>
  );
}
