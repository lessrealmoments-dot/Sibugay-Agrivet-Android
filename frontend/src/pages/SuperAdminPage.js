import { useState, useEffect, useCallback, useRef } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Building2, Users, BarChart3, Shield, RefreshCw, ArrowLeft,
  CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronUp,
  Search, TrendingUp, Edit3, Save, X, Plus, Minus, GitBranch,
  CreditCard, Upload, Eye, EyeOff, Globe, Phone, Settings,
  Clock, Layers, Image, Trash2, ExternalLink
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';

/* ── helpers ──────────────────────────────────────────────────────────────── */
const PLAN_COLORS = {
  trial:       'bg-blue-500/15 text-blue-300 border-blue-500/30',
  basic:       'bg-slate-500/15 text-slate-300 border-slate-500/30',
  standard:    'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  pro:         'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
  founders:    'bg-amber-400/20 text-amber-300 border-amber-400/40',
  suspended:   'bg-red-500/15 text-red-300 border-red-500/30',
  grace_period:'bg-amber-500/15 text-amber-300 border-amber-500/30',
  expired:     'bg-red-500/15 text-red-400 border-red-500/30',
};

const STATUS_DOT = {
  active:       'bg-emerald-400',
  trial:        'bg-blue-400',
  grace_period: 'bg-amber-400',
  expired:      'bg-red-400',
  suspended:    'bg-red-600',
  founders:     'bg-amber-400',
};

function BranchGauge({ used, max }) {
  const pct = max === 0 ? 0 : Math.min((used / max) * 100, 100);
  const color = pct >= 100 ? '#ef4444' : pct >= 80 ? '#f59e0b' : '#10b981';
  const dots = max === 0 ? 10 : Math.min(max + (used > max ? used - max : 0), 10);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        {Array.from({ length: dots }).map((_, i) => (
          <div key={i} className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ background: i < used ? color : '#1e293b', border: `1px solid ${i < used ? color : '#334155'}` }} />
        ))}
        {max === 0 && <span className="text-xs text-slate-500 ml-1">∞</span>}
      </div>
      <span className="text-xs font-mono" style={{ color }}>
        {used}/{max === 0 ? '∞' : max} branches
      </span>
    </div>
  );
}

function PlanBadge({ plan }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold uppercase tracking-wide ${PLAN_COLORS[plan] || PLAN_COLORS.basic}`}>
      {plan}
    </span>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color = 'emerald' }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">{label}</span>
        <div className={`w-8 h-8 rounded-lg bg-${color}-500/10 flex items-center justify-center`}>
          <Icon size={16} className={`text-${color}-400`} />
        </div>
      </div>
      <div className="text-3xl font-extrabold text-white">{value}</div>
      {sub && <div className="text-slate-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────────────────────── */
export default function SuperAdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterPlan, setFilterPlan] = useState('all');
  const [expandedOrg, setExpandedOrg] = useState(null);
  const [orgBranches, setOrgBranches] = useState({});
  const [editModal, setEditModal] = useState(null); // org being edited
  const [paymentSettings, setPaymentSettings] = useState({});
  const [savingPayment, setSavingPayment] = useState(false);

  const load = useCallback(async () => {
    if (!user?.is_super_admin) { navigate('/dashboard'); return; }
    setLoading(true);
    try {
      const [s, o] = await Promise.all([
        api.get('/superadmin/stats'),
        api.get('/superadmin/organizations'),
      ]);
      setStats(s.data);
      setOrgs(o.data);
    } catch { toast.error('Failed to load data'); }
    setLoading(false);
  }, [user, navigate]);

  const loadPayment = useCallback(async () => {
    try {
      const r = await api.get('/superadmin/settings/payment');
      setPaymentSettings(r.data?.value || {});
    } catch {}
  }, []);

  useEffect(() => { load(); loadPayment(); }, [load, loadPayment]);

  const loadOrgBranches = async (orgId) => {
    if (orgBranches[orgId]) return;
    try {
      const r = await api.get(`/superadmin/organizations/${orgId}/branches`);
      setOrgBranches(prev => ({ ...prev, [orgId]: r.data }));
    } catch {}
  };

  const toggleExpand = async (orgId) => {
    if (expandedOrg === orgId) { setExpandedOrg(null); return; }
    setExpandedOrg(orgId);
    await loadOrgBranches(orgId);
  };

  const filtered = orgs.filter(o => {
    const matchSearch = !search ||
      o.name.toLowerCase().includes(search.toLowerCase()) ||
      o.owner_email?.toLowerCase().includes(search.toLowerCase());
    const matchPlan = filterPlan === 'all' || (o.effective_plan || o.plan) === filterPlan;
    return matchSearch && matchPlan;
  });

  if (!user?.is_super_admin) return null;

  return (
    <div className="min-h-screen bg-[#060D1A]" style={{ fontFamily: 'Manrope, sans-serif' }}>
      {/* Top bar */}
      <header className="border-b border-white/5 bg-[#0A0F1C]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/dashboard')} className="text-slate-500 hover:text-slate-300 transition-colors">
              <ArrowLeft size={18} />
            </button>
            <div className="w-7 h-7 bg-emerald-500 rounded-lg flex items-center justify-center">
              <Shield size={14} className="text-white" />
            </div>
            <span className="text-white font-bold">Platform Admin</span>
            <span className="text-slate-600 text-xs hidden md:block">· AgriBooks</span>
          </div>
          <Button variant="ghost" size="sm" onClick={load} className="text-slate-400 hover:text-white gap-2">
            <RefreshCw size={14} />
          </Button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="bg-slate-800/50 border border-slate-700/50 p-1 rounded-xl">
            <TabsTrigger value="overview" className="data-[state=active]:bg-slate-700 data-[state=active]:text-white text-slate-400 rounded-lg px-5">
              Overview
            </TabsTrigger>
            <TabsTrigger value="organizations" className="data-[state=active]:bg-slate-700 data-[state=active]:text-white text-slate-400 rounded-lg px-5">
              Organizations {orgs.length > 0 && <span className="ml-1.5 bg-slate-600 text-slate-300 text-xs px-1.5 py-0.5 rounded-full">{orgs.length}</span>}
            </TabsTrigger>
            <TabsTrigger value="features" className="data-[state=active]:bg-slate-700 data-[state=active]:text-white text-slate-400 rounded-lg px-5">
              Feature Flags
            </TabsTrigger>
            <TabsTrigger value="settings" className="data-[state=active]:bg-slate-700 data-[state=active]:text-white text-slate-400 rounded-lg px-5">
              Payment Settings
            </TabsTrigger>
          </TabsList>

          {/* ── OVERVIEW ────────────────────────────────────────────────── */}
          <TabsContent value="overview" className="space-y-6">
            {loading ? (
              <div className="text-center py-16 text-slate-500">Loading...</div>
            ) : stats && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-3">
                  <KpiCard icon={Building2}     label="Total Orgs"    value={stats.total_organizations} color="slate" />
                  <KpiCard icon={CheckCircle}   label="Active (Paid)" value={stats.active}              color="emerald" />
                  <KpiCard icon={Clock}         label="On Trial"      value={stats.trial}               color="blue" />
                  <KpiCard icon={Star}          label="Founders"      value={stats.founders || 0}       color="amber" />
                  <KpiCard icon={AlertTriangle} label="Expiring Soon" value={stats.expiring_soon}       sub="within 7 days" color="amber" />
                  <KpiCard icon={XCircle}       label="Suspended"     value={stats.suspended}           color="red" />
                  <KpiCard icon={Users}         label="Total Users"   value={stats.total_users}         color="indigo" />
                </div>

                {/* Plan breakdown */}
                <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-6">
                  <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
                    <Layers size={16} className="text-slate-400" /> Plan Breakdown
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { plan: 'basic', label: 'Basic', color: '#64748b', price: '₱1,500' },
                      { plan: 'standard', label: 'Standard', color: '#10b981', price: '₱4,000' },
                      { plan: 'pro', label: 'Pro', color: '#6366f1', price: '₱7,500' },
                    ].map(({ plan, label, color, price }) => {
                      const count = stats.by_plan?.[plan] || 0;
                      const maxVal = Math.max(...Object.values(stats.by_plan || {}), 1);
                      return (
                        <div key={plan} className="bg-slate-900/50 rounded-xl p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-slate-300 text-sm font-medium">{label}</span>
                            <span className="text-xs text-slate-500">{price}</span>
                          </div>
                          <div className="text-2xl font-bold text-white mb-2">{count}</div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5">
                            <div className="h-1.5 rounded-full transition-all" style={{ width: `${(count / maxVal) * 100}%`, background: color }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Orgs needing attention */}
                {orgs.filter(o => ['grace_period', 'expired', 'suspended'].includes(o.effective_plan)).length > 0 && (
                  <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-5">
                    <h3 className="text-amber-300 font-semibold mb-4 flex items-center gap-2">
                      <AlertTriangle size={16} /> Needs Attention
                    </h3>
                    <div className="space-y-2">
                      {orgs.filter(o => ['grace_period', 'expired', 'suspended'].includes(o.effective_plan)).map(org => (
                        <div key={org.id} className="flex items-center justify-between bg-slate-900/50 rounded-xl px-4 py-3">
                          <div>
                            <span className="text-white text-sm font-medium">{org.name}</span>
                            <span className="text-slate-500 text-xs ml-2">{org.owner_email}</span>
                          </div>
                          <PlanBadge plan={org.effective_plan} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </TabsContent>

          {/* ── ORGANIZATIONS ────────────────────────────────────────────── */}
          <TabsContent value="organizations" className="space-y-4">
            {/* Filters */}
            <div className="flex gap-3 flex-wrap">
              <div className="relative flex-1 min-w-[200px]">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search company or email..."
                  className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-600 pl-9 h-10" />
              </div>
              <div className="flex gap-1.5">
                {['all', 'trial', 'basic', 'standard', 'pro', 'suspended'].map(p => (
                  <button key={p} onClick={() => setFilterPlan(p)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${filterPlan === p ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}>
                    {p === 'all' ? 'All' : p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="text-center py-16 text-slate-500">Loading organizations...</div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16 text-slate-500">No organizations found</div>
            ) : (
              <div className="space-y-2">
                {filtered.map(org => (
                  <OrgRow key={org.id} org={org} expanded={expandedOrg === org.id}
                    branches={orgBranches[org.id] || []}
                    onToggle={() => toggleExpand(org.id)}
                    onEdit={() => setEditModal(org)}
                    onRefresh={load} />
                ))}
              </div>
            )}
          </TabsContent>

          {/* ── FEATURE FLAGS ────────────────────────────────────────────── */}
          <TabsContent value="features">
            <FeatureFlagsPanel />
          </TabsContent>

          {/* ── PAYMENT SETTINGS ─────────────────────────────────────────── */}
          <TabsContent value="settings">
            <PaymentSettingsPanel
              settings={paymentSettings}
              setSettings={setPaymentSettings}
              saving={savingPayment}
              setSaving={setSavingPayment}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* Edit subscription modal */}
      {editModal && (
        <EditSubscriptionModal
          org={editModal}
          onClose={() => setEditModal(null)}
          onSaved={(updated) => {
            setOrgs(prev => prev.map(o => o.id === updated.id ? { ...o, ...updated } : o));
            setEditModal(null);
            toast.success('Subscription updated');
          }}
        />
      )}
    </div>
  );
}

/* ── Org Row ────────────────────────────────────────────────────────────── */
function OrgRow({ org, expanded, branches, onToggle, onEdit, onRefresh }) {
  const effectivePlan = org.effective_plan || org.plan;
  const statusKey = org.subscription_status === 'active' && effectivePlan === 'grace_period'
    ? 'grace_period'
    : effectivePlan === 'expired' ? 'expired' : org.subscription_status;

  const expiryDate = org.plan === 'trial' ? org.trial_ends_at : org.subscription_expires_at;
  const daysLeft = expiryDate
    ? Math.ceil((new Date(expiryDate) - new Date()) / 86400000)
    : null;

  return (
    <div className="bg-slate-800/30 border border-slate-700/40 rounded-2xl overflow-hidden hover:border-slate-600/60 transition-colors">
      {/* Row header */}
      <div className="flex items-center gap-4 px-5 py-4">
        {/* Status dot */}
        <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${STATUS_DOT[statusKey] || 'bg-slate-500'}`} />

        {/* Company info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-white font-semibold text-sm truncate">{org.name}</span>
            {org.is_default && <span className="text-xs bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded">Default</span>}
          </div>
          <div className="text-slate-500 text-xs mt-0.5 truncate">{org.owner_email || 'No email'}</div>
        </div>

        {/* Plan */}
        <div className="hidden sm:block">
          <PlanBadge plan={effectivePlan} />
        </div>

        {/* Branch gauge */}
        <div className="hidden md:block">
          <BranchGauge used={org.branch_count || 0} max={org.max_branches || 1} />
        </div>

        {/* Users */}
        <div className="hidden lg:flex items-center gap-1.5 text-slate-400">
          <Users size={13} />
          <span className="text-xs">{org.user_count || 0}</span>
        </div>

        {/* Expiry */}
        {org.plan === 'founders' ? (
          <div className="hidden lg:flex items-center gap-1 text-amber-300 text-xs font-medium">
            <span>★</span> Lifetime
          </div>
        ) : daysLeft !== null ? (
          <div className={`hidden lg:block text-xs font-medium ${daysLeft <= 0 ? 'text-red-400' : daysLeft <= 7 ? 'text-amber-400' : 'text-slate-500'}`}>
            {daysLeft <= 0 ? 'Expired' : `${daysLeft}d left`}
          </div>
        ) : ['basic', 'standard', 'pro'].includes(org.plan) ? (
          <div className="hidden lg:block text-xs text-amber-500/70" title="No expiry date set — plan won't auto-expire">
            No expiry set
          </div>
        ) : null}

        {/* Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button data-testid={`edit-org-${org.id}`} onClick={onEdit}
            className="w-8 h-8 rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 hover:text-white flex items-center justify-center transition-colors">
            <Edit3 size={14} />
          </button>
          <button data-testid={`expand-org-${org.id}`} onClick={onToggle}
            className="w-8 h-8 rounded-lg bg-slate-700/60 hover:bg-slate-600 text-slate-300 hover:text-white flex items-center justify-center transition-colors">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-700/40 bg-slate-900/30 px-5 py-4">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Branches */}
            <div>
              <h4 className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2">
                <GitBranch size={13} /> Branches ({org.branch_count || 0}/{org.max_branches === 0 ? '∞' : org.max_branches})
              </h4>
              {branches.length === 0 ? (
                <p className="text-slate-600 text-xs">No branches yet</p>
              ) : (
                <div className="space-y-1.5">
                  {branches.map(b => (
                    <div key={b.id} className="flex items-center gap-2 text-sm">
                      <div className={`w-1.5 h-1.5 rounded-full ${b.active ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                      <span className={b.active ? 'text-slate-300' : 'text-slate-600'}>{b.name}</span>
                      {b.is_main && <span className="text-xs text-emerald-500">main</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Subscription details */}
            <div>
              <h4 className="text-slate-300 text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2">
                <CreditCard size={13} /> Subscription
              </h4>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Plan</span>
                  <span className="text-slate-300 capitalize">{org.plan}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Effective</span>
                  <span className="text-slate-300 capitalize">{effectivePlan}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Status</span>
                  <span className="text-slate-300">{org.subscription_status}</span>
                </div>
                {org.trial_ends_at && org.plan === 'trial' && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Trial ends</span>
                    <span className="text-slate-300">{new Date(org.trial_ends_at).toLocaleDateString()}</span>
                  </div>
                )}
                {org.plan === 'founders' ? (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Expires</span>
                    <span className="text-amber-300 font-semibold">★ Never (Lifetime)</span>
                  </div>
                ) : org.subscription_expires_at && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Sub expires</span>
                    <span className={`${
                      new Date(org.subscription_expires_at) < new Date() ? 'text-red-400' :
                      Math.ceil((new Date(org.subscription_expires_at) - new Date()) / 86400000) <= 7 ? 'text-amber-400' :
                      'text-slate-300'
                    }`}>
                      {new Date(org.subscription_expires_at).toLocaleDateString()}
                      {' '}
                      ({Math.ceil((new Date(org.subscription_expires_at) - new Date()) / 86400000)}d)
                    </span>
                  </div>
                )}
                {['basic', 'standard', 'pro'].includes(org.plan) && !org.subscription_expires_at && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Expires</span>
                    <span className="text-amber-500/70 text-xs">Not set — set via Edit</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-500">Max branches</span>
                  <span className="text-slate-300">{org.max_branches === 0 ? '∞' : org.max_branches} (+{org.extra_branches || 0} add-on)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Joined</span>
                  <span className="text-slate-300">{new Date(org.created_at).toLocaleDateString()}</span>
                </div>
                {org.admin_notes && (
                  <div className="mt-2 p-2 bg-slate-800 rounded-lg text-slate-400 text-xs">{org.admin_notes}</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Edit Subscription Modal ─────────────────────────────────────────────── */
function EditSubscriptionModal({ org, onClose, onSaved }) {
  const today = new Date().toISOString().split('T')[0];
  const plus30 = new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0];

  const [form, setForm] = useState({
    plan: org.plan || 'trial',
    extra_branches: org.extra_branches || 0,
    trial_days: '',
    subscription_expires_at: org.subscription_expires_at
      ? org.subscription_expires_at.split('T')[0]
      : plus30,
    notes: org.admin_notes || '',
  });
  const [loading, setLoading] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Auto-set 30-day expiry when switching to a paid plan
  const handlePlanChange = (newPlan) => {
    set('plan', newPlan);
    if (['basic', 'standard', 'pro'].includes(newPlan) && !org.subscription_expires_at) {
      set('subscription_expires_at', plus30);
    }
  };

  const setQuickExpiry = (days) => {
    const d = new Date(Date.now() + days * 86400000).toISOString().split('T')[0];
    set('subscription_expires_at', d);
  };

  const daysUntilExpiry = form.subscription_expires_at
    ? Math.ceil((new Date(form.subscription_expires_at) - new Date()) / 86400000)
    : null;

  const handleSave = async () => {
    setLoading(true);
    try {
      const payload = {
        plan: form.plan,
        extra_branches: parseInt(form.extra_branches) || 0,
        notes: form.notes,
      };
      if (form.trial_days && parseInt(form.trial_days) > 0)
        payload.trial_days = parseInt(form.trial_days);
      if (['basic', 'standard', 'pro'].includes(form.plan))
        payload.subscription_expires_at = form.subscription_expires_at || null;
      if (form.plan === 'founders')
        payload.subscription_expires_at = null;

      const r = await api.put(`/superadmin/organizations/${org.id}/subscription`, payload);
      onSaved(r.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed');
    }
    setLoading(false);
  };

  const isPaidPlan = ['basic', 'standard', 'pro'].includes(form.plan);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-white font-bold text-lg">Edit Subscription</h3>
            <p className="text-slate-400 text-sm">{org.name}</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
        </div>

        <div className="space-y-5">
          {/* Plan selector */}
          <div>
            <label className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2 block">Plan</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { key: 'trial',    label: 'Trial',    color: 'blue' },
                { key: 'basic',    label: 'Basic',    color: 'slate' },
                { key: 'standard', label: 'Standard', color: 'emerald' },
                { key: 'pro',      label: 'Pro',      color: 'indigo' },
                { key: 'founders', label: '★ Founders', color: 'amber', special: true },
                { key: 'suspended',label: 'Suspend',  color: 'red' },
              ].map(p => (
                <button key={p.key} onClick={() => handlePlanChange(p.key)}
                  className={`py-2.5 rounded-xl text-xs font-semibold border transition-all ${
                    form.plan === p.key
                      ? p.special
                        ? 'border-amber-400 bg-amber-400/15 text-amber-300'
                        : 'border-emerald-500 bg-emerald-500/10 text-emerald-300'
                      : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>

            {/* Founders info */}
            {form.plan === 'founders' && (
              <div className="mt-2 bg-amber-400/10 border border-amber-400/30 rounded-xl px-4 py-3 flex items-start gap-2">
                <span className="text-amber-300 text-lg">★</span>
                <div>
                  <p className="text-amber-300 text-xs font-semibold">Founders Plan — Lifetime Access</p>
                  <p className="text-amber-400/70 text-xs mt-0.5">All Pro features, never expires. Reserved for early adopters and special accounts.</p>
                </div>
              </div>
            )}
          </div>

          {/* Subscription expiry — paid plans only */}
          {isPaidPlan && (
            <div>
              <label className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2 block">
                Subscription Expires On
              </label>

              {/* Quick buttons */}
              <div className="flex gap-1.5 mb-2 flex-wrap">
                {[
                  { label: '30 days', days: 30 },
                  { label: '60 days', days: 60 },
                  { label: '90 days', days: 90 },
                  { label: '6 months', days: 180 },
                  { label: '1 year', days: 365 },
                ].map(({ label, days }) => (
                  <button key={days} onClick={() => setQuickExpiry(days)}
                    className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-emerald-600 text-slate-400 hover:text-white border border-slate-700 hover:border-emerald-500 rounded-lg transition-all">
                    +{label}
                  </button>
                ))}
              </div>

              <Input value={form.subscription_expires_at}
                onChange={e => set('subscription_expires_at', e.target.value)}
                type="date"
                className="bg-slate-800 border-slate-700 text-white h-10 text-sm" />

              {/* Expiry preview */}
              {daysUntilExpiry !== null && (
                <div className={`mt-2 text-xs flex items-center gap-1.5 ${
                  daysUntilExpiry <= 0 ? 'text-red-400' :
                  daysUntilExpiry <= 7 ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  <Clock size={12} />
                  {daysUntilExpiry <= 0
                    ? 'This date is in the past — plan will be in grace period'
                    : `Expires in ${daysUntilExpiry} days (${new Date(form.subscription_expires_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })})`
                  }
                </div>
              )}
            </div>
          )}

          {/* Trial extension */}
          {form.plan === 'trial' && (
            <div>
              <label className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2 block">
                Extend Trial By (days)
              </label>
              <div className="flex gap-1.5 mb-2">
                {[7, 14, 30].map(d => (
                  <button key={d} onClick={() => set('trial_days', d)}
                    className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-blue-600/50 text-slate-400 hover:text-white border border-slate-700 rounded-lg transition-all">
                    +{d} days
                  </button>
                ))}
              </div>
              <Input value={form.trial_days} onChange={e => set('trial_days', e.target.value)}
                type="number" min="1" placeholder="Custom days (e.g. 14)"
                className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-600 h-9 text-sm" />
              {org.trial_ends_at && (
                <p className="text-slate-500 text-xs mt-1">
                  Current trial ends: {new Date(org.trial_ends_at).toLocaleDateString()}
                </p>
              )}
            </div>
          )}

          {/* Extra branches — not for founders */}
          {!['founders', 'suspended', 'trial'].includes(form.plan) && (
            <div>
              <label className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2 block">
                Extra Branch Add-ons <span className="text-slate-600 normal-case font-normal">(₱1,500/mo each)</span>
              </label>
              <div className="flex items-center gap-3">
                <button onClick={() => set('extra_branches', Math.max(0, form.extra_branches - 1))}
                  className="w-9 h-9 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white flex items-center justify-center">
                  <Minus size={14} />
                </button>
                <span className="text-white font-bold text-xl w-8 text-center">{form.extra_branches}</span>
                <button onClick={() => set('extra_branches', form.extra_branches + 1)}
                  className="w-9 h-9 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white flex items-center justify-center">
                  <Plus size={14} />
                </button>
                <span className="text-slate-500 text-xs">
                  = {(PLAN_LIMITS_MAP[form.plan] || 1) + form.extra_branches} total branches
                </span>
              </div>
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2 block">Admin Notes</label>
            <Input value={form.notes} onChange={e => set('notes', e.target.value)}
              placeholder="Internal notes (not visible to customer)"
              className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-600 h-9 text-sm" />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <Button onClick={handleSave} disabled={loading}
            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold h-10">
            {loading ? 'Saving...' : 'Save Changes'}
          </Button>
          <Button variant="outline" onClick={onClose}
            className="border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 h-10">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

const PLAN_LIMITS_MAP = { trial: 5, basic: 1, standard: 2, pro: 5, founders: 0, suspended: 0 };

/* ── Feature Flags Panel ────────────────────────────────────────────────── */
function FeatureFlagsPanel() {
  const [defs, setDefs] = useState([]);
  const [flags, setFlags] = useState({ basic: {}, standard: {}, pro: {} });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    api.get('/superadmin/settings/features').then(r => {
      setDefs(r.data.feature_definitions || []);
      setFlags(r.data.flags || { basic: {}, standard: {}, pro: {} });
      setLastUpdated(r.data.last_updated);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const toggle = (plan, featureKey) => {
    if (plan === 'trial') return; // Trial always mirrors Pro - read-only
    setFlags(prev => ({
      ...prev,
      [plan]: { ...prev[plan], [featureKey]: !prev[plan]?.[featureKey] },
    }));
    setHasChanges(true);
  };

  const setAll = (plan, value) => {
    if (plan === 'trial') return;
    const locked = defs.filter(d => d.locked_on?.includes(plan)).map(d => d.key);
    setFlags(prev => ({
      ...prev,
      [plan]: {
        ...prev[plan],
        ...Object.fromEntries(defs.map(d => [d.key, locked.includes(d.key) ? true : value])),
      },
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/superadmin/settings/features', { flags });
      setHasChanges(false);
      setLastUpdated(new Date().toISOString());
      toast.success('Feature flags saved! Landing page updated live.');
    } catch {
      toast.error('Failed to save feature flags');
    }
    setSaving(false);
  };

  const categories = [...new Set(defs.map(d => d.category))];
  const PLANS = [
    { key: 'basic', label: 'Basic', color: '#64748b', price: '₱1,500' },
    { key: 'standard', label: 'Standard', color: '#10b981', price: '₱4,000' },
    { key: 'pro', label: 'Pro', color: '#6366f1', price: '₱7,500' },
  ];

  if (loading) return <div className="text-center py-12 text-slate-500">Loading feature flags...</div>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-white font-bold text-lg">Feature Flags</h2>
          <p className="text-slate-400 text-sm">
            Control which features are available per plan. Changes are live immediately on the pricing page.
            {lastUpdated && <span className="text-slate-600 ml-2">Last saved: {new Date(lastUpdated).toLocaleString()}</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && (
            <span className="text-amber-400 text-xs flex items-center gap-1">
              <AlertTriangle size={12} /> Unsaved changes
            </span>
          )}
          <Button onClick={handleSave} disabled={saving || !hasChanges}
            className={`gap-2 font-semibold ${hasChanges ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-slate-700 text-slate-400 cursor-not-allowed'}`}>
            <Save size={14} /> {saving ? 'Saving...' : 'Save & Publish'}
          </Button>
        </div>
      </div>

      {/* Trial + founders note */}
      <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl px-4 py-3 text-blue-300 text-xs flex items-start gap-2">
        <Shield size={14} className="mt-0.5 shrink-0" />
        <span>
          <strong>Trial</strong> and <strong className="text-amber-300">★ Founders</strong> plans always mirror Pro (all features unlocked) — this cannot be changed.
        </span>
      </div>

      {/* Feature table */}
      <div className="bg-slate-800/20 border border-slate-700/40 rounded-2xl overflow-hidden">
        {/* Column headers */}
        <div className="grid border-b border-slate-700/40" style={{ gridTemplateColumns: '1fr repeat(3, 160px)' }}>
          <div className="px-5 py-4 text-slate-400 text-xs font-semibold uppercase tracking-wider">Feature</div>
          {PLANS.map(p => (
            <div key={p.key} className="px-4 py-4 text-center border-l border-slate-700/30">
              <div className="font-bold text-sm" style={{ color: p.color }}>{p.label}</div>
              <div className="text-slate-500 text-xs">{p.price}/mo</div>
              <div className="flex gap-1.5 justify-center mt-2">
                <button onClick={() => setAll(p.key, true)}
                  className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-emerald-600 text-slate-400 hover:text-white rounded transition-colors">
                  All On
                </button>
                <button onClick={() => setAll(p.key, false)}
                  className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-red-600 text-slate-400 hover:text-white rounded transition-colors">
                  All Off
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Features grouped by category */}
        {categories.map(cat => (
          <div key={cat}>
            {/* Category header */}
            <div className="px-5 py-2.5 bg-slate-900/40 border-b border-slate-700/30">
              <span className="text-slate-400 text-xs font-semibold uppercase tracking-widest">{cat}</span>
            </div>
            {defs.filter(d => d.category === cat).map((feature, idx, arr) => {
              const isLast = idx === arr.length - 1;
              return (
                <div key={feature.key}
                  className={`grid items-center hover:bg-slate-800/30 transition-colors ${!isLast ? 'border-b border-slate-700/20' : ''}`}
                  style={{ gridTemplateColumns: '1fr repeat(3, 160px)' }}>
                  {/* Feature info */}
                  <div className="px-5 py-3.5">
                    <div className="text-slate-200 text-sm font-medium">{feature.name}</div>
                    <div className="text-slate-500 text-xs mt-0.5 leading-relaxed">{feature.description}</div>
                  </div>
                  {/* Toggle per plan */}
                  {PLANS.map(p => {
                    const isLocked = feature.locked_on?.includes(p.key);
                    const enabled = isLocked ? true : (flags[p.key]?.[feature.key] ?? false);
                    return (
                      <div key={p.key} className="px-4 py-3.5 flex justify-center border-l border-slate-700/20">
                        <button
                          data-testid={`toggle-${p.key}-${feature.key}`}
                          onClick={() => !isLocked && toggle(p.key, feature.key)}
                          disabled={isLocked}
                          title={isLocked ? 'This feature is always included' : (enabled ? 'Click to disable' : 'Click to enable')}
                          className={`relative w-11 h-6 rounded-full transition-all focus:outline-none ${
                            isLocked
                              ? 'opacity-50 cursor-not-allowed'
                              : 'cursor-pointer'
                          } ${enabled ? 'bg-emerald-500' : 'bg-slate-700'}`}
                        >
                          <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${enabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </button>
                        {isLocked && <span className="ml-2 text-xs text-slate-600">always</span>}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Preview note */}
      <div className="bg-slate-800/30 border border-slate-700/40 rounded-xl px-4 py-3 text-slate-400 text-xs">
        <strong className="text-slate-300">How it works:</strong> When you save, the pricing page ({window.location.origin}) and feature comparison table update instantly — no code changes needed.
        Customers on active plans see the features their plan currently has. Changes don't revoke access mid-subscription.
      </div>
    </div>
  );
}

/* ── Payment Settings Panel ─────────────────────────────────────────────── */
function PaymentSettingsPanel({ settings, setSettings, saving, setSaving }) {
  const fileRefs = { gcash: useRef(), maya: useRef(), bank: useRef(), paypal: useRef() };

  const update = (method, key, value) => {
    setSettings(prev => ({
      ...prev,
      [method]: { ...(prev[method] || {}), [key]: value }
    }));
  };

  const handleFileUpload = (method, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { toast.error('File too large. Max 2MB.'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => update(method, 'qr_base64', ev.target.result);
    reader.readAsDataURL(file);
  };

  const removeQR = (method) => update(method, 'qr_base64', '');

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/superadmin/settings/payment', { value: settings });
      toast.success('Payment settings saved!');
    } catch {
      toast.error('Failed to save settings');
    }
    setSaving(false);
  };

  const METHODS = [
    { key: 'gcash', label: 'GCash', icon: '💚', color: 'emerald', fields: [
      { field: 'number', label: 'GCash Number', placeholder: '09XX-XXX-XXXX' },
      { field: 'account_name', label: 'Account Name', placeholder: 'Full name on account' },
    ]},
    { key: 'maya', label: 'Maya', icon: '💜', color: 'purple', fields: [
      { field: 'number', label: 'Maya Number', placeholder: '09XX-XXX-XXXX' },
      { field: 'account_name', label: 'Account Name', placeholder: 'Full name on account' },
    ]},
    { key: 'bank', label: 'Bank Transfer', icon: '🏦', color: 'blue', fields: [
      { field: 'bank_name', label: 'Bank Name', placeholder: 'e.g. BDO, BPI, UnionBank' },
      { field: 'account_number', label: 'Account Number', placeholder: 'XXXX-XXXX-XXXX' },
      { field: 'account_name', label: 'Account Name', placeholder: 'Business name on account' },
    ]},
    { key: 'paypal', label: 'PayPal', icon: '🔵', color: 'indigo', fields: [
      { field: 'email', label: 'PayPal Email', placeholder: 'paypal@email.com' },
      { field: 'link', label: 'PayPal.me Link', placeholder: 'https://paypal.me/yourlink' },
    ]},
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-bold text-lg">Payment Methods</h2>
          <p className="text-slate-400 text-sm">Configure how customers pay for subscriptions. QR codes appear on the Upgrade page.</p>
        </div>
        <Button onClick={handleSave} disabled={saving}
          className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold gap-2">
          <Save size={14} /> {saving ? 'Saving...' : 'Save All'}
        </Button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {METHODS.map(({ key, label, icon, fields }) => (
          <div key={key} className="bg-slate-800/30 border border-slate-700/40 rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{icon}</span>
              <h3 className="text-white font-semibold">{label}</h3>
            </div>

            {/* Text fields */}
            {fields.map(({ field, label: fLabel, placeholder }) => (
              <div key={field}>
                <label className="text-slate-400 text-xs font-medium mb-1.5 block">{fLabel}</label>
                <Input
                  value={settings[key]?.[field] || ''}
                  onChange={e => update(key, field, e.target.value)}
                  placeholder={placeholder}
                  className="bg-slate-900 border-slate-700 text-white placeholder:text-slate-600 h-9 text-sm"
                />
              </div>
            ))}

            {/* QR code upload */}
            <div>
              <label className="text-slate-400 text-xs font-medium mb-2 block">QR Code Image</label>
              {settings[key]?.qr_base64 ? (
                <div className="relative inline-block">
                  <img src={settings[key].qr_base64} alt={`${label} QR`}
                    className="w-32 h-32 rounded-xl border border-slate-600 object-contain bg-white p-1" />
                  <button onClick={() => removeQR(key)}
                    className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center">
                    <Trash2 size={11} className="text-white" />
                  </button>
                  <button onClick={() => fileRefs[key]?.current?.click()}
                    className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-slate-700 hover:bg-slate-600 text-xs text-white px-2 py-0.5 rounded-full whitespace-nowrap">
                    Change
                  </button>
                </div>
              ) : (
                <button onClick={() => fileRefs[key]?.current?.click()}
                  className="w-32 h-32 border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-emerald-400 transition-colors group">
                  <Upload size={20} />
                  <span className="text-xs">Upload QR</span>
                </button>
              )}
              <input ref={fileRefs[key]} type="file" accept="image/*" className="hidden"
                onChange={e => handleFileUpload(key, e)} />
              <p className="text-slate-600 text-xs mt-2">PNG/JPG · Max 2MB</p>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
        <p className="text-blue-300 text-sm font-medium mb-1">How this works</p>
        <p className="text-blue-400/70 text-xs leading-relaxed">
          Customers see these payment details when they click "Upgrade" in the app. They send payment manually,
          then contact you for activation. You then activate their plan from this admin panel.
        </p>
      </div>
    </div>
  );
}
