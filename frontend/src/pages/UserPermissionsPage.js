import { useState, useEffect, useCallback } from 'react';
import { api } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { 
  Shield, Users, Settings, Check, X, Eye, Edit3, Trash2, 
  ShoppingCart, Package, Warehouse, DollarSign, FileText,
  Building2, Truck, UserCog, BarChart3, Save, RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';

const MODULE_ICONS = {
  dashboard: BarChart3,
  branches: Building2,
  products: Package,
  inventory: Warehouse,
  sales: ShoppingCart,
  purchase_orders: Truck,
  suppliers: Truck,
  customers: Users,
  accounting: DollarSign,
  price_schemes: FileText,
  reports: BarChart3,
  settings: Settings,
  count_sheets: FileText,
};

export default function UserPermissionsPage() {
  const [users, setUsers] = useState([]);
  const [modules, setModules] = useState({});
  const [presets, setPresets] = useState({});
  const [selectedUser, setSelectedUser] = useState(null);
  const [userPermissions, setUserPermissions] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalPermissions, setOriginalPermissions] = useState({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [usersRes, modulesRes, presetsRes] = await Promise.all([
        api.get('/users'),
        api.get('/permissions/modules'),
        api.get('/permissions/presets'),
      ]);
      setUsers(usersRes.data);
      setModules(modulesRes.data);
      setPresets(presetsRes.data);
    } catch (e) {
      toast.error('Failed to load data');
    }
    setLoading(false);
  };

  const selectUser = async (user) => {
    setSelectedUser(user);
    setHasChanges(false);
    try {
      const res = await api.get(`/users/${user.id}/permissions`);
      const perms = res.data.permissions || {};
      setUserPermissions(perms);
      setOriginalPermissions(JSON.parse(JSON.stringify(perms)));
    } catch (e) {
      toast.error('Failed to load user permissions');
    }
  };

  const handlePermissionToggle = (module, action) => {
    setUserPermissions(prev => {
      const newPerms = { ...prev };
      // Deep-copy the module object to avoid mutating previous state
      const modulePerms = { ...(prev[module] || {}) };
      modulePerms[action] = !modulePerms[action];
      newPerms[module] = modulePerms;
      return newPerms;
    });
    setHasChanges(true);
  };

  const handleModuleToggleAll = (module, enabled) => {
    const moduleActions = modules[module]?.actions || {};
    setUserPermissions(prev => {
      const newPerms = { ...prev };
      newPerms[module] = {};
      Object.keys(moduleActions).forEach(action => {
        newPerms[module][action] = enabled;
      });
      return newPerms;
    });
    setHasChanges(true);
  };

  const applyPreset = async (presetKey) => {
    if (!selectedUser) return;
    try {
      const res = await api.post(`/users/${selectedUser.id}/apply-preset`, { preset: presetKey });
      setUserPermissions(res.data.permissions);
      setOriginalPermissions(JSON.parse(JSON.stringify(res.data.permissions)));
      setSelectedUser(res.data);
      toast.success(`Applied ${presets[presetKey]?.label} preset`);
      setHasChanges(false);
      loadData();
    } catch (e) {
      toast.error('Failed to apply preset');
    }
  };

  const savePermissions = async () => {
    if (!selectedUser) return;
    setSaving(true);
    try {
      await api.put(`/users/${selectedUser.id}/permissions`, { permissions: userPermissions });
      setOriginalPermissions(JSON.parse(JSON.stringify(userPermissions)));
      setHasChanges(false);
      toast.success('Permissions saved');
      loadData();
    } catch (e) {
      toast.error('Failed to save permissions');
    }
    setSaving(false);
  };

  const discardChanges = () => {
    setUserPermissions(JSON.parse(JSON.stringify(originalPermissions)));
    setHasChanges(false);
  };

  const getModuleStatus = (module) => {
    const modulePerms = userPermissions[module] || {};
    const moduleActions = modules[module]?.actions || {};
    const total = Object.keys(moduleActions).length;
    const enabled = Object.values(modulePerms).filter(Boolean).length;
    
    if (enabled === 0) return { status: 'none', label: 'No Access', color: 'bg-slate-100 text-slate-500' };
    if (enabled === total) return { status: 'full', label: 'Full Access', color: 'bg-emerald-100 text-emerald-700' };
    return { status: 'partial', label: 'Partial', color: 'bg-amber-100 text-amber-700' };
  };

  const getRoleBadgeColor = (role) => {
    const colors = {
      admin: 'bg-purple-100 text-purple-700',
      manager: 'bg-blue-100 text-blue-700',
      cashier: 'bg-green-100 text-green-700',
      inventory_clerk: 'bg-orange-100 text-orange-700',
      custom: 'bg-slate-100 text-slate-700',
    };
    return colors[role] || colors.custom;
  };

  return (
    <div className="space-y-5 animate-fadeIn" data-testid="user-permissions-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
            <Shield className="text-[#1A4D2E]" /> User Permissions
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure granular access control for each user — Inflow Cloud style
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        {/* User List */}
        <Card className="border-slate-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2" style={{ fontFamily: 'Manrope' }}>
              <Users size={16} /> Users
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[500px]">
              {users.map(user => (
                <button
                  key={user.id}
                  data-testid={`user-item-${user.username}`}
                  onClick={(e) => { e.stopPropagation(); selectUser(user); }}
                  className={`w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors ${
                    selectedUser?.id === user.id ? 'bg-[#1A4D2E]/5 border-l-2 border-l-[#1A4D2E]' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm">{user.full_name || user.username}</p>
                      <p className="text-xs text-slate-400">@{user.username}</p>
                    </div>
                    <Badge className={`text-[10px] ${getRoleBadgeColor(user.permission_preset || user.role)}`}>
                      {user.permission_preset || user.role}
                    </Badge>
                  </div>
                </button>
              ))}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Permission Editor */}
        <div className="lg:col-span-2">
          {selectedUser ? (
            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg font-bold" style={{ fontFamily: 'Manrope' }}>
                      {selectedUser.full_name || selectedUser.username}
                    </CardTitle>
                    <p className="text-sm text-slate-500 mt-0.5">
                      @{selectedUser.username} · {selectedUser.email || 'No email'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select onValueChange={applyPreset}>
                      <SelectTrigger className="w-40 h-9">
                        <SelectValue placeholder="Apply Preset" />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(presets).map(([key, preset]) => (
                          <SelectItem key={key} value={key}>
                            {preset.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                {hasChanges && (
                  <div className="flex items-center justify-between mt-3 p-2 bg-amber-50 border border-amber-200 rounded-lg">
                    <p className="text-sm text-amber-700">You have unsaved changes</p>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" data-testid="discard-changes-btn" onClick={discardChanges}>Discard</Button>
                      <Button size="sm" data-testid="save-permissions-btn" onClick={savePermissions} disabled={saving} className="bg-[#1A4D2E] hover:bg-[#14532d] text-white">
                        <Save size={14} className="mr-1" /> {saving ? 'Saving...' : 'Save'}
                      </Button>
                    </div>
                  </div>
                )}
              </CardHeader>
              
              <CardContent className="p-0">
                <ScrollArea className="h-[450px]">
                  <div className="divide-y divide-slate-100">
                    {Object.entries(modules).map(([moduleKey, moduleData]) => {
                      const IconComponent = MODULE_ICONS[moduleKey] || Settings;
                      const status = getModuleStatus(moduleKey);
                      const modulePerms = userPermissions[moduleKey] || {};
                      
                      return (
                        <div key={moduleKey} className="p-4">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <IconComponent size={18} className="text-slate-500" />
                              <span className="font-semibold text-sm">{moduleData.label}</span>
                              <Badge className={`text-[9px] ${status.color}`}>{status.label}</Badge>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs"
                                onClick={() => handleModuleToggleAll(moduleKey, false)}
                              >
                                <X size={12} className="mr-1" /> None
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs"
                                onClick={() => handleModuleToggleAll(moduleKey, true)}
                              >
                                <Check size={12} className="mr-1" /> All
                              </Button>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                            {Object.entries(moduleData.actions).map(([actionKey, actionLabel]) => (
                              <label
                                key={actionKey}
                                className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-colors ${
                                  modulePerms[actionKey] 
                                    ? 'bg-emerald-50 border-emerald-200' 
                                    : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                                }`}
                              >
                                <Switch
                                  checked={modulePerms[actionKey] || false}
                                  onCheckedChange={() => handlePermissionToggle(moduleKey, actionKey)}
                                  className="data-[state=checked]:bg-emerald-500"
                                />
                                <span className="text-xs">{actionLabel}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-slate-200">
              <CardContent className="p-12 text-center">
                <UserCog size={48} className="mx-auto text-slate-200 mb-4" />
                <p className="text-slate-400">Select a user to manage permissions</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Preset Legend */}
      <Card className="border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold" style={{ fontFamily: 'Manrope' }}>
            Role Presets Reference
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4">
            {Object.entries(presets).map(([key, preset]) => (
              <div key={key} className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2 mb-1">
                  <Badge className={`text-[10px] ${getRoleBadgeColor(key)}`}>{preset.label}</Badge>
                </div>
                <p className="text-xs text-slate-500">{preset.description}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
