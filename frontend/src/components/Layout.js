import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu';
import { Separator } from './ui/separator';
import {
  LayoutDashboard, Building2, Package, Warehouse, ShoppingCart,
  Users, Tags, Receipt, Calculator, Settings, Menu, X,
  ChevronDown, LogOut, User, Store, Truck, Shield, ClipboardList, UserCog, Briefcase, Upload, Lock, ArrowRight, BarChart3, RotateCcw
} from 'lucide-react';
import OfflineIndicator from './OfflineIndicator';
import NotificationBell from './NotificationBell';

const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, perm: null },
  { path: '/branches', label: 'Branches', icon: Building2, perm: 'branches.view' },
  { path: '/branch-transfers', label: 'Branch Transfers', icon: ArrowRight, perm: 'branches.view' },
  { path: '/products', label: 'Products', icon: Package, perm: 'products.view' },
  { path: '/inventory', label: 'Inventory', icon: Warehouse, perm: 'inventory.view' },
  { path: '/count-sheets', label: 'Count Sheets', icon: ClipboardList, perm: 'count_sheets.view' },
  { path: '/import', label: 'Import Center', icon: Upload, perm: 'products.create' },
  { path: '/sales-new', label: 'Sales', icon: ShoppingCart, perm: 'sales.view' },
  { path: '/returns', label: 'Return & Refund', icon: RotateCcw, perm: 'sales.view' },
  { path: '/purchase-orders', label: 'Purchase Orders', icon: Truck, perm: 'purchase_orders.view' },
  { path: '/pay-supplier', label: 'Pay Supplier', icon: Building2, perm: 'purchase_orders.view' },
  { path: '/suppliers', label: 'Suppliers', icon: Truck, perm: 'suppliers.view' },
  { path: '/daily-ops', label: 'Daily Operations', icon: Receipt, perm: 'reports.view' },
  { path: '/close-wizard', label: 'Close Wizard', icon: Lock, perm: 'reports.close_day' },
  { path: '/reports', label: 'Reports', icon: BarChart3, perm: 'reports.view' },
  { path: '/customers', label: 'Customers', icon: Users, perm: 'customers.view' },
  { path: '/payments', label: 'Receive Payments', icon: Tags, perm: 'accounting.view' },
  { path: '/price-schemes', label: 'Price Schemes', icon: Tags, perm: 'price_schemes.view' },
  { path: '/fund-management', label: 'Fund Mgmt', icon: Calculator, perm: 'accounting.manage_funds' },
  { path: '/sales', label: 'Sales History', icon: Receipt, perm: 'reports.view' },
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

  const filteredNav = NAV_ITEMS.filter(item => {
    if (!item.perm) return true;
    const [mod, act] = item.perm.split('.');
    return hasPerm(mod, act);
  });

  const NavLink = ({ item }) => {
    const active = location.pathname === item.path;
    return (
      <Link
        to={item.path}
        data-testid={`nav-${item.path.slice(1)}`}
        onClick={() => setSidebarOpen(false)}
        className={`flex items-center gap-3 px-4 py-2.5 rounded-md text-sm font-medium transition-all duration-200 ${
          active
            ? 'bg-[#1A4D2E] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-white/5'
        }`}
      >
        <item.icon size={18} strokeWidth={1.5} />
        <span>{item.label}</span>
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
        <div className="flex-1 overflow-auto p-4 lg:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
