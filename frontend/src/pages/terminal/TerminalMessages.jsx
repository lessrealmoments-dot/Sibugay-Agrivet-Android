import { useState, useEffect, useCallback } from 'react';
import {
  MessageSquare, Send, Clock, AlertTriangle, SkipForward,
  RefreshCw, ChevronDown, ChevronUp, Users, Filter,
  Edit3, Check, X, Search, Megaphone, Loader2
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';

const STATUS_TABS = [
  { key: 'pending', label: 'Pending', icon: Clock, color: 'text-amber-600' },
  { key: 'sent', label: 'Sent', icon: Check, color: 'text-emerald-600' },
  { key: 'failed', label: 'Failed', icon: AlertTriangle, color: 'text-red-600' },
];

export default function TerminalMessages({ api, session }) {
  const [view, setView] = useState('queue'); // queue | compose | blast | templates
  const [statusTab, setStatusTab] = useState('pending');
  const [queue, setQueue] = useState([]);
  const [queueTotal, setQueueTotal] = useState(0);
  const [stats, setStats] = useState({ pending: 0, sent: 0, failed: 0, skipped: 0 });
  const [loading, setLoading] = useState(false);

  // Compose state
  const [customers, setCustomers] = useState([]);
  const [custSearch, setCustSearch] = useState('');
  const [selectedCust, setSelectedCust] = useState(null);
  const [composeMsg, setComposeMsg] = useState('');

  // Blast state
  const [blastMsg, setBlastMsg] = useState('');
  const [blastFilter, setBlastFilter] = useState({ min_balance: '' });
  const [blasting, setBlasting] = useState(false);

  // Templates state
  const [templates, setTemplates] = useState([]);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editBody, setEditBody] = useState('');

  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/sms/queue', { params: { status: statusTab, limit: 50 } });
      setQueue(res.data.items || []);
      setQueueTotal(res.data.total || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [api, statusTab]);

  const loadStats = useCallback(async () => {
    try {
      const res = await api.get('/sms/stats');
      setStats(res.data);
    } catch { /* ignore */ }
  }, [api]);

  useEffect(() => { loadQueue(); loadStats(); }, [loadQueue, loadStats]);

  const loadCustomers = async (search) => {
    try {
      const res = await api.get('/customers', { params: { search, limit: 20 } });
      setCustomers(res.data.customers || []);
    } catch { setCustomers([]); }
  };

  const loadTemplates = async () => {
    try {
      const res = await api.get('/sms/templates');
      setTemplates(res.data || []);
    } catch { toast.error('Failed to load templates'); }
  };

  // Actions
  const markSent = async (id) => {
    try {
      await api.patch(`/sms/queue/${id}/mark-sent`);
      toast.success('Marked as sent');
      loadQueue(); loadStats();
    } catch { toast.error('Failed'); }
  };

  const retrySms = async (id) => {
    try {
      await api.post(`/sms/queue/${id}/retry`);
      toast.success('Re-queued');
      loadQueue(); loadStats();
    } catch { toast.error('Failed'); }
  };

  const skipSms = async (id) => {
    try {
      await api.post(`/sms/queue/${id}/skip`);
      toast('Skipped');
      loadQueue(); loadStats();
    } catch { toast.error('Failed'); }
  };

  const openSmsApp = (phone, message) => {
    const encoded = encodeURIComponent(message);
    window.open(`sms:${phone}?body=${encoded}`, '_self');
  };

  const handleComposeSend = async () => {
    if (!selectedCust || !composeMsg.trim()) return;
    try {
      await api.post('/sms/send', {
        customer_id: selectedCust.id,
        customer_name: selectedCust.name,
        phone: selectedCust.phone,
        message: composeMsg,
        branch_id: session.branchId,
        branch_name: session.branchName,
      });
      toast.success('Message queued');
      setComposeMsg('');
      setSelectedCust(null);
      setCustSearch('');
      setView('queue');
      loadQueue(); loadStats();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to queue'); }
  };

  const handleBlast = async () => {
    if (!blastMsg.trim()) return;
    setBlasting(true);
    try {
      const payload = {
        message: blastMsg,
        branch_id: session.branchId,
        branch_name: session.branchName,
        filter: {},
      };
      if (blastFilter.min_balance) payload.filter.min_balance = parseFloat(blastFilter.min_balance);
      if (session.branchId) payload.filter.branch_id = session.branchId;
      const res = await api.post('/sms/blast', payload);
      toast.success(`${res.data.queued} messages queued (${res.data.skipped_no_phone} skipped — no phone)`);
      setBlastMsg('');
      setBlastFilter({ min_balance: '' });
      setView('queue');
      loadQueue(); loadStats();
    } catch (e) { toast.error(e.response?.data?.detail || 'Blast failed'); }
    setBlasting(false);
  };

  const saveTemplate = async () => {
    if (!editingTemplate) return;
    try {
      await api.put(`/sms/templates/${editingTemplate.id}`, { body: editBody });
      toast.success('Template updated');
      setEditingTemplate(null);
      loadTemplates();
    } catch { toast.error('Failed to save'); }
  };

  const toggleTemplate = async (t) => {
    try {
      await api.put(`/sms/templates/${t.id}`, { active: !t.active });
      toast.success(`${t.name} ${t.active ? 'disabled' : 'enabled'}`);
      loadTemplates();
    } catch { toast.error('Failed'); }
  };

  const fmtTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full bg-[#F5F5F0]" data-testid="terminal-messages">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <MessageSquare size={18} className="text-[#1A4D2E]" />
          <h2 className="text-base font-bold" style={{ fontFamily: 'Manrope' }}>Messages</h2>
          {stats.pending > 0 && (
            <Badge className="text-[10px] bg-amber-100 text-amber-700">{stats.pending} pending</Badge>
          )}
        </div>
        <div className="flex gap-1.5">
          <button onClick={() => setView('queue')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${view === 'queue' ? 'bg-[#1A4D2E] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            data-testid="view-queue-btn">
            Queue
          </button>
          <button onClick={() => { setView('compose'); loadCustomers(''); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${view === 'compose' ? 'bg-[#1A4D2E] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            data-testid="view-compose-btn">
            Compose
          </button>
          <button onClick={() => { setView('blast'); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${view === 'blast' ? 'bg-[#1A4D2E] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            data-testid="view-blast-btn">
            Blast
          </button>
          <button onClick={() => { setView('templates'); loadTemplates(); }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${view === 'templates' ? 'bg-[#1A4D2E] text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            data-testid="view-templates-btn">
            Templates
          </button>
        </div>
      </div>

      {/* ═══ QUEUE VIEW ═══ */}
      {view === 'queue' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Status tabs */}
          <div className="flex items-center gap-2 px-4 py-2 bg-white border-b border-slate-100 shrink-0">
            {STATUS_TABS.map(t => {
              const Icon = t.icon;
              const count = stats[t.key] || 0;
              return (
                <button key={t.key} onClick={() => setStatusTab(t.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    statusTab === t.key ? 'bg-slate-800 text-white' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid={`status-tab-${t.key}`}>
                  <Icon size={12} /> {t.label}
                  {count > 0 && <span className="ml-1 text-[10px] opacity-70">({count})</span>}
                </button>
              );
            })}
            <div className="flex-1" />
            <button onClick={() => { loadQueue(); loadStats(); }} className="text-slate-400 hover:text-slate-600">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>

          {/* Queue list */}
          <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
            {queue.length === 0 && (
              <div className="text-center text-slate-400 text-sm py-12">
                No {statusTab} messages
              </div>
            )}
            {queue.map(sms => (
              <div key={sms.id}
                className="bg-white rounded-xl border border-slate-200 p-3 space-y-2"
                data-testid={`sms-item-${sms.id}`}>
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800 truncate">{sms.customer_name || 'Unknown'}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{sms.phone}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{sms.message}</p>
                  </div>
                  <div className="text-right shrink-0 ml-2">
                    <Badge className={`text-[9px] ${
                      sms.template_key === 'custom' ? 'bg-slate-100 text-slate-600' :
                      sms.template_key === 'credit_new' ? 'bg-blue-100 text-blue-700' :
                      sms.template_key.startsWith('reminder') ? 'bg-amber-100 text-amber-700' :
                      sms.template_key === 'overdue_notice' ? 'bg-red-100 text-red-700' :
                      sms.template_key === 'payment_received' ? 'bg-emerald-100 text-emerald-700' :
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {sms.template_key.replace(/_/g, ' ')}
                    </Badge>
                    <p className="text-[10px] text-slate-400 mt-0.5">{fmtTime(sms.created_at)}</p>
                  </div>
                </div>

                {/* Actions */}
                {statusTab === 'pending' && (
                  <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                    <Button size="sm" className="h-7 text-[10px] bg-[#1A4D2E] hover:bg-[#14532d] text-white flex-1"
                      onClick={() => openSmsApp(sms.phone, sms.message)}
                      data-testid={`sms-send-${sms.id}`}>
                      <Send size={10} className="mr-1" /> Send via SMS App
                    </Button>
                    <Button size="sm" variant="outline" className="h-7 text-[10px]"
                      onClick={() => markSent(sms.id)}
                      data-testid={`sms-mark-sent-${sms.id}`}>
                      <Check size={10} className="mr-1" /> Mark Sent
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7 text-[10px] text-slate-400"
                      onClick={() => skipSms(sms.id)}>
                      <SkipForward size={10} className="mr-1" /> Skip
                    </Button>
                  </div>
                )}
                {statusTab === 'failed' && (
                  <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
                    {sms.error && <span className="text-[10px] text-red-500 flex-1 truncate">{sms.error}</span>}
                    <Button size="sm" variant="outline" className="h-7 text-[10px] text-amber-600 border-amber-200"
                      onClick={() => retrySms(sms.id)}>
                      <RefreshCw size={10} className="mr-1" /> Retry
                    </Button>
                  </div>
                )}
                {statusTab === 'sent' && sms.sent_at && (
                  <p className="text-[10px] text-emerald-500 pt-1 border-t border-slate-100">
                    Sent {fmtTime(sms.sent_at)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ COMPOSE VIEW ═══ */}
      {view === 'compose' && (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <h3 className="text-sm font-bold text-slate-700">Compose Message</h3>

            {/* Customer search */}
            <div>
              <Label className="text-[10px] text-slate-400 uppercase">To (Customer)</Label>
              {selectedCust ? (
                <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 mt-1">
                  <div>
                    <span className="text-sm font-medium">{selectedCust.name}</span>
                    <span className="text-xs text-slate-400 ml-2">{selectedCust.phone}</span>
                  </div>
                  <button onClick={() => { setSelectedCust(null); setCustSearch(''); }} className="text-slate-400 hover:text-slate-600">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="relative mt-1">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input value={custSearch}
                    onChange={e => { setCustSearch(e.target.value); loadCustomers(e.target.value); }}
                    placeholder="Search customer..."
                    className="pl-8 h-9"
                    data-testid="compose-customer-search" />
                  {custSearch && customers.length > 0 && (
                    <div className="absolute z-10 top-full mt-1 w-full bg-white border rounded-lg shadow-lg max-h-40 overflow-y-auto">
                      {customers.map(c => (
                        <button key={c.id} onClick={() => { setSelectedCust(c); setCustSearch(''); setCustomers([]); }}
                          className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm border-b last:border-0 flex justify-between"
                          data-testid={`compose-cust-${c.id}`}>
                          <span>{c.name}</span>
                          <span className="text-xs text-slate-400">{c.phone || 'No phone'}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Message */}
            <div>
              <Label className="text-[10px] text-slate-400 uppercase">Message</Label>
              <textarea value={composeMsg} onChange={e => setComposeMsg(e.target.value)}
                rows={4} maxLength={320}
                placeholder="Type your message..."
                className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20"
                data-testid="compose-message" />
              <p className="text-[10px] text-slate-400 text-right">{composeMsg.length}/320</p>
            </div>

            <Button onClick={handleComposeSend}
              disabled={!selectedCust || !selectedCust.phone || !composeMsg.trim()}
              className="w-full bg-[#1A4D2E] hover:bg-[#14532d] text-white disabled:opacity-40"
              data-testid="compose-send-btn">
              <Send size={14} className="mr-2" /> Queue Message
            </Button>
          </div>
        </div>
      )}

      {/* ═══ BLAST VIEW ═══ */}
      {view === 'blast' && (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Megaphone size={16} className="text-amber-500" />
              <h3 className="text-sm font-bold text-slate-700">Promo Blast</h3>
            </div>
            <p className="text-xs text-slate-400">Send a message to multiple customers. Use &lt;customer_name&gt; to personalize.</p>

            {/* Filters */}
            <div className="bg-slate-50 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <Filter size={12} className="text-slate-400" />
                <span className="text-[10px] text-slate-500 uppercase font-semibold">Filters</span>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-1.5">
                  <Label className="text-[10px] text-slate-400">Min Balance:</Label>
                  <Input type="number" value={blastFilter.min_balance}
                    onChange={e => setBlastFilter(f => ({ ...f, min_balance: e.target.value }))}
                    placeholder="0" className="h-7 w-24 text-xs"
                    data-testid="blast-min-balance" />
                </div>
                <p className="text-[10px] text-slate-400">Branch: {session.branchName || 'All'}</p>
              </div>
            </div>

            {/* Message */}
            <div>
              <Label className="text-[10px] text-slate-400 uppercase">Message</Label>
              <textarea value={blastMsg} onChange={e => setBlastMsg(e.target.value)}
                rows={4} maxLength={320}
                placeholder="Hi <customer_name>, may special promo kami..."
                className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20"
                data-testid="blast-message" />
              <p className="text-[10px] text-slate-400 text-right">{blastMsg.length}/320</p>
            </div>

            <Button onClick={handleBlast} disabled={blasting || !blastMsg.trim()}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-40"
              data-testid="blast-send-btn">
              {blasting ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Megaphone size={14} className="mr-2" />}
              {blasting ? 'Sending...' : 'Send Blast'}
            </Button>
          </div>
        </div>
      )}

      {/* ═══ TEMPLATES VIEW ═══ */}
      {view === 'templates' && (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
          {templates.map(t => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 p-3" data-testid={`template-${t.key}`}>
              {editingTemplate?.id === t.id ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">{t.name}</span>
                    <div className="flex gap-1.5">
                      <Button size="sm" className="h-7 text-[10px] bg-[#1A4D2E] text-white" onClick={saveTemplate}>
                        <Check size={10} className="mr-1" /> Save
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 text-[10px]" onClick={() => setEditingTemplate(null)}>
                        <X size={10} />
                      </Button>
                    </div>
                  </div>
                  <textarea value={editBody} onChange={e => setEditBody(e.target.value)}
                    rows={4}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20 font-mono" />
                  <div className="flex flex-wrap gap-1">
                    {t.placeholders?.map(p => (
                      <span key={p} className="text-[9px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-mono">&lt;{p}&gt;</span>
                    ))}
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-700">{t.name}</span>
                      <Badge className={`text-[9px] ${t.active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>
                        {t.active ? 'Active' : 'Disabled'}
                      </Badge>
                      <Badge className="text-[9px] bg-slate-50 text-slate-500">{t.trigger}</Badge>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => { setEditingTemplate(t); setEditBody(t.body); }}
                        className="text-slate-400 hover:text-slate-600 p-1">
                        <Edit3 size={12} />
                      </button>
                      <button onClick={() => toggleTemplate(t)}
                        className={`p-1 ${t.active ? 'text-emerald-500 hover:text-red-500' : 'text-slate-300 hover:text-emerald-500'}`}
                        title={t.active ? 'Disable' : 'Enable'}>
                        {t.active ? <Check size={12} /> : <X size={12} />}
                      </button>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 font-mono">{t.body}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
