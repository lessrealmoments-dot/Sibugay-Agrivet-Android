import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Settings, Plus, Shield, Key, Smartphone, CheckCircle2, XCircle, Lock, RefreshCw, AlertTriangle, Users, ExternalLink } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { toast } from 'sonner';

const PERMISSION_MODULES = []; // unused - permissions managed via /user-permissions page

export default function SettingsPage() {
  const { user: currentUser, branches } = useAuth();
  const navigate = useNavigate();
  const isAdmin = currentUser?.role === 'admin';

  // ── User Management ───────────────────────────────────────────────────────
  const [users, setUsers] = useState([]);
  const [createDialog, setCreateDialog] = useState(false);
  const [resetPwDialog, setResetPwDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newPw, setNewPw] = useState('');
  const [createForm, setCreateForm] = useState({
    username: '', full_name: '', email: '', password: '', role: 'cashier', branch_id: ''
  });

  const fetchUsers = useCallback(async () => {
    try { const res = await api.get('/users'); setUsers(res.data); }
    catch { toast.error('Failed to load users'); }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleCreate = async () => {
    try {
      await api.post('/auth/register', createForm);
      toast.success('User created');
      setCreateDialog(false);
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

  // ── TOTP Setup ────────────────────────────────────────────────────────────
  const [totpStatus, setTotpStatus] = useState({ enabled: false, verified: false });
  const [totpSetup, setTotpSetup] = useState(null);   // { secret, qr_uri } during setup
  const [totpConfirmCode, setTotpConfirmCode] = useState('');
  const [totpLoading, setTotpLoading] = useState(false);
  const [totpStep, setTotpStep] = useState('idle'); // 'idle' | 'scan' | 'verify'

  const loadTotpStatus = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const res = await api.get('/auth/totp/status');
      setTotpStatus(res.data);
    } catch {}
  }, [isAdmin]);

  useEffect(() => { loadTotpStatus(); }, [loadTotpStatus]);

  const startTotpSetup = async () => {
    setTotpLoading(true);
    try {
      const res = await api.post('/auth/totp/setup');
      setTotpSetup(res.data);
      setTotpStep('scan');
    } catch { toast.error('Failed to generate TOTP secret'); }
    setTotpLoading(false);
  };

  const confirmTotpSetup = async () => {
    if (totpConfirmCode.length !== 6) { toast.error('Enter 6-digit code'); return; }
    setTotpLoading(true);
    try {
      const res = await api.post('/auth/totp/verify-setup', { code: totpConfirmCode });
      if (res.data.verified) {
        toast.success('Authenticator app connected!');
        setTotpStep('idle');
        setTotpSetup(null);
        setTotpConfirmCode('');
        loadTotpStatus();
      } else {
        toast.error(res.data.error || 'Code mismatch — try again');
      }
    } catch { toast.error('Verification failed'); }
    setTotpLoading(false);
  };

  const disableTotp = async () => {
    if (!window.confirm('Disable TOTP? You will fall back to using your login password for admin verification.')) return;
    try {
      await api.delete('/auth/totp/disable');
      toast.success('TOTP disabled');
      loadTotpStatus();
    } catch { toast.error('Failed to disable TOTP'); }
  };

  // ── TOTP Controls ─────────────────────────────────────────────────────────
  const [totpActions, setTotpActions] = useState([]);
  const [enabledActions, setEnabledActions] = useState([]);
  const [savingControls, setSavingControls] = useState(false);

  const loadTotpControls = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const res = await api.get('/settings/totp-controls');
      setTotpActions(res.data.actions || []);
      setEnabledActions(res.data.enabled_actions || []);
    } catch {}
  }, [isAdmin]);

  useEffect(() => { loadTotpControls(); }, [loadTotpControls]);

  const toggleAction = (key) => {
    setEnabledActions(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const saveControls = async () => {
    setSavingControls(true);
    try {
      await api.put('/settings/totp-controls', { enabled_actions: enabledActions });
      toast.success('TOTP controls saved');
    } catch { toast.error('Failed to save'); }
    setSavingControls(false);
  };

  // Group actions by module for display
  const actionsByModule = totpActions.reduce((acc, a) => {
    if (!acc[a.module]) acc[a.module] = [];
    acc[a.module].push(a);
    return acc;
  }, {});

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="settings-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Settings</h1>
          <p className="text-sm text-slate-500 mt-1">User management, security & system settings</p>
        </div>
      </div>

      <Tabs defaultValue="users">
        <TabsList className="mb-4">
          <TabsTrigger value="users" className="flex items-center gap-1.5">
            <Users size={14} /> Users
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="security" data-testid="security-tab" className="flex items-center gap-1.5">
              <Shield size={14} /> Security
            </TabsTrigger>
          )}
        </TabsList>

        {/* ── Users Tab ─────────────────────────────────────────────────── */}
        <TabsContent value="users">
          <div className="flex justify-end mb-3">
            <Button data-testid="create-user-btn" onClick={() => {
              setCreateForm({ username: '', full_name: '', email: '', password: '', role: 'cashier', branch_id: '' });
              setCreateDialog(true);
            }} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
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
                          <SelectTrigger className="h-8 w-28 text-xs"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="manager">Manager</SelectItem>
                            <SelectItem value="cashier">Cashier</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-sm text-slate-500">
                        {branches.find(b => b.id === u.branch_id)?.name || 'All'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="outline" size="sm" data-testid={`perms-btn-${u.id}`}
                            onClick={() => navigate('/user-permissions')}
                            title="Manage full permissions in the User Permissions page">
                            <Shield size={12} className="mr-1" /> Permissions
                            <ExternalLink size={10} className="ml-1 opacity-50" />
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
        </TabsContent>

        {/* ── Security Tab ──────────────────────────────────────────────── */}
        {isAdmin && (
          <TabsContent value="security" className="space-y-6">

            {/* TOTP Setup Card */}
            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
                  <Smartphone size={18} className="text-[#1A4D2E]" />
                  Authenticator App (TOTP)
                  {totpStatus.enabled && totpStatus.verified ? (
                    <Badge className="text-[10px] bg-emerald-100 text-emerald-700 ml-2">Active</Badge>
                  ) : (
                    <Badge className="text-[10px] bg-slate-100 text-slate-500 ml-2">Not Set Up</Badge>
                  )}
                </CardTitle>
                <p className="text-sm text-slate-500">
                  Connect Google Authenticator, Authy, or any TOTP app to generate time-based
                  codes for sensitive actions. Codes change every 30 seconds and require a network
                  connection to verify — they cannot be used offline.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">

                {/* ── Idle / Active state ── */}
                {totpStep === 'idle' && (
                  <>
                    {totpStatus.enabled && totpStatus.verified ? (
                      <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 size={20} className="text-emerald-600" />
                          <div>
                            <p className="font-semibold text-emerald-800 text-sm">TOTP is active</p>
                            <p className="text-xs text-emerald-600">Admin verification uses your authenticator app codes</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={startTotpSetup} disabled={totpLoading}>
                            <RefreshCw size={13} className="mr-1" /> Regenerate
                          </Button>
                          <Button size="sm" variant="outline" onClick={disableTotp} className="text-red-500 border-red-200 hover:bg-red-50">
                            <XCircle size={13} className="mr-1" /> Disable
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between p-4 bg-amber-50 border border-amber-200 rounded-lg">
                        <div className="flex items-center gap-3">
                          <AlertTriangle size={20} className="text-amber-600" />
                          <div>
                            <p className="font-semibold text-amber-800 text-sm">TOTP not configured</p>
                            <p className="text-xs text-amber-600">Admin actions fall back to your login password</p>
                          </div>
                        </div>
                        <Button size="sm" onClick={startTotpSetup} disabled={totpLoading}
                          className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                          {totpLoading ? <RefreshCw size={13} className="animate-spin mr-1" /> : <Smartphone size={13} className="mr-1" />}
                          Set Up Now
                        </Button>
                      </div>
                    )}
                  </>
                )}

                {/* ── Step 1: Scan QR ── */}
                {totpStep === 'scan' && totpSetup && (
                  <div className="space-y-4">
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                      <strong>Step 1:</strong> Open your authenticator app and scan the QR code below.
                      Then click <strong>Next</strong> to confirm it&apos;s working.
                    </div>
                    <div className="flex flex-col items-center gap-4 py-4">
                      <div className="p-4 bg-white border-2 border-slate-200 rounded-xl shadow-sm">
                        <QRCodeSVG value={totpSetup.qr_uri} size={180} level="M" />
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-500 mb-1">Can&apos;t scan? Enter this secret manually:</p>
                        <code className="text-sm bg-slate-100 px-3 py-1.5 rounded font-mono tracking-wider select-all">
                          {totpSetup.secret}
                        </code>
                      </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                      <Button variant="outline" onClick={() => { setTotpStep('idle'); setTotpSetup(null); }}>Cancel</Button>
                      <Button onClick={() => setTotpStep('verify')} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                        Next — Enter Code
                      </Button>
                    </div>
                  </div>
                )}

                {/* ── Step 2: Verify code ── */}
                {totpStep === 'verify' && (
                  <div className="space-y-4">
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                      <strong>Step 2:</strong> Enter the current 6-digit code from your authenticator app
                      to confirm it&apos;s working correctly.
                    </div>
                    <div className="max-w-xs mx-auto space-y-2">
                      <Label>Confirmation Code</Label>
                      <Input
                        data-testid="totp-confirm-input"
                        value={totpConfirmCode}
                        onChange={e => setTotpConfirmCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                        placeholder="000000"
                        className="text-center text-2xl tracking-[0.4em] font-mono h-12"
                        maxLength={6}
                        autoFocus
                        onKeyDown={e => e.key === 'Enter' && confirmTotpSetup()}
                      />
                    </div>
                    <div className="flex gap-2 justify-end">
                      <Button variant="outline" onClick={() => setTotpStep('scan')}>Back</Button>
                      <Button
                        data-testid="totp-confirm-btn"
                        onClick={confirmTotpSetup}
                        disabled={totpLoading || totpConfirmCode.length !== 6}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        {totpLoading ? <RefreshCw size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
                        Activate
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* TOTP Controls Card */}
            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
                      <Lock size={18} className="text-[#1A4D2E]" />
                      TOTP-Protected Actions
                    </CardTitle>
                    <p className="text-sm text-slate-500 mt-0.5">
                      Toggle which actions require TOTP verification before proceeding.
                      Non-admin users will need to enter a valid code from your app.
                    </p>
                  </div>
                  <Button
                    data-testid="save-totp-controls-btn"
                    size="sm"
                    onClick={saveControls}
                    disabled={savingControls}
                    className="bg-[#1A4D2E] hover:bg-[#14532d] text-white shrink-0"
                  >
                    {savingControls ? <RefreshCw size={13} className="animate-spin mr-1" /> : null}
                    Save
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-5">
                  {Object.entries(actionsByModule).map(([module, actions]) => (
                    <div key={module}>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">{module}</p>
                      <div className="grid sm:grid-cols-2 gap-2">
                        {actions.map(action => (
                          <label
                            key={action.key}
                            data-testid={`totp-action-${action.key}`}
                            className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                              enabledActions.includes(action.key)
                                ? 'bg-amber-50 border-amber-200'
                                : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                            }`}
                          >
                            <Switch
                              checked={enabledActions.includes(action.key)}
                              onCheckedChange={() => toggleAction(action.key)}
                              className="data-[state=checked]:bg-amber-500"
                            />
                            <div>
                              <p className="text-sm font-medium">{action.label}</p>
                              <p className="text-xs text-slate-400">{action.module}</p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                  {totpActions.length === 0 && (
                    <p className="text-sm text-slate-400 text-center py-4">Loading actions...</p>
                  )}
                </div>
              </CardContent>
            </Card>

          </TabsContent>
        )}
      </Tabs>

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
