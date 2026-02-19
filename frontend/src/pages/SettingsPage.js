import { useState, useEffect } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Settings, Plus, Shield, Key } from 'lucide-react';
import { toast } from 'sonner';

const PERMISSION_MODULES = [
  { key: 'branches', label: 'Branches', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'products', label: 'Products', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'inventory', label: 'Inventory', actions: ['view', 'adjust', 'transfer'] },
  { key: 'pos', label: 'POS', actions: ['view', 'sell', 'void'] },
  { key: 'customers', label: 'Customers', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'price_schemes', label: 'Price Schemes', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'accounting', label: 'Accounting', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'reports', label: 'Reports', actions: ['view', 'export'] },
  { key: 'settings', label: 'Settings', actions: ['view', 'manage_users', 'manage_roles'] },
];

export default function SettingsPage() {
  const { user: currentUser, branches } = useAuth();
  const [users, setUsers] = useState([]);
  const [createDialog, setCreateDialog] = useState(false);
  const [permDialog, setPermDialog] = useState(false);
  const [resetPwDialog, setResetPwDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [perms, setPerms] = useState({});
  const [newPw, setNewPw] = useState('');
  const [createForm, setCreateForm] = useState({ username: '', full_name: '', email: '', password: '', role: 'cashier', branch_id: '' });

  const fetchUsers = async () => {
    try { const res = await api.get('/users'); setUsers(res.data); }
    catch { toast.error('Failed to load users'); }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = async () => {
    try {
      await api.post('/auth/register', createForm);
      toast.success('User created');
      setCreateDialog(false);
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openPerms = (u) => {
    setSelectedUser(u);
    setPerms(JSON.parse(JSON.stringify(u.permissions || {})));
    setPermDialog(true);
  };

  const togglePerm = (module, action) => {
    setPerms(prev => ({
      ...prev,
      [module]: { ...prev[module], [action]: !prev[module]?.[action] }
    }));
  };

  const savePerms = async () => {
    try {
      await api.put(`/users/${selectedUser.id}/permissions`, { permissions: perms });
      toast.success('Permissions updated');
      setPermDialog(false);
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const openResetPw = (u) => { setSelectedUser(u); setNewPw(''); setResetPwDialog(true); };

  const handleResetPw = async () => {
    try {
      await api.put(`/users/${selectedUser.id}/reset-password`, { new_password: newPw });
      toast.success('Password reset');
      setResetPwDialog(false);
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  const updateRole = async (userId, role) => {
    try {
      await api.put(`/users/${userId}`, { role });
      toast.success('Role updated');
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Error'); }
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="settings-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Settings</h1>
          <p className="text-sm text-slate-500 mt-1">User management & permissions</p>
        </div>
        <Button data-testid="create-user-btn" onClick={() => { setCreateForm({ username: '', full_name: '', email: '', password: '', role: 'cashier', branch_id: '' }); setCreateDialog(true); }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
          <Plus size={16} className="mr-2" /> Add User
        </Button>
      </div>

      <Card className="border-slate-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">User</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Username</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Role</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Branch</TableHead>
                <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-48">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map(u => (
                <TableRow key={u.id} className="table-row-hover">
                  <TableCell>
                    <div>
                      <p className="font-medium">{u.full_name || u.username}</p>
                      <p className="text-xs text-slate-400">{u.email}</p>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{u.username}</TableCell>
                  <TableCell>
                    <Select value={u.role} onValueChange={v => updateRole(u.id, v)} disabled={u.id === currentUser?.id}>
                      <SelectTrigger className="h-8 w-28 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="manager">Manager</SelectItem>
                        <SelectItem value="cashier">Cashier</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="text-sm text-slate-500">{branches.find(b => b.id === u.branch_id)?.name || 'All'}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" data-testid={`perms-btn-${u.id}`} onClick={() => openPerms(u)}>
                        <Shield size={12} className="mr-1" /> Permissions
                      </Button>
                      <Button variant="outline" size="sm" data-testid={`reset-pw-${u.id}`} onClick={() => openResetPw(u)}>
                        <Key size={12} className="mr-1" /> Reset PW
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create User Dialog */}
      <Dialog open={createDialog} onOpenChange={setCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Create User</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Username</Label><Input data-testid="new-username" value={createForm.username} onChange={e => setCreateForm({ ...createForm, username: e.target.value })} /></div>
              <div><Label>Full Name</Label><Input data-testid="new-fullname" value={createForm.full_name} onChange={e => setCreateForm({ ...createForm, full_name: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Email</Label><Input value={createForm.email} onChange={e => setCreateForm({ ...createForm, email: e.target.value })} /></div>
              <div><Label>Password</Label><Input data-testid="new-password" type="password" value={createForm.password} onChange={e => setCreateForm({ ...createForm, password: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Role</Label>
                <Select value={createForm.role} onValueChange={v => setCreateForm({ ...createForm, role: v })}>
                  <SelectTrigger data-testid="new-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="cashier">Cashier</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Branch</Label>
                <Select value={createForm.branch_id} onValueChange={v => setCreateForm({ ...createForm, branch_id: v })}>
                  <SelectTrigger><SelectValue placeholder="All branches" /></SelectTrigger>
                  <SelectContent>
                    {branches.map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateDialog(false)}>Cancel</Button>
              <Button data-testid="save-user-btn" onClick={handleCreate} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Create User</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Permissions Dialog */}
      <Dialog open={permDialog} onOpenChange={setPermDialog}>
        <DialogContent className="sm:max-w-lg max-h-[85vh]">
          <DialogHeader>
            <DialogTitle style={{ fontFamily: 'Manrope' }}>Permissions: {selectedUser?.full_name || selectedUser?.username}</DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            <div className="space-y-4 mt-2 pr-4">
              {PERMISSION_MODULES.map(mod => (
                <Card key={mod.key} className="border-slate-200">
                  <CardHeader className="py-3 px-4"><CardTitle className="text-sm font-semibold">{mod.label}</CardTitle></CardHeader>
                  <CardContent className="px-4 pb-3">
                    <div className="grid grid-cols-2 gap-2">
                      {mod.actions.map(action => (
                        <div key={action} className="flex items-center justify-between p-2 rounded bg-slate-50">
                          <span className="text-sm capitalize">{action.replace('_', ' ')}</span>
                          <Switch
                            data-testid={`perm-${mod.key}-${action}`}
                            checked={perms[mod.key]?.[action] || false}
                            onCheckedChange={() => togglePerm(mod.key, action)}
                          />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </ScrollArea>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setPermDialog(false)}>Cancel</Button>
            <Button data-testid="save-perms-btn" onClick={savePerms} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Save Permissions</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog open={resetPwDialog} onOpenChange={setResetPwDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle style={{ fontFamily: 'Manrope' }}>Reset Password</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <p className="text-sm text-slate-500">Reset password for: <span className="font-medium text-slate-800">{selectedUser?.username}</span></p>
            <div><Label>New Password</Label><Input data-testid="reset-pw-input" type="password" value={newPw} onChange={e => setNewPw(e.target.value)} /></div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setResetPwDialog(false)}>Cancel</Button>
              <Button data-testid="confirm-reset-pw-btn" onClick={handleResetPw} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">Reset</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
