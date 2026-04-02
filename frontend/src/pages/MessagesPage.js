import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  MessageSquare, Send, Clock, AlertTriangle, SkipForward,
  RefreshCw, Users, Filter, Edit3, Check, X, Search,
  Megaphone, Loader2, Settings, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, Phone, FileText, UserPlus
} from 'lucide-react';
import { toast } from 'sonner';

const STATUS_CONFIG = {
  pending: { label: 'Pending', icon: Clock, cls: 'bg-amber-100 text-amber-700', dotCls: 'bg-amber-400' },
  sent: { label: 'Sent', icon: CheckCircle2, cls: 'bg-emerald-100 text-emerald-700', dotCls: 'bg-emerald-400' },
  failed: { label: 'Failed', icon: XCircle, cls: 'bg-red-100 text-red-700', dotCls: 'bg-red-400' },
  skipped: { label: 'Skipped', icon: SkipForward, cls: 'bg-slate-100 text-slate-500', dotCls: 'bg-slate-400' },
};

const TEMPLATE_BADGE = {
  credit_new: 'bg-blue-100 text-blue-700',
  reminder_15day: 'bg-amber-100 text-amber-700',
  reminder_7day: 'bg-orange-100 text-orange-700',
  overdue_notice: 'bg-red-100 text-red-700',
  payment_received: 'bg-emerald-100 text-emerald-700',
  charge_applied: 'bg-purple-100 text-purple-700',
  delivery_ready: 'bg-teal-100 text-teal-700',
  promo_blast: 'bg-pink-100 text-pink-700',
  monthly_summary: 'bg-indigo-100 text-indigo-700',
  custom: 'bg-slate-100 text-slate-600',
};

export default function MessagesPage() {
  const { user, currentBranch, branches } = useAuth();
  const [activeTab, setActiveTab] = useState('queue');

  // Queue state
  const [statusFilter, setStatusFilter] = useState('pending');
  const [queue, setQueue] = useState([]);
  const [queueTotal, setQueueTotal] = useState(0);
  const [stats, setStats] = useState({ pending: 0, sent: 0, failed: 0, skipped: 0, total: 0 });
  const [loading, setLoading] = useState(false);

  // Company name for signature hint
  const [companyName, setCompanyName] = useState('');

  // Conversations state
  const [convoSection, setConvoSection] = useState('customers'); // 'customers' | 'unknown' (admin only)
  const [unknownCount, setUnknownCount] = useState(0);
  const [conversations, setConversations] = useState([]);
  const [activeConvo, setActiveConvo] = useState(null);
  const [thread, setThread] = useState([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [replyMsg, setReplyMsg] = useState('');
  const [replying, setReplying] = useState(false);
  const [convoSearch, setConvoSearch] = useState('');

  // Assign-to-customer modal state
  const [assignModal, setAssignModal] = useState(false);
  const [assignSearch, setAssignSearch] = useState('');
  const [assignResults, setAssignResults] = useState([]);
  const [assigning, setAssigning] = useState(false);

  // Compose state
  const [customers, setCustomers] = useState([]);
  const [custSearch, setCustSearch] = useState('');
  const [custDropdownOpen, setCustDropdownOpen] = useState(false);
  const [selectedCust, setSelectedCust] = useState(null);
  const [composeMsg, setComposeMsg] = useState('');
  const [sending, setSending] = useState(false);

  // Blast state
  const [blastMsg, setBlastMsg] = useState('');
  const [blastMinBal, setBlastMinBal] = useState('');
  const [blasting, setBlasting] = useState(false);

  // Templates state
  const [templates, setTemplates] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editBody, setEditBody] = useState('');

  // Settings state
  const [smsSettings, setSmsSettings] = useState([]);

  // Adaptive polling ref + thread scroll anchor
  const pollIntervalRef = useRef(null);
  const messagesEndRef = useRef(null);

  // ── Data loaders ──
  const loadStats = useCallback(async () => {
    try {
      const res = await api.get('/sms/stats');
      setStats(res.data);
    } catch { /* ignore */ }
  }, []);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const params = { status: statusFilter, limit: 100 };
      if (currentBranch?.id) params.branch_id = currentBranch.id;
      const res = await api.get('/sms/queue', { params });
      setQueue(res.data.items || []);
      setQueueTotal(res.data.total || 0);
    } catch { /* ignore */ }
    setLoading(false);
  }, [statusFilter, currentBranch]);

  const loadTemplates = useCallback(async () => {
    try {
      const res = await api.get('/sms/templates');
      setTemplates(res.data || []);
    } catch { /* ignore */ }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      const res = await api.get('/sms/settings');
      setSmsSettings(res.data || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { if (activeTab === 'queue') loadQueue(); }, [activeTab, loadQueue]);
  useEffect(() => { if (activeTab === 'templates') loadTemplates(); }, [activeTab, loadTemplates]);
  useEffect(() => { if (activeTab === 'settings') loadSettings(); }, [activeTab, loadSettings]);
  // Reload conversations + unknown count when tab, section, or branch changes
  useEffect(() => {
    if (activeTab === 'conversations') {
      loadConversations(convoSection);
      loadUnknownCount();
      setActiveConvo(null);
      setThread([]);
    }
  }, [activeTab, convoSection, currentBranch]); // eslint-disable-line

  // Fetch company name once for the auto-signature hint
  useEffect(() => {
    api.get('/settings/business-info').then(res => {
      setCompanyName(res.data.business_name || '');
    }).catch(() => {});
  }, []);

  // ── Adaptive polling ──────────────────────────────────────────────────────
  useEffect(() => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    const isConvoTab = activeTab === 'conversations';
    const hasThread  = Boolean(activeConvo?.phone);
    const pollMs = hasThread ? 7000 : isConvoTab ? 30000 : 60000;

    const poll = () => {
      if (document.hidden) return;
      api.get('/sms/stats').then(res => setStats(res.data)).catch(() => {});

      if (isConvoTab) {
        const params = { section: convoSection };
        if (convoSection === 'customers' && currentBranch?.id) params.branch_id = currentBranch.id;
        api.get('/sms/conversations', { params })
          .then(res => setConversations(res.data || []))
          .catch(() => {});
        // Keep unknown count badge fresh
        api.get('/sms/conversations', { params: { section: 'unknown' } })
          .then(res => setUnknownCount(res.data.length || 0))
          .catch(() => {});

        if (hasThread) {
          api.get(`/sms/conversation/${encodeURIComponent(activeConvo.phone)}`)
            .then(res => setThread(res.data.messages || []))
            .catch(() => {});
        }
      }
    };

    pollIntervalRef.current = setInterval(poll, pollMs);
    return () => clearInterval(pollIntervalRef.current);
  }, [activeTab, activeConvo?.phone, currentBranch?.id, convoSection]); // eslint-disable-line

  // Cleanup on unmount
  useEffect(() => () => clearInterval(pollIntervalRef.current), []);

  // Auto-scroll thread to bottom when new messages arrive
  useEffect(() => {
    if (thread.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [thread.length]);

  // ── Conversations ──
  const loadConversations = async (section = convoSection) => {
    try {
      const params = { section };
      if (section === 'customers' && currentBranch?.id) params.branch_id = currentBranch.id;
      const res = await api.get('/sms/conversations', { params });
      setConversations(res.data || []);
    } catch { /* ignore */ }
  };

  const loadUnknownCount = async () => {
    if (user?.role !== 'admin') return;
    try {
      const res = await api.get('/sms/conversations', { params: { section: 'unknown' } });
      setUnknownCount(res.data.length || 0);
    } catch { /* ignore */ }
  };

  const openConversation = async (convo) => {
    setActiveConvo(convo);
    setThreadLoading(true);
    try {
      const res = await api.get(`/sms/conversation/${encodeURIComponent(convo.phone)}`);
      setThread(res.data.messages || []);
      // Refresh to clear unread
      loadConversations(convoSection);
    } catch { setThread([]); }
    setThreadLoading(false);
  };

  const searchAssignCustomers = async (q) => {
    setAssignSearch(q);
    if (!q.trim()) { setAssignResults([]); return; }
    try {
      const res = await api.get('/customers', { params: { search: q, limit: 10 } });
      setAssignResults(res.data.customers || []);
    } catch { setAssignResults([]); }
  };

  const handleAssignPhone = async (customer) => {
    if (!activeConvo) return;
    setAssigning(true);
    try {
      const res = await api.patch('/sms/assign-phone', {
        phone: activeConvo.phone,
        customer_id: customer.id,
      });
      toast.success(`${activeConvo.phone} assigned to ${customer.name} — ${res.data.migrated_messages} messages migrated`);
      setAssignModal(false);
      setAssignSearch('');
      setAssignResults([]);
      setActiveConvo(null);
      setThread([]);
      loadConversations('customers');
      loadConversations('unknown').then(() => loadUnknownCount());
    } catch (e) { toast.error(e.response?.data?.detail || 'Assignment failed'); }
    setAssigning(false);
  };

  const sendReply = async () => {
    if (!activeConvo || !replyMsg.trim()) return;
    setReplying(true);
    try {
      await api.post('/sms/send', {
        phone: activeConvo.phone,
        customer_name: activeConvo.customer_name,
        customer_id: activeConvo.customer_id || '',
        message: replyMsg,
        branch_id: currentBranch?.id || '',
        branch_name: currentBranch?.name || '',
      });
      setReplyMsg('');
      toast.success('Message queued');
      openConversation(activeConvo);
    } catch (e) { toast.error('Failed to send'); }
    setReplying(false);
  };


  // ── Queue actions ──
  const markSent = async (id) => {
    await api.patch(`/sms/queue/${id}/mark-sent`);
    toast.success('Marked as sent');
    loadQueue(); loadStats();
  };

  const retrySms = async (id) => {
    await api.post(`/sms/queue/${id}/retry`);
    toast.success('Re-queued for sending');
    loadQueue(); loadStats();
  };

  const skipSms = async (id) => {
    await api.post(`/sms/queue/${id}/skip`);
    toast('Message skipped');
    loadQueue(); loadStats();
  };

  // ── Compose ──
  const searchCustomers = async (q) => {
    setCustSearch(q);
    if (!q) { setCustomers([]); return; }
    try {
      const res = await api.get('/customers', { params: { search: q, limit: 12 } });
      setCustomers(res.data.customers || []);
    } catch { setCustomers([]); }
  };

  const handleComposeSend = async () => {
    if (!selectedCust?.phone || !composeMsg.trim()) return;
    setSending(true);
    try {
      await api.post('/sms/send', {
        customer_id: selectedCust.id, customer_name: selectedCust.name,
        phone: selectedCust.phone, message: composeMsg,
        branch_id: currentBranch?.id || '', branch_name: currentBranch?.name || '',
      });
      toast.success(`Message queued for ${selectedCust.name}`);
      setComposeMsg(''); setSelectedCust(null); setCustSearch('');
      loadStats();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setSending(false);
  };

  // ── Blast ──
  const handleBlast = async () => {
    if (!blastMsg.trim()) return;
    setBlasting(true);
    try {
      const payload = {
        message: blastMsg,
        branch_id: currentBranch?.id || '',
        branch_name: currentBranch?.name || '',
        filter: {},
      };
      if (blastMinBal) payload.filter.min_balance = parseFloat(blastMinBal);
      if (currentBranch?.id) payload.filter.branch_id = currentBranch.id;
      const res = await api.post('/sms/blast', payload);
      toast.success(`${res.data.queued} messages queued (${res.data.skipped_no_phone} skipped — no phone)`);
      setBlastMsg(''); setBlastMinBal('');
      loadStats();
    } catch (e) { toast.error(e.response?.data?.detail || 'Blast failed'); }
    setBlasting(false);
  };

  // ── Templates ──
  const saveTemplate = async (id) => {
    try {
      await api.put(`/sms/templates/${id}`, { body: editBody });
      toast.success('Template saved');
      setEditingId(null);
      loadTemplates();
    } catch { toast.error('Failed to save'); }
  };

  const toggleTemplate = async (t) => {
    await api.put(`/sms/templates/${t.id}`, { active: !t.active });
    toast.success(`${t.name} ${t.active ? 'disabled' : 'enabled'}`);
    loadTemplates();
  };

  // ── Settings ──
  const toggleSetting = async (key) => {
    const current = smsSettings.find(s => s.trigger_key === key);
    const enabled = current ? !current.enabled : false;
    await api.put(`/sms/settings/${key}`, { enabled });
    toast.success(`${key.replace(/_/g, ' ')} ${enabled ? 'enabled' : 'disabled'}`);
    loadSettings();
  };

  const fmtTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' }) + ' ' +
           d.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-4 animate-fadeIn" data-testid="messages-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }} data-testid="messages-title">
            SMS Messages
          </h1>
          <div className="flex items-center gap-2">
            {stats.pending > 0 && <Badge className="bg-amber-100 text-amber-700 text-xs">{stats.pending} pending</Badge>}
            {stats.failed > 0 && <Badge className="bg-red-100 text-red-700 text-xs">{stats.failed} failed</Badge>}
            <span className="text-xs text-slate-400">{stats.total} total</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 pb-px" data-testid="messages-tabs">
        {[
          { key: 'conversations', label: 'Conversations', icon: MessageSquare },
          { key: 'queue', label: 'Message Queue', icon: Clock },
          { key: 'compose', label: 'Compose', icon: Send },
          { key: 'blast', label: 'Promo Blast', icon: Megaphone },
          { key: 'templates', label: 'Templates', icon: FileText },
          { key: 'settings', label: 'Settings', icon: Settings },
        ].map(t => {
          const Icon = t.icon;
          return (
            <button key={t.key} onClick={() => setActiveTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === t.key
                  ? 'border-[#1A4D2E] text-[#1A4D2E]'
                  : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}
              data-testid={`tab-${t.key}`}>
              <Icon size={14} /> {t.label}
            </button>
          );
        })}
      </div>

      {/* ═══ CONVERSATIONS TAB ═══ */}
      {activeTab === 'conversations' && (
        <div className="flex gap-4 h-[calc(100vh-220px)]">
          {/* Left — conversation list */}
          <div className="w-72 shrink-0 flex flex-col border border-slate-200 rounded-xl overflow-hidden bg-white">
            {/* Section toggle — Customers / Unknown (admin only) */}
            <div className="flex border-b border-slate-100">
              <button onClick={() => setConvoSection('customers')}
                className={`flex-1 py-2 text-xs font-semibold transition-colors ${
                  convoSection === 'customers' ? 'bg-[#1A4D2E] text-white' : 'text-slate-400 hover:bg-slate-50'
                }`}
                data-testid="section-customers">
                Customers
              </button>
              {user?.role === 'admin' && (
                <button onClick={() => setConvoSection('unknown')}
                  className={`flex-1 py-2 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 ${
                    convoSection === 'unknown' ? 'bg-amber-500 text-white' : 'text-slate-400 hover:bg-slate-50'
                  }`}
                  data-testid="section-unknown">
                  Unknown
                  {unknownCount > 0 && (
                    <span className={`text-[9px] font-bold rounded-full px-1.5 py-0.5 ${
                      convoSection === 'unknown' ? 'bg-white/30 text-white' : 'bg-amber-500 text-white'
                    }`}>{unknownCount}</span>
                  )}
                </button>
              )}
            </div>

            <div className="px-3 py-2 border-b border-slate-100 flex items-center gap-2">
              <Search size={13} className="text-slate-400" />
              <input value={convoSearch} onChange={e => setConvoSearch(e.target.value)}
                placeholder={convoSection === 'unknown' ? 'Search by number…' : 'Search conversations…'}
                className="flex-1 text-xs outline-none bg-transparent text-slate-700 placeholder-slate-400" />
              {/* Live polling indicator */}
              <div className="flex items-center gap-1 shrink-0">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[9px] text-slate-400">
                  {activeConvo ? '7s' : '30s'}
                </span>
              </div>
              <button onClick={() => loadConversations(convoSection)} className="text-slate-400 hover:text-slate-600">
                <RefreshCw size={12} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
              {conversations.length === 0 && (
                <div className="text-center text-slate-400 text-xs py-12">
                  {convoSection === 'unknown' ? 'No unknown numbers' : 'No conversations yet'}
                </div>
              )}
              {conversations
                .filter(c => !convoSearch || c.customer_name?.toLowerCase().includes(convoSearch.toLowerCase()) || c.phone?.includes(convoSearch))
                .map(c => {
                  const isUnknown = convoSection === 'unknown';
                  return (
                    <button key={c.phone} onClick={() => openConversation(c)}
                      className={`w-full text-left px-3 py-3 hover:bg-slate-50 transition-colors ${activeConvo?.phone === c.phone ? 'bg-[#f0f7f3]' : ''}`}
                      data-testid={`convo-${c.phone}`}>
                      <div className="flex items-start justify-between gap-1">
                        <div className="flex items-center gap-2 shrink-0">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                            isUnknown ? 'bg-amber-400' : 'bg-[#1A4D2E]'
                          }`}>
                            {isUnknown ? '?' : c.customer_name?.[0]?.toUpperCase() || '?'}
                          </div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs font-semibold text-slate-800 truncate">
                              {isUnknown ? c.phone : c.customer_name}
                            </span>
                            {c.unread > 0 && (
                              <span className={`shrink-0 text-white text-[9px] font-bold rounded-full px-1.5 py-0.5 ${isUnknown ? 'bg-amber-500' : 'bg-[#1A4D2E]'}`}>{c.unread}</span>
                            )}
                            {isUnknown && (
                              <span className="text-[8px] bg-amber-50 text-amber-600 border border-amber-200 px-1 py-0.5 rounded font-medium">Unregistered</span>
                            )}
                          </div>
                          {!isUnknown && (
                            <>
                              <p className="text-[10px] text-slate-400 font-mono">{c.phone}</p>
                              {c.branch_names?.length > 1 && (
                                <div className="flex gap-1 mt-0.5 flex-wrap">
                                  {c.branch_names.filter(Boolean).map((bn, i) => (
                                    <span key={i} className={`text-[8px] px-1.5 py-0.5 rounded-full font-medium ${
                                      bn === currentBranch?.name ? 'bg-[#1A4D2E] text-white' : 'bg-blue-100 text-blue-700'
                                    }`}>{bn}</span>
                                  ))}
                                </div>
                              )}
                              {c.branch_names?.length === 1 && c.branch_names[0] && (
                                <span className="text-[9px] text-slate-400">{c.branch_names[0]}</span>
                              )}
                            </>
                          )}
                          <p className={`text-[10px] mt-0.5 truncate ${c.last_direction === 'in' ? isUnknown ? 'text-amber-600 font-medium' : 'text-[#1A4D2E] font-medium' : 'text-slate-400'}`}>
                            {c.last_direction === 'in' ? '← ' : '→ '}{c.last_message}
                          </p>
                        </div>
                        <span className="text-[9px] text-slate-300 shrink-0 mt-0.5">
                          {c.last_time ? new Date(c.last_time).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' }) : ''}
                        </span>
                      </div>
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Right — thread */}
          <div className="flex-1 flex flex-col border border-slate-200 rounded-xl overflow-hidden bg-white">
            {!activeConvo ? (
              <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
                <div className="text-center">
                  <MessageSquare size={32} className="mx-auto mb-2 opacity-30" />
                  <p>Select a conversation</p>
                </div>
              </div>
            ) : (
              <>
                {/* Thread header */}
                <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                    convoSection === 'unknown' ? 'bg-amber-400' : 'bg-[#1A4D2E]'
                  }`}>
                    {convoSection === 'unknown' ? '?' : activeConvo.customer_name?.[0]?.toUpperCase() || '?'}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-800">
                        {convoSection === 'unknown' ? activeConvo.phone : activeConvo.customer_name}
                      </p>
                      {convoSection === 'unknown' && (
                        <span className="text-[9px] bg-amber-50 text-amber-600 border border-amber-200 px-1.5 py-0.5 rounded font-medium">Unregistered</span>
                      )}
                    </div>
                    {convoSection !== 'unknown' && (
                      <p className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                        <Phone size={9} /> {activeConvo.phone}
                      </p>
                    )}
                  </div>
                  {/* Branch context + Assign button */}
                  <div className="ml-auto flex items-center gap-2">
                    {convoSection === 'unknown' ? (
                      <button onClick={() => setAssignModal(true)}
                        className="flex items-center gap-1.5 text-xs bg-[#1A4D2E] text-white px-3 py-1.5 rounded-lg hover:bg-[#14532d] transition-colors"
                        data-testid="assign-phone-btn">
                        <UserPlus size={12} /> Assign to Customer
                      </button>
                    ) : currentBranch ? (
                      <span className="text-[10px] bg-[#1A4D2E]/10 text-[#1A4D2E] px-2 py-0.5 rounded-full font-medium">
                        {currentBranch.name}
                      </span>
                    ) : (
                      <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium">
                        All Branches
                      </span>
                    )}
                    <button onClick={() => openConversation(activeConvo)} className="text-slate-400 hover:text-slate-600">
                      <RefreshCw size={13} className={threadLoading ? 'animate-spin' : ''} />
                    </button>
                  </div>
                </div>

                {/* Bubbles */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                  {threadLoading && (
                    <div className="flex justify-center py-8"><Loader2 size={20} className="animate-spin text-slate-400" /></div>
                  )}
                  {!threadLoading && thread.length === 0 && (
                    <div className="text-center text-slate-400 text-xs py-8">No messages yet</div>
                  )}
                  {thread.map((msg, i) => {
                    const isOut = msg.direction === 'out';
                    const isMyBranch = !currentBranch || msg.branch_id === currentBranch?.id || !msg.branch_id;
                    return (
                      <div key={msg.id || i} className={`flex ${isOut ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[70%] px-3 py-2 text-xs leading-relaxed shadow-sm ${
                          isOut && isMyBranch
                            ? 'bg-[#1A4D2E] text-white rounded-t-2xl rounded-bl-2xl rounded-br-sm'
                            : isOut && !isMyBranch
                            ? 'bg-blue-600 text-white rounded-t-2xl rounded-bl-2xl rounded-br-sm opacity-80'
                            : 'bg-slate-100 text-slate-800 rounded-t-2xl rounded-br-2xl rounded-bl-sm'
                        }`}>
                          {/* Other-branch label */}
                          {isOut && !isMyBranch && msg.branch_name && (
                            <p className="text-[9px] font-semibold text-blue-200 mb-1">{msg.branch_name}</p>
                          )}
                          <p className="whitespace-pre-wrap">{msg.message}</p>
                          <p className={`text-[9px] mt-1 ${isOut ? 'text-white/60' : 'text-slate-400'}`}>
                            {msg.sent_by_name && <span className="mr-1">{msg.sent_by_name} ·</span>}
                            {msg.created_at ? new Date(msg.created_at).toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' }) : ''}
                            {isOut && msg.status && <span className="ml-1 opacity-60">· {msg.status}</span>}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  {/* Scroll anchor — new messages auto-scroll here */}
                  <div ref={messagesEndRef} />
                </div>

                {/* Reply box */}
                <div className="px-4 py-3 border-t border-slate-100">
                  {/* Auto-signature hint — read-only, always appended by server */}
                  {currentBranch && (
                    <p className="text-[10px] text-slate-400 mb-1.5 flex items-center gap-1">
                      <span className="font-mono bg-slate-50 border border-slate-200 rounded px-1.5 py-0.5 text-slate-500">
                        Auto-signature: - {[companyName, currentBranch.name].filter(Boolean).join(' | ')}
                      </span>
                      <span className="text-slate-300">(cannot be removed)</span>
                    </p>
                  )}
                  <div className="flex items-center gap-2">
                    <input value={replyMsg} onChange={e => setReplyMsg(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendReply()}
                      placeholder="Type a message…"
                      className="flex-1 text-sm border border-slate-200 rounded-full px-4 py-2 outline-none focus:border-[#1A4D2E] transition-colors" />
                    <button onClick={sendReply} disabled={replying || !replyMsg.trim()}
                      className="w-9 h-9 rounded-full bg-[#1A4D2E] flex items-center justify-center text-white disabled:opacity-40 hover:bg-[#14532d] transition-colors"
                      data-testid="send-reply-btn">
                      {replying ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ═══ ASSIGN TO CUSTOMER MODAL ═══ */}
      {assignModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md space-y-4 p-5">
            <div>
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <UserPlus size={16} className="text-[#1A4D2E]" />
                Assign Number to Customer
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                <span className="font-mono font-semibold text-slate-600">{activeConvo?.phone}</span>
                {' '}→ all past messages will move to the customer's branch.
              </p>
            </div>

            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                autoFocus
                value={assignSearch}
                onChange={e => searchAssignCustomers(e.target.value)}
                placeholder="Search customer by name or phone..."
                className="pl-8 h-9 text-sm"
                data-testid="assign-search-input"
              />
            </div>

            {assignResults.length > 0 && (
              <div className="border border-slate-200 rounded-lg overflow-hidden max-h-52 overflow-y-auto">
                {assignResults.map(c => {
                  const branchName = branches?.find(b => b.id === c.branch_id)?.name || '';
                  return (
                    <button key={c.id}
                      onClick={() => handleAssignPhone(c)}
                      disabled={assigning}
                      className="w-full text-left px-3 py-2.5 hover:bg-slate-50 border-b last:border-0 flex items-center justify-between gap-2 transition-colors"
                      data-testid={`assign-customer-${c.id}`}>
                      <div>
                        <p className="text-sm font-medium text-slate-800">{c.name}</p>
                        <p className="text-[10px] text-slate-400 font-mono">{c.phone || 'No phone'}</p>
                      </div>
                      <div className="text-right shrink-0">
                        {branchName && (
                          <span className="text-[9px] bg-[#1A4D2E]/10 text-[#1A4D2E] px-1.5 py-0.5 rounded-full font-medium">
                            {branchName}
                          </span>
                        )}
                        {assigning && <Loader2 size={12} className="animate-spin text-slate-400 ml-1 inline" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {assignSearch && assignResults.length === 0 && (
              <p className="text-xs text-center text-slate-400 py-2">No customers found</p>
            )}

            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => {
                setAssignModal(false);
                setAssignSearch('');
                setAssignResults([]);
              }}>Cancel</Button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ QUEUE TAB ═══ */}
      {activeTab === 'queue' && (
        <Card className="border-slate-200">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <div className="flex gap-1.5">
              {Object.entries(STATUS_CONFIG).map(([key, cfg]) => {
                const Icon = cfg.icon;
                const count = stats[key] || 0;
                return (
                  <button key={key} onClick={() => setStatusFilter(key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      statusFilter === key ? 'bg-slate-800 text-white' : 'bg-slate-50 text-slate-500 hover:bg-slate-100'
                    }`}
                    data-testid={`filter-${key}`}>
                    <Icon size={12} /> {cfg.label}
                    {count > 0 && <span className="opacity-70">({count})</span>}
                  </button>
                );
              })}
            </div>
            <button onClick={() => { loadQueue(); loadStats(); }}
              className="text-slate-400 hover:text-slate-600 p-1" data-testid="refresh-queue-btn">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>

          <div className="divide-y divide-slate-100 max-h-[calc(100vh-320px)] overflow-y-auto">
            {queue.length === 0 && (
              <div className="text-center text-slate-400 text-sm py-16">
                No {statusFilter} messages
              </div>
            )}
            {queue.map(sms => {
              const sc = STATUS_CONFIG[sms.status] || STATUS_CONFIG.pending;
              return (
                <div key={sms.id} className="px-4 py-3 hover:bg-slate-50/50 transition-colors" data-testid={`sms-row-${sms.id}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-800">{sms.customer_name || 'Unknown'}</span>
                        <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                          <Phone size={10} /> {sms.phone}
                        </span>
                        <Badge className={`text-[9px] ${TEMPLATE_BADGE[sms.template_key] || 'bg-slate-100 text-slate-600'}`}>
                          {sms.template_key.replace(/_/g, ' ')}
                        </Badge>
                        {sms.branch_name && (
                          <span className="text-[10px] text-slate-400">{sms.branch_name}</span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">{sms.message}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <Badge className={`text-[9px] ${sc.cls}`}>{sc.label}</Badge>
                      <p className="text-[10px] text-slate-400 mt-0.5">{fmtTime(sms.created_at)}</p>
                      {sms.sent_at && <p className="text-[10px] text-emerald-500">Sent {fmtTime(sms.sent_at)}</p>}
                      {sms.error && <p className="text-[10px] text-red-500 max-w-[140px] truncate">{sms.error}</p>}
                    </div>
                  </div>

                  {/* Actions per status */}
                  {sms.status === 'pending' && (
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-100">
                      <Button size="sm" className="h-7 text-[10px] bg-[#1A4D2E] hover:bg-[#14532d] text-white"
                        onClick={() => markSent(sms.id)} data-testid={`mark-sent-${sms.id}`}>
                        <CheckCircle2 size={10} className="mr-1" /> Mark Sent
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 text-[10px] text-slate-400"
                        onClick={() => skipSms(sms.id)}>
                        <SkipForward size={10} className="mr-1" /> Skip
                      </Button>
                      <div className="flex-1" />
                      <span className="text-[10px] text-slate-300">{sms.trigger}</span>
                    </div>
                  )}
                  {sms.status === 'failed' && (
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-100">
                      <Button size="sm" variant="outline" className="h-7 text-[10px] text-amber-600 border-amber-200"
                        onClick={() => retrySms(sms.id)}>
                        <RefreshCw size={10} className="mr-1" /> Retry
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {queueTotal > queue.length && (
            <div className="px-4 py-2 text-center text-xs text-slate-400 border-t border-slate-100">
              Showing {queue.length} of {queueTotal}
            </div>
          )}
        </Card>
      )}

      {/* ═══ COMPOSE TAB ═══ */}
      {activeTab === 'compose' && (
        <Card className="border-slate-200 max-w-2xl">
          <CardContent className="p-5 space-y-4">
            <h2 className="text-sm font-bold text-slate-700">Compose Message</h2>

            {/* Customer selector */}
            <div>
              <Label className="text-xs text-slate-500 uppercase tracking-wide">To (Customer)</Label>
              {selectedCust ? (
                <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2.5 mt-1">
                  <div>
                    <span className="text-sm font-medium">{selectedCust.name}</span>
                    <span className="text-xs text-slate-400 ml-2 font-mono">{selectedCust.phone || 'No phone'}</span>
                  </div>
                  <button onClick={() => { setSelectedCust(null); setCustSearch(''); }} className="text-slate-400 hover:text-slate-600">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="relative mt-1">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input value={custSearch}
                    onChange={e => searchCustomers(e.target.value)}
                    onFocus={() => setCustDropdownOpen(true)}
                    onBlur={() => setTimeout(() => setCustDropdownOpen(false), 200)}
                    placeholder="Search customer by name or phone..."
                    className="pl-8 h-9"
                    data-testid="compose-search" />
                  {custDropdownOpen && customers.length > 0 && (
                    <div className="absolute z-50 top-full mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                      {customers.map(c => (
                        <button key={c.id} onMouseDown={() => { setSelectedCust(c); setCustSearch(''); setCustomers([]); }}
                          className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm border-b last:border-0 flex justify-between"
                          data-testid={`compose-cust-${c.id}`}>
                          <span className="font-medium">{c.name}</span>
                          <span className="text-xs text-slate-400 font-mono">{c.phone || 'No phone'}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Message */}
            <div>
              <Label className="text-xs text-slate-500 uppercase tracking-wide">Message</Label>
              <textarea value={composeMsg} onChange={e => setComposeMsg(e.target.value)}
                rows={5} maxLength={320}
                placeholder="Type your message here..."
                className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20"
                data-testid="compose-message" />
              <p className="text-[10px] text-slate-400 text-right mt-1">{composeMsg.length} / 320 characters</p>
            </div>

            <div className="flex items-center gap-3">
              <Button onClick={handleComposeSend}
                disabled={sending || !selectedCust?.phone || !composeMsg.trim()}
                className="bg-[#1A4D2E] hover:bg-[#14532d] text-white disabled:opacity-40"
                data-testid="compose-send-btn">
                {sending ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Send size={14} className="mr-2" />}
                Queue Message
              </Button>
              {!selectedCust?.phone && selectedCust && (
                <span className="text-xs text-red-500">This customer has no phone number</span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ═══ BLAST TAB ═══ */}
      {activeTab === 'blast' && (
        <Card className="border-slate-200 max-w-2xl">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2">
              <Megaphone size={18} className="text-amber-500" />
              <h2 className="text-sm font-bold text-slate-700">Promo Blast</h2>
            </div>
            <p className="text-xs text-slate-400">
              Send a message to multiple customers at once. Use <code className="bg-slate-100 px-1 rounded text-[11px]">&lt;customer_name&gt;</code> to personalize each message.
            </p>

            {/* Filters */}
            <div className="bg-slate-50 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Filter size={13} className="text-slate-400" />
                <span className="text-xs text-slate-500 uppercase font-semibold">Customer Filters</span>
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <Label className="text-xs text-slate-500">Min Balance:</Label>
                  <Input type="number" value={blastMinBal}
                    onChange={e => setBlastMinBal(e.target.value)}
                    placeholder="e.g. 5000" className="h-8 w-28 text-xs"
                    data-testid="blast-min-balance" />
                </div>
                <div className="text-xs text-slate-400">
                  Branch: <strong>{currentBranch?.name || 'All branches'}</strong>
                </div>
              </div>
            </div>

            {/* Message */}
            <div>
              <Label className="text-xs text-slate-500 uppercase tracking-wide">Message</Label>
              <textarea value={blastMsg} onChange={e => setBlastMsg(e.target.value)}
                rows={5} maxLength={320}
                placeholder="Hi <customer_name>, may special promo kami ngayong buwan..."
                className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20"
                data-testid="blast-message" />
              <p className="text-[10px] text-slate-400 text-right mt-1">{blastMsg.length} / 320 characters</p>
            </div>

            <Button onClick={handleBlast} disabled={blasting || !blastMsg.trim()}
              className="bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-40"
              data-testid="blast-send-btn">
              {blasting ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Megaphone size={14} className="mr-2" />}
              {blasting ? 'Sending...' : 'Send Blast'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ═══ TEMPLATES TAB ═══ */}
      {activeTab === 'templates' && (
        <div className="space-y-3 max-w-3xl">
          <p className="text-xs text-slate-400">Edit message templates. Use <code className="bg-slate-100 px-1 rounded text-[11px]">&lt;placeholder&gt;</code> tags that get replaced with real data when the message is generated.</p>
          {templates.map(t => (
            <Card key={t.id} className="border-slate-200" data-testid={`template-card-${t.key}`}>
              <CardContent className="p-4">
                {editingId === t.id ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-slate-700">{t.name}</span>
                      <div className="flex gap-2">
                        <Button size="sm" className="h-7 text-xs bg-[#1A4D2E] text-white" onClick={() => saveTemplate(t.id)}
                          data-testid={`save-template-${t.key}`}>
                          <Check size={11} className="mr-1" /> Save
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingId(null)}>Cancel</Button>
                      </div>
                    </div>
                    <textarea value={editBody} onChange={e => setEditBody(e.target.value)}
                      rows={5}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-[#1A4D2E]/20" />
                    <div className="flex flex-wrap gap-1.5">
                      <span className="text-[10px] text-slate-400 mr-1">Available:</span>
                      {t.placeholders?.map(p => (
                        <button key={p} onClick={() => setEditBody(prev => prev + `<${p}>`)}
                          className="text-[10px] bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded font-mono hover:bg-blue-100 cursor-pointer">
                          &lt;{p}&gt;
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-slate-700">{t.name}</span>
                        <Badge className={`text-[9px] ${t.active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>
                          {t.active ? 'Active' : 'Disabled'}
                        </Badge>
                        <Badge className="text-[9px] bg-slate-50 text-slate-500 border border-slate-200">{t.trigger}</Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => { setEditingId(t.id); setEditBody(t.body); }}
                          className="text-slate-400 hover:text-[#1A4D2E] p-1.5 rounded-lg hover:bg-slate-50" title="Edit template"
                          data-testid={`edit-template-${t.key}`}>
                          <Edit3 size={13} />
                        </button>
                        <button onClick={() => toggleTemplate(t)}
                          className={`p-1.5 rounded-lg hover:bg-slate-50 ${t.active ? 'text-emerald-500 hover:text-red-500' : 'text-slate-300 hover:text-emerald-500'}`}
                          title={t.active ? 'Disable' : 'Enable'}
                          data-testid={`toggle-template-${t.key}`}>
                          {t.active ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2 font-mono leading-relaxed bg-slate-50 rounded-lg p-3">{t.body}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {t.placeholders?.map(p => (
                        <span key={p} className="text-[9px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-mono">&lt;{p}&gt;</span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* ═══ SETTINGS TAB ═══ */}
      {activeTab === 'settings' && (
        <Card className="border-slate-200 max-w-2xl">
          <CardContent className="p-5 space-y-4">
            <h2 className="text-sm font-bold text-slate-700">SMS Trigger Settings</h2>
            <p className="text-xs text-slate-400">Enable or disable automatic SMS triggers. Disabled triggers will not generate new messages.</p>
            <div className="divide-y divide-slate-100">
              {smsSettings.map(s => (
                <div key={s.trigger_key} className="flex items-center justify-between py-3" data-testid={`setting-${s.trigger_key}`}>
                  <div>
                    <p className="text-sm font-medium text-slate-700">{s.template_name}</p>
                    <p className="text-[10px] text-slate-400">{s.trigger_key.replace(/_/g, ' ')}</p>
                  </div>
                  <button onClick={() => toggleSetting(s.trigger_key)}
                    className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${s.enabled ? 'bg-[#1A4D2E]' : 'bg-slate-300'}`}
                    data-testid={`toggle-setting-${s.trigger_key}`}>
                    <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${s.enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
