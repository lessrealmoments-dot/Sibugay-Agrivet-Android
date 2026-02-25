import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useOnlineStatus } from '../lib/useOnlineStatus';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Separator } from './ui/separator';
import {
  LayoutDashboard, Building2, Package, Warehouse, ShoppingCart,
  Users, Tags, Receipt, Calculator, Settings, Menu, X,
  ChevronDown, LogOut, User, Store, Truck, Shield, ClipboardList, UserCog, Briefcase, Upload, Lock, ArrowRight, BarChart3, RotateCcw, ShieldCheck, WifiOff
} from 'lucide-react';
import OfflineIndicator from './OfflineIndicator';
import NotificationBell from './NotificationBell';
import { toast } from 'sonner';

// offlineOk: 'full' = works offline | 'readonly' = view cached only | false/omit = requires internet
const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, perm: null, offlineOk: 'readonly' },
  { path: '/branches', label: 'Branches', icon: Building2, perm: 'branches.view' },
  { path: '/branch-transfers', label: 'Branch Transfers', icon: ArrowRight, perm: 'branches.view' },
  { path: '/products', label: 'Products', icon: Package, perm: 'products.view', offlineOk: 'readonly' },
  { path: '/inventory', label: 'Inventory', icon: Warehouse, perm: 'inventory.view', offlineOk: 'readonly' },
  { path: '/count-sheets', label: 'Count Sheets', icon: ClipboardList, perm: 'count_sheets.view' },
  { path: '/import', label: 'Import Center', icon: Upload, perm: 'products.create' },
  { path: '/sales-new', label: 'Sales', icon: ShoppingCart, perm: 'sales.view', offlineOk: 'full' },
  { path: '/returns', label: 'Return & Refund', icon: RotateCcw, perm: 'sales.view' },
  { path: '/purchase-orders', label: 'Purchase Orders', icon: Truck, perm: 'purchase_orders.view' },
  { path: '/pay-supplier', label: 'Pay Supplier', icon: Building2, perm: 'purchase_orders.view' },
  { path: '/suppliers', label: 'Suppliers', icon: Truck, perm: 'suppliers.view' },
  { path: '/daily-ops', label: 'Daily Operations', icon: Receipt, perm: 'reports.view' },
  { path: '/close-wizard', label: 'Close Wizard', icon: Lock, perm: 'reports.close_day' },
  { path: '/reports', label: 'Reports', icon: BarChart3, perm: 'reports.view' },
  { path: '/audit', label: 'Audit Center', icon: ShieldCheck, perm: 'reports.view' },
  { path: '/customers', label: 'Customers', icon: Users, perm: 'customers.view', offlineOk: 'readonly' },
  { path: '/payments', label: 'Receive Payments', icon: Tags, perm: 'accounting.view' },
  { path: '/price-schemes', label: 'Price Schemes', icon: Tags, perm: 'price_schemes.view' },
  { path: '/fund-management', label: 'Fund Mgmt', icon: Calculator, perm: 'accounting.manage_funds' },
  { path: '/accounting', label: 'Accounting', icon: Calculator, perm: 'accounting.view' },
  { path: '/employees', label: 'Employees', icon: Briefcase, perm: 'settings.manage_users' },
  { path: '/accounts', label: 'Accounts', icon: UserCog, perm: 'settings.manage_users' },
  { path: '/user-permissions', label: 'Permissions', icon: Shield, perm: 'settings.manage_permissions' },
  { path: '/settings', label: 'Settings', icon: Settings, perm: 'settings.view' },
];

export default function Layout({ children }) {
  const { 
    user, logout, branches, switchBranch, hasPerm,
    selectedBranchId, canViewAllBranches, viewingBranchName, isConsolidatedView
  } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isOnline = useOnlineStatus();

  const filteredNav = NAV_ITEMS.filter(item => {
    if (!item.perm) return true;
    const [mod, act] = item.perm.split('.');
    return hasPerm(mod, act);
  });

  const NavLink = ({ item }) => {
    const active = location.pathname === item.path;
    const locked = !isOnline && !item.offlineOk;
    const readOnly = !isOnline && item.offlineOk === 'readonly';

    const handleClick = (e) => {
      if (locked) {
        e.preventDefault();
        toast.error('You\'re offline — this area requires internet', { duration: 2500 });
        return;
      }
      setSidebarOpen(false);
    };

    return (
      <Link
        to={item.path}
        data-testid={`nav-${item.path.slice(1)}`}
        onClick={handleClick}
        className={`relative flex items-center gap-3 px-4 py-2.5 rounded-md text-sm font-medium transition-all duration-200 ${
          locked
            ? 'text-slate-600 opacity-50 cursor-not-allowed'
            : active
            ? 'bg-[#1A4D2E] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-white/5'
        }`}
      >
        <item.icon size={18} strokeWidth={1.5} />
        <span className="flex-1">{item.label}</span>
        {locked && <WifiOff size={11} className="text-slate-500 shrink-0" />}
        {readOnly && !active && <span className="text-[9px] text-slate-500 shrink-0">cached</span>}
      </Link>
    );
  };

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <div className="px-5 py-5 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-[#1A4D2E] flex items-center justify-center">
          <Store size={18} className="text-white" strokeWidth={2} />
        </div>
        <div>
          <h1 className="text-base font-bold text-white tracking-tight" style={{ fontFamily: 'Manrope' }}>AgriBooks</h1>
          <p className="text-[11px] text-slate-500">Business Management</p>
        </div>
      </div>
      <Separator className="bg-white/5" />
      <div className="px-3 py-3">
        {canViewAllBranches ? (
          <Select
            value={selectedBranchId}
            onValueChange={(val) => switchBranch(val)}
          >
            <SelectTrigger
              data-testid="branch-selector"
              className="bg-white/5 border-white/10 text-white text-xs h-9"
            >
              <div className="flex items-center gap-2">
                {isConsolidatedView && <Building2 size={14} className="text-emerald-400" />}
                <SelectValue placeholder="Select Branch">{viewingBranchName}</SelectValue>
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">
                <div className="flex items-center gap-2">
                  <Building2 size={14} className="text-emerald-500" />
                  <span className="font-medium">All Branches</span>
                  <span className="text-xs text-slate-400">(Consolidated)</span>
                </div>
              </SelectItem>
              <Separator className="my-1" />
              {branches.map(b => (
                <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <div className="bg-white/5 border border-white/10 rounded-md px-3 py-2 text-xs text-white flex items-center gap-2">
            <Building2 size={14} className="text-slate-400" />
            <span>{viewingBranchName}</span>
            <span className="ml-auto text-slate-500">🔒</span>
          </div>
        )}
      </div>
      <ScrollArea className="flex-1 px-3">
        <nav className="space-y-1 py-2">
          {filteredNav.map(item => <NavLink key={item.path} item={item} />)}
        </nav>
      </ScrollArea>
      <Separator className="bg-white/5" />
      <OfflineIndicator />
      <Separator className="bg-white/5" />
      <div className="p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              data-testid="user-menu-trigger"
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-white/5 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-[#1A4D2E] flex items-center justify-center text-white text-xs font-bold">
                {user?.full_name?.[0] || user?.username?.[0] || 'U'}
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm text-white font-medium truncate">{user?.full_name || user?.username}</p>
                <p className="text-[11px] text-slate-500 capitalize">{user?.role}</p>
              </div>
              <ChevronDown size={14} className="text-slate-500" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => navigate('/settings')}>
              <User size={14} className="mr-2" /> Profile
            </DropdownMenuItem>
            {!user?.is_super_admin && (
              <DropdownMenuItem onClick={() => navigate('/upgrade')}>
                <BarChart3 size={14} className="mr-2" /> Upgrade Plan
              </DropdownMenuItem>
            )}
            {user?.is_super_admin && (
              <DropdownMenuItem onClick={() => navigate('/superadmin')}>
                <Shield size={14} className="mr-2" /> Platform Admin
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="logout-btn" onClick={logout} className="text-red-600">
              <LogOut size={14} className="mr-2" /> Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-[250px] flex-col bg-[#0F172A] sidebar-texture shrink-0">
        <SidebarContent />
      </aside>
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setSidebarOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-[250px] bg-[#0F172A] sidebar-texture">
            <button onClick={() => setSidebarOpen(false)} className="absolute top-4 right-4 text-white">
              <X size={20} />
            </button>
            <SidebarContent />
          </aside>
        </div>
      )}
      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#F5F5F0]">
        <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-4 lg:px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button data-testid="mobile-menu-btn" onClick={() => setSidebarOpen(true)} className="lg:hidden p-1">
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2">
              {isConsolidatedView ? (
                <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-emerald-50 border border-emerald-200">
                  <Building2 size={14} className="text-emerald-600" />
                  <span className="text-sm font-medium text-emerald-700">All Branches</span>
                </div>
              ) : (
                <h2 className="text-sm font-semibold text-slate-700" style={{ fontFamily: 'Manrope' }}>
                  {viewingBranchName}
                </h2>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <NotificationBell />
            <span className="hidden sm:inline">{user?.full_name || user?.username}</span>
            <span className="capitalize bg-slate-100 px-2 py-0.5 rounded text-[11px]">{user?.role}</span>
          </div>
        </header>
        {/* Offline banner — only on pages that require internet */}
        {!isOnline && (() => {
          const currentItem = NAV_ITEMS.find(i => i.path === location.pathname);
          const isLocked = !currentItem?.offlineOk;
          if (!isLocked) return null;
          return (
            <div className="shrink-0 bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2">
              <WifiOff size={14} className="text-amber-600 shrink-0" />
              <span className="text-xs font-medium text-amber-800">
                You&apos;re offline — this page requires internet. Data shown may be outdated.
                Switch to <strong>Sales</strong> for offline operations.
              </span>
            </div>
          );
        })()}
        {/* Trial expiry banner */}
        {user?.subscription?.plan === 'trial' && (() => {
          const daysLeft = user.subscription.trial_ends_at
            ? Math.ceil((new Date(user.subscription.trial_ends_at) - new Date()) / 86400000)
            : null;
          if (!daysLeft || daysLeft > 5) return null;
          return (
            <div className="shrink-0 bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-amber-800">
                Your free trial ends in <strong>{daysLeft} day{daysLeft !== 1 ? 's' : ''}</strong>.
                Upgrade to keep access to all features.
              </span>
              <button onClick={() => navigate('/upgrade')}
                className="text-xs bg-amber-600 text-white px-3 py-1 rounded-full hover:bg-amber-700 shrink-0">
                Upgrade Now
              </button>
            </div>
          );
        })()}
        <div className="flex-1 overflow-auto p-4 lg:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
