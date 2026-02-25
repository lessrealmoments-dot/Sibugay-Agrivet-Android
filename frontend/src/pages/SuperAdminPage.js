import { useState, useEffect, useCallback } from 'react';
import { api, useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import {
  Building2, Users, BarChart3, Shield, RefreshCw, ArrowLeft,
  CheckCircle, AlertTriangle, XCircle, ChevronDown, ChevronUp, Search
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

const PLAN_COLORS = {
  trial: 'bg-blue-100 text-blue-700',
  basic: 'bg-slate-100 text-slate-700',
  standard: 'bg-emerald-100 text-emerald-700',
  pro: 'bg-indigo-100 text-indigo-700',
  suspended: 'bg-red-100 text-red-700',
};

export default function SuperAdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expandedOrg, setExpandedOrg] = useState(null);
  const [editingOrg, setEditingOrg] = useState(null);
  const [editForm, setEditForm] = useState({});

  const load = useCallback(async () => {
    if (!user?.is_super_admin) { navigate('/dashboard'); return; }
    setLoading(true);
    try {
      const [statsRes, orgsRes] = await Promise.all([
        api.get('/superadmin/stats'),
        api.get('/superadmin/organizations'),
      ]);
      setStats(statsRes.data);
      setOrgs(orgsRes.data);
    } catch (err) {
      if (err.response?.status === 403) navigate('/dashboard');
    }
    setLoading(false);
  }, [navigate, user]);

  useEffect(() => { load(); }, [load]);

  if (!user?.is_super_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F5F5F0]">
        <div className="text-center">
          <Shield size={48} className="text-red-400 mx-auto mb-3" />
          <h2 className="text-lg font-semibold text-slate-700">Access Denied</h2>
          <p className="text-slate-500 text-sm mt-1">Super admin access required</p>
          <Button className="mt-4" onClick={() => navigate('/dashboard')}>Go to Dashboard</Button>
        </div>
      </div>
    );
  }

  const filtered = orgs.filter(o =>
    o.name.toLowerCase().includes(search.toLowerCase()) ||
    o.owner_email?.toLowerCase().includes(search.toLowerCase())
  );

  const startEdit = (org) => {
    setEditingOrg(org.id);
    setEditForm({
      plan: org.plan,
      extra_branches: org.extra_branches || 0,
      trial_days: '',
      notes: org.admin_notes || '',
    });
  };

  const saveEdit = async (orgId) => {
    try {
      const payload = {};
      if (editForm.plan) payload.plan = editForm.plan;
      if (editForm.extra_branches !== '') payload.extra_branches = parseInt(editForm.extra_branches);
      if (editForm.trial_days) payload.trial_days = parseInt(editForm.trial_days);
      if (editForm.notes) payload.notes = editForm.notes;

      await api.put(`/superadmin/organizations/${orgId}/subscription`, payload);
      toast.success('Subscription updated');
      setEditingOrg(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed');
    }
  };

  const StatusIcon = ({ status }) => {
    if (status === 'active') return <CheckCircle size={14} className="text-emerald-500" />;
    if (status === 'trial') return <AlertTriangle size={14} className="text-blue-500" />;
    return <XCircle size={14} className="text-red-400" />;
  };

  return (
    <div className="min-h-screen bg-[#F5F5F0] p-6" style={{ fontFamily: 'Manrope, sans-serif' }}>
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate('/dashboard')} className="text-slate-400 hover:text-slate-600">
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Platform Admin</h1>
              <p className="text-slate-500 text-sm">Manage all organizations and subscriptions</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={load} className="gap-2">
            <RefreshCw size={14} />Refresh
          </Button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {[
              { label: "Total Orgs", value: stats.total_organizations, icon: Building2, color: "slate" },
              { label: "On Trial", value: stats.trial, icon: AlertTriangle, color: "blue" },
              { label: "Active Paid", value: stats.active, icon: CheckCircle, color: "emerald" },
              { label: "Suspended", value: stats.suspended, icon: XCircle, color: "red" },
              { label: "Total Users", value: stats.total_users, icon: Users, color: "indigo" },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="bg-white rounded-2xl p-4 border border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-slate-500 text-xs font-medium">{label}</span>
                  <Icon size={16} className={`text-${color}-500`} />
                </div>
                <div className="text-2xl font-bold text-slate-900">{value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Plan breakdown */}
        {stats?.by_plan && (
          <div className="bg-white rounded-2xl border border-slate-200 p-5 mb-6">
            <h3 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
              <BarChart3 size={16} className="text-slate-500" /> Plan Breakdown
            </h3>
            <div className="flex gap-4">
              {Object.entries(stats.by_plan).map(([plan, count]) => (
                <div key={plan} className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PLAN_COLORS[plan] || 'bg-slate-100 text-slate-700'}`}>
                    {plan}
                  </span>
                  <span className="text-sm font-bold text-slate-700">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search */}
        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by company name or email..."
            className="pl-9 bg-white border-slate-200"
          />
        </div>

        {/* Organizations list */}
        <div className="space-y-3">
          {loading ? (
            <div className="text-center py-12 text-slate-400">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-400">No organizations found</div>
          ) : filtered.map(org => (
            <div key={org.id} data-testid={`org-row-${org.id}`}
              className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="flex items-center p-4 gap-4">
                <div className="w-10 h-10 bg-slate-100 rounded-xl flex items-center justify-center shrink-0">
                  <Building2 size={18} className="text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-900">{org.name}</span>
                    {org.is_default && <Badge variant="outline" className="text-xs">Default</Badge>}
                    {org.is_demo && <Badge variant="outline" className="text-xs bg-blue-50 text-blue-600">Demo</Badge>}
                  </div>
                  <div className="text-slate-500 text-xs mt-0.5">{org.owner_email}</div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusIcon status={org.subscription_status} />
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PLAN_COLORS[org.effective_plan || org.plan] || 'bg-slate-100 text-slate-700'}`}>
                    {org.effective_plan || org.plan}
                  </span>
                  <span className="text-xs text-slate-400 hidden md:block">
                    {org.branch_count}b · {org.user_count}u
                  </span>
                  <button onClick={() => setExpandedOrg(expandedOrg === org.id ? null : org.id)}
                    className="text-slate-400 hover:text-slate-600">
                    {expandedOrg === org.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </button>
                </div>
              </div>

              {expandedOrg === org.id && (
                <div className="border-t border-slate-100 p-4 bg-slate-50">
                  {editingOrg === org.id ? (
                    <div className="space-y-3">
                      <h4 className="font-semibold text-slate-800 text-sm">Edit Subscription</h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <label className="text-xs text-slate-500 mb-1 block">Plan</label>
                          <select
                            value={editForm.plan}
                            onChange={e => setEditForm(f => ({ ...f, plan: e.target.value }))}
                            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                          >
                            {['trial', 'basic', 'standard', 'pro', 'suspended'].map(p => (
                              <option key={p} value={p}>{p}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="text-xs text-slate-500 mb-1 block">Extra Branches</label>
                          <Input
                            type="number" min="0"
                            value={editForm.extra_branches}
                            onChange={e => setEditForm(f => ({ ...f, extra_branches: e.target.value }))}
                            className="text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500 mb-1 block">Extend Trial (days)</label>
                          <Input
                            type="number" min="1" placeholder="e.g. 14"
                            value={editForm.trial_days}
                            onChange={e => setEditForm(f => ({ ...f, trial_days: e.target.value }))}
                            className="text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-500 mb-1 block">Admin Notes</label>
                          <Input
                            value={editForm.notes}
                            onChange={e => setEditForm(f => ({ ...f, notes: e.target.value }))}
                            placeholder="Internal notes"
                            className="text-sm"
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => saveEdit(org.id)}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white">Save Changes</Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingOrg(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="space-y-1.5 text-sm">
                        <div><span className="text-slate-500">Plan:</span> <strong className="text-slate-800">{org.plan}</strong> (effective: {org.effective_plan})</div>
                        <div><span className="text-slate-500">Status:</span> <strong className="text-slate-800">{org.subscription_status}</strong></div>
                        {org.trial_ends_at && (
                          <div><span className="text-slate-500">Trial ends:</span> <strong className="text-slate-800">{new Date(org.trial_ends_at).toLocaleDateString()}</strong></div>
                        )}
                        <div><span className="text-slate-500">Max branches:</span> <strong className="text-slate-800">{org.max_branches}</strong> · Extra: {org.extra_branches || 0}</div>
                        <div><span className="text-slate-500">Created:</span> <strong className="text-slate-800">{new Date(org.created_at).toLocaleDateString()}</strong></div>
                        {org.admin_notes && <div><span className="text-slate-500">Notes:</span> {org.admin_notes}</div>}
                      </div>
                      <Button size="sm" variant="outline" onClick={() => startEdit(org)}>
                        Edit Subscription
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
