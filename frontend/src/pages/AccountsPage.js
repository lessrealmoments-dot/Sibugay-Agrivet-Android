import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { formatPHP } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import { Plus, KeyRound, Edit2, Shield, User, Building2, AlertTriangle, Lock, Unlock, Search } from 'lucide-react';
import { toast } from 'sonner';

const ROLES = [
  { key: 'admin', label: 'Administrator', color: 'bg-purple-100 text-purple-700' },
  { key: 'manager', label: 'Branch Manager', color: 'bg-blue-100 text-blue-700' },
  { key: 'cashier', label: 'Cashier', color: 'bg-green-100 text-green-700' },
  { key: 'inventory', label: 'Inventory Clerk', color: 'bg-orange-100 text-orange-700' },
];

const BLANK_FORM = {
  username: '', full_name: '', email: '', role: 'cashier',
  branch_id: '', password: '', confirm_password: '', manager_pin: ''
};

export default function AccountsPage() {
  const { user: currentUser, branches } = useAuth();
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [userDialog, setUserDialog] = useState(false);
  const [pinDialog, setPinDialog] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [pinTarget, setPinTarget] = useState(null);
  const [form, setForm] = useState(BLANK_FORM);
  const [pinForm, setPinForm] = useState({ pin: '', confirm: '' });
  const [saving, setSaving] = useState(false);

  const isAdmin = currentUser?.role === 'admin';

  const fetchUsers = async () => {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch { toast.error('Failed to load users'); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const filteredUsers = users.filter(u =>
    !search || u.full_name?.toLowerCase().includes(search.toLowerCase()) ||
    u.username?.toLowerCase().includes(search.toLowerCase()) ||
    u.role?.toLowerCase().includes(search.toLowerCase())
  );

  const openCreate = () => {
    setEditingUser(null);
    setForm(BLANK_FORM);
    setUserDialog(true);
  };

  const openEdit = (u) => {
    setEditingUser(u);
    setForm({
      username: u.username, full_name: u.full_name || '', email: u.email || '',
      role: u.role || 'cashier', branch_id: u.branch_id || '',
      password: '', confirm_password: '', manager_pin: ''
    });
    setUserDialog(true);
  };

  const openPinDialog = (u) => {
    setPinTarget(u);
    setPinForm({ pin: '', confirm: '' });
    setPinDialog(true);
  };

  const handleSave = async () => {
    if (!form.username.trim()) { toast.error('Username is required'); return; }
    if (!editingUser && !form.password) { toast.error('Password is required for new users'); return; }
    if (form.password && form.password !== form.confirm_password) {
      toast.error('Passwords do not match'); return;
    }
    if (form.manager_pin && form.manager_pin.length < 4) {
      toast.error('Manager PIN must be at least 4 digits'); return;
    }
    setSaving(true);
    try {
      const payload = {
        username: form.username, full_name: form.full_name, email: form.email,
        role: form.role, branch_id: form.branch_id || null,
      };
      if (form.password) payload.password = form.password;

      let savedUser;
      if (editingUser) {
        const res = await api.put(`/users/${editingUser.id}`, payload);
        savedUser = res.data;
        toast.success(`${form.full_name || form.username} updated`);
      } else {
        const res = await api.post('/users', payload);
        savedUser = res.data;
        toast.success(`User ${form.username} created`);
      }

      // Set PIN if provided
      if (form.manager_pin && savedUser?.id) {
        await api.put(`/users/${savedUser.id}/pin`, { pin: form.manager_pin });
        toast.success('Manager PIN set');
      }

      setUserDialog(false);
      fetchUsers();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save user');
    }
    setSaving(false);
  };

  const handleSetPin = async () => {
    if (pinForm.pin && pinForm.pin.length < 4) { toast.error('PIN must be at least 4 digits'); return; }
    if (pinForm.pin && pinForm.pin !== pinForm.confirm) { toast.error('PINs do not match'); return; }
    try {
      await api.put(`/users/${pinTarget.id}/pin`, { pin: pinForm.pin });
      toast.success(pinForm.pin ? `PIN set for ${pinTarget.full_name || pinTarget.username}` : 'PIN cleared');
      setPinDialog(false);
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to set PIN'); }
  };

  const toggleActive = async (u) => {
    if (u.id === currentUser?.id) { toast.error("Can't deactivate your own account"); return; }
    try {
      await api.put(`/users/${u.id}`, { active: !u.active });
      toast.success(`${u.full_name || u.username} ${u.active ? 'deactivated' : 'activated'}`);
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const getRoleBadge = (role) => {
    const r = ROLES.find(x => x.key === role);
    return r ? <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${r.color}`}>{r.label}</span>
      : <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-600">{role}</span>;
  };

  const getBranchName = (id) => branches.find(b => b.id === id)?.name || (id ? 'Unknown' : 'All Branches');

  const avatarColors = { admin: 'bg-purple-600', manager: 'bg-blue-600', cashier: 'bg-green-600', inventory: 'bg-orange-500' };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="accounts-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Accounts</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage system users, roles, and manager PINs</p>
        </div>
        {isAdmin && (
          <Button onClick={openCreate} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white gap-2" data-testid="create-user-btn">
            <Plus size={16} /> New User
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {ROLES.map(r => {
          const count = users.filter(u => u.role === r.key && u.active !== false).length;
          return (
            <Card key={r.key} className="border-slate-200">
              <CardContent className="p-3 flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${avatarColors[r.key] || 'bg-slate-600'}`}>
                  <User size={15} className="text-white" />
                </div>
                <div>
                  <p className="text-xl font-bold">{count}</p>
                  <p className="text-xs text-slate-500">{r.label}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative w-80">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input className="pl-9 h-9" placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {/* Users Table */}
      <Card className="border-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">User</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Role</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Branch</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">PIN</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Status</th>
                <th className="px-4 py-3 text-xs font-medium text-slate-500 uppercase text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map(u => (
                <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold ${avatarColors[u.role] || 'bg-slate-500'}`}>
                        {(u.full_name?.[0] || u.username?.[0] || 'U').toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-slate-800">{u.full_name || u.username}</p>
                        <p className="text-xs text-slate-400">@{u.username}</p>
                        {u.email && <p className="text-xs text-slate-400">{u.email}</p>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">{getRoleBadge(u.role)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-slate-600 text-xs">
                      <Building2 size={12} />
                      {getBranchName(u.branch_id)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {u.manager_pin ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-600">
                        <Lock size={11} /> Set
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-slate-400">
                        <Unlock size={11} /> Not set
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={u.active !== false ? 'default' : 'secondary'} className={`text-[10px] ${u.active !== false ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-500'}`}>
                      {u.active !== false ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      {isAdmin && (
                        <>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-slate-400 hover:text-slate-700" onClick={() => openEdit(u)} title="Edit user">
                            <Edit2 size={14} />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-slate-400 hover:text-amber-600" onClick={() => openPinDialog(u)} title="Set manager PIN">
                            <KeyRound size={14} />
                          </Button>
                          {u.id !== currentUser?.id && (
                            <Button variant="ghost" size="sm" className={`h-8 w-8 p-0 ${u.active !== false ? 'text-slate-400 hover:text-red-500' : 'text-slate-400 hover:text-green-600'}`}
                              onClick={() => toggleActive(u)} title={u.active !== false ? 'Deactivate' : 'Activate'}>
                              {u.active !== false ? <Lock size={14} /> : <Unlock size={14} />}
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-12 text-center text-slate-400">No users found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create/Edit User Dialog */}
      <Dialog open={userDialog} onOpenChange={setUserDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>{editingUser ? 'Edit User' : 'Create New User'}</DialogTitle>
            <DialogDescription>
              {editingUser ? `Editing account for @${editingUser.username}` : 'Create a new system account'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Username *</Label>
                <Input value={form.username} onChange={e => setForm({...form, username: e.target.value})}
                  placeholder="e.g. cashier01" className="h-9" disabled={!!editingUser} data-testid="user-username" />
              </div>
              <div>
                <Label className="text-xs">Full Name</Label>
                <Input value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})}
                  placeholder="Juan dela Cruz" className="h-9" data-testid="user-fullname" />
              </div>
            </div>
            <div>
              <Label className="text-xs">Email</Label>
              <Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})}
                placeholder="user@example.com" className="h-9" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Role *</Label>
                <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                  <SelectTrigger className="h-9" data-testid="user-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ROLES.map(r => <SelectItem key={r.key} value={r.key}>{r.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Branch Assignment</Label>
                <Select value={form.branch_id || 'all'} onValueChange={v => setForm({...form, branch_id: v === 'all' ? '' : v})}>
                  <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Branches (Admin)</SelectItem>
                    {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Separator />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">{editingUser ? 'New Password (leave blank to keep)' : 'Password *'}</Label>
                <Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})}
                  placeholder="Min. 6 characters" className="h-9" data-testid="user-password" />
              </div>
              <div>
                <Label className="text-xs">Confirm Password</Label>
                <Input type="password" value={form.confirm_password} onChange={e => setForm({...form, confirm_password: e.target.value})}
                  placeholder="Repeat password" className="h-9" />
              </div>
            </div>
            {(form.role === 'admin' || form.role === 'manager') && (
              <div>
                <Label className="text-xs flex items-center gap-1">
                  <KeyRound size={11} /> Manager PIN (4-6 digits, optional)
                </Label>
                <Input type="password" value={form.manager_pin} onChange={e => setForm({...form, manager_pin: e.target.value})}
                  placeholder="Used for credit sale approvals" className="h-9 tracking-widest text-center"
                  maxLength={6} data-testid="user-pin" />
                <p className="text-[10px] text-slate-400 mt-1">Admins auto-approve credit sales. PINs are for when they hand control to a cashier.</p>
              </div>
            )}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1" onClick={() => setUserDialog(false)}>Cancel</Button>
              <Button className="flex-1 bg-[#1A4D2E] hover:bg-[#14532d] text-white" onClick={handleSave} disabled={saving} data-testid="save-user-btn">
                {saving ? 'Saving...' : (editingUser ? 'Save Changes' : 'Create User')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Set PIN Dialog */}
      <Dialog open={pinDialog} onOpenChange={setPinDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }} className="flex items-center gap-2">
              <KeyRound size={18} className="text-amber-500" /> Manager PIN
            </DialogTitle>
            <DialogDescription>
              Set or clear the PIN for <strong>{pinTarget?.full_name || pinTarget?.username}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-xs text-amber-700">
                Manager PINs are used to approve credit sales, over-limit cash advances, and other actions requiring authorization.
                Admins always auto-approve — PINs are for branch managers/cashiers.
              </p>
            </div>
            <div>
              <Label className="text-xs">New PIN (4-6 digits)</Label>
              <Input type="password" value={pinForm.pin} onChange={e => setPinForm({...pinForm, pin: e.target.value})}
                placeholder="Leave blank to clear PIN" className="h-10 text-center text-2xl tracking-widest"
                maxLength={6} data-testid="pin-input" />
            </div>
            {pinForm.pin && (
              <div>
                <Label className="text-xs">Confirm PIN</Label>
                <Input type="password" value={pinForm.confirm} onChange={e => setPinForm({...pinForm, confirm: e.target.value})}
                  placeholder="Repeat PIN" className="h-10 text-center text-2xl tracking-widest" maxLength={6} />
              </div>
            )}
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setPinDialog(false)}>Cancel</Button>
              {pinTarget?.manager_pin && !pinForm.pin && (
                <Button variant="outline" className="text-red-600 border-red-200 hover:bg-red-50" onClick={handleSetPin}>
                  Clear PIN
                </Button>
              )}
              <Button className="flex-1 bg-amber-500 hover:bg-amber-600 text-white" onClick={handleSetPin} data-testid="set-pin-btn">
                {pinForm.pin ? 'Set PIN' : 'Save'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
