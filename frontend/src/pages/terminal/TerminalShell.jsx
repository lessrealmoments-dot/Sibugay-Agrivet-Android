import { useState, useEffect, useCallback, useRef } from 'react';
import { ShoppingCart, ClipboardCheck, ArrowLeftRight, Wifi, WifiOff, LogOut, RefreshCw, Bell } from 'lucide-react';
import { toast } from 'sonner';
import TerminalSales from './TerminalSales';
import TerminalPOCheck from './TerminalPOCheck';
import TerminalTransfers from './TerminalTransfers';
import axios from 'axios';
import {
  cacheProducts, getProducts, cacheCustomers,
  cachePriceSchemes, cacheInventory,
  cacheBranchPrices, setOfflineOrg, getPendingSaleCount,
} from '../../lib/offlineDB';
import { syncPendingSales, startAutoSync, stopAutoSync } from '../../lib/syncManager';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace(/^http/, 'ws');

const TABS = [
  { key: 'sales', label: 'Sales', icon: ShoppingCart },
  { key: 'po', label: 'PO Check', icon: ClipboardCheck },
  { key: 'transfers', label: 'Transfers', icon: ArrowLeftRight },
];

export default function TerminalShell({ session, onLogout }) {
  const [activeTab, setActiveTab] = useState('sales');
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [syncing, setSyncing] = useState(false);
  const [dataReady, setDataReady] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncProgress, setSyncProgress] = useState('');
  const [notifications, setNotifications] = useState([]);
  const wsRef = useRef(null);
  const poRefreshRef = useRef(null); // callback to refresh PO list
  const transferRefreshRef = useRef(null);

  // Authenticated axios instance
  const [api] = useState(() => {
    const instance = axios.create({ baseURL: `${BACKEND_URL}/api` });
    instance.interceptors.request.use(config => {
      config.headers.Authorization = `Bearer ${session.token}`;
      if (config.method === 'get' && session.branchId) {
        config.params = { ...config.params, branch_id: session.branchId };
      }
      return config;
    });
    return instance;
  });

  // Online/offline detection
  useEffect(() => {
    const goOnline = () => { setIsOnline(true); toast.success('Back online'); };
    const goOffline = () => { setIsOnline(false); toast('Working offline', { duration: 3000 }); };
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => { window.removeEventListener('online', goOnline); window.removeEventListener('offline', goOffline); };
  }, []);

  // WebSocket connection for real-time events
  useEffect(() => {
    if (!session.terminalId) return;

    const connectWS = () => {
      try {
        const ws = new WebSocket(`${WS_URL}/api/terminal/ws/terminal/${session.terminalId}`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          switch (msg.type) {
            case 'po_assigned':
              toast.success(`New PO: ${msg.data.po_number || 'PO'} from ${msg.data.vendor || 'vendor'}`, { duration: 5000 });
              setNotifications(prev => [...prev, { type: 'po', ...msg.data, time: Date.now() }]);
              // Auto-refresh PO list
              if (poRefreshRef.current) poRefreshRef.current();
              break;
            case 'transfer_assigned':
              toast.success(`New Transfer: ${msg.data.transfer_number || 'Transfer'}`, { duration: 5000 });
              setNotifications(prev => [...prev, { type: 'transfer', ...msg.data, time: Date.now() }]);
              if (transferRefreshRef.current) transferRefreshRef.current();
              break;
            default:
              break;
          }
        };

        ws.onclose = () => {
          wsRef.current = null;
          // Reconnect after 3 seconds
          setTimeout(() => { if (navigator.onLine) connectWS(); }, 3000);
        };

        ws.onerror = () => { ws.close(); };
      } catch { /* WebSocket not available */ }
    };

    if (navigator.onLine) connectWS();

    return () => { if (wsRef.current) { wsRef.current.close(); wsRef.current = null; } };
  }, [session.terminalId]);

  // Initial data load
  const loadData = useCallback(async () => {
    setSyncing(true);
    setSyncProgress('Connecting...');
    if (session.organizationId) setOfflineOrg(session.organizationId);

    if (navigator.onLine) {
      try {
        setSyncProgress('Downloading products...');
        const params = { branch_id: session.branchId };
        const [posRes, custRes, schemeRes] = await Promise.all([
          api.get('/sync/pos-data', { params }),
          api.get('/customers', { params: { limit: 500, ...params } }),
          api.get('/price-schemes'),
        ]);

        setSyncProgress('Saving to local storage...');
        await Promise.all([
          cacheProducts(posRes.data.products || []),
          cacheCustomers(custRes.data.customers || posRes.data.customers || []),
          cachePriceSchemes(schemeRes.data || posRes.data.price_schemes || []),
          posRes.data.inventory?.length ? cacheInventory(
            posRes.data.inventory.map(item => ({
              product_id: item.product_id, quantity: item.quantity ?? 0,
              branch_id: item.branch_id, updated_at: item.updated_at || new Date().toISOString(),
            }))
          ) : Promise.resolve(),
          posRes.data.branch_prices?.length ? cacheBranchPrices(
            posRes.data.branch_prices.map(bp => ({
              product_id: bp.product_id, prices: bp.prices || {},
              cost_price: bp.cost_price ?? null, branch_id: bp.branch_id,
            }))
          ) : Promise.resolve(),
        ]);

        const count = await getPendingSaleCount();
        setPendingCount(count);
        if (count > 0) {
          setSyncProgress(`Syncing ${count} pending sale(s)...`);
          await syncPendingSales();
          setPendingCount(await getPendingSaleCount());
        }

        setSyncProgress('');
        setDataReady(true);
        toast.success(`Data synced — ${posRes.data.products?.length || 0} products loaded`);
      } catch (e) {
        console.error('Sync failed:', e);
        await loadOfflineData();
      }
    } else {
      await loadOfflineData();
    }
    setSyncing(false);
  }, [api, session.branchId, session.organizationId]);

  const loadOfflineData = async () => {
    const prods = await getProducts();
    if (prods.length > 0) {
      setDataReady(true);
      toast('Loaded from offline cache', { duration: 3000 });
    } else {
      toast.error('No cached data — connect to internet first');
    }
    setSyncProgress('');
  };

  useEffect(() => { loadData(); }, [loadData]);

  // Auto sync
  useEffect(() => {
    startAutoSync(() => session.branchId);
    return () => stopAutoSync();
  }, [session.branchId]);

  const handleManualSync = async () => {
    setSyncing(true);
    await loadData();
    setSyncing(false);
  };

  const handleLogout = () => {
    if (wsRef.current) wsRef.current.close();
    localStorage.removeItem('agrismart_terminal');
    onLogout();
  };

  // Notification badge count (unread)
  const unreadCount = notifications.filter(n => Date.now() - n.time < 60000).length;

  if (!dataReady) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white" data-testid="terminal-loading">
        <RefreshCw className="w-10 h-10 animate-spin text-emerald-400 mb-4" />
        <p className="text-slate-300 text-sm">{syncProgress || 'Preparing terminal...'}</p>
        <p className="text-slate-500 text-xs mt-2">{session.branchName}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F5F0] flex flex-col" data-testid="terminal-shell">
      {/* Top bar */}
      <div className="bg-white border-b border-slate-200 px-3 py-2 flex items-center justify-between safe-area-top">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#1A4D2E]" style={{ fontFamily: 'Manrope' }}>AgriSmart</span>
          <span className="text-xs text-slate-500 border-l border-slate-200 pl-2">{session.branchName}</span>
        </div>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <span className="bg-amber-100 text-amber-700 text-[10px] font-medium px-2 py-0.5 rounded-full" data-testid="pending-badge">
              {pendingCount} pending
            </span>
          )}
          <span className={`flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${isOnline ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`} data-testid="online-status">
            {isOnline ? <Wifi size={10} /> : <WifiOff size={10} />}
            {isOnline ? 'Online' : 'Offline'}
          </span>
          <button onClick={handleManualSync} disabled={syncing} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500" data-testid="sync-btn">
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
          </button>
          <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500" data-testid="terminal-logout-btn">
            <LogOut size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'sales' && (
          <TerminalSales api={api} session={session} isOnline={isOnline} pendingCount={pendingCount} setPendingCount={setPendingCount} />
        )}
        {activeTab === 'po' && (
          <TerminalPOCheck api={api} session={session} isOnline={isOnline} onRefreshRef={poRefreshRef} />
        )}
        {activeTab === 'transfers' && (
          <TerminalTransfers api={api} session={session} isOnline={isOnline} onRefreshRef={transferRefreshRef} />
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="bg-white border-t border-slate-200 safe-area-bottom">
        <div className="flex items-center justify-around py-1.5 px-2">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            const hasBadge = (tab.key === 'po' && notifications.some(n => n.type === 'po' && Date.now() - n.time < 60000)) ||
                             (tab.key === 'transfers' && notifications.some(n => n.type === 'transfer' && Date.now() - n.time < 60000));
            return (
              <button
                key={tab.key}
                onClick={() => { setActiveTab(tab.key); setNotifications(prev => prev.filter(n => n.type !== (tab.key === 'po' ? 'po' : 'transfer'))); }}
                className={`relative flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-xl transition-all ${
                  active ? 'text-[#1A4D2E] bg-emerald-50' : 'text-slate-400'
                }`}
                data-testid={`tab-${tab.key}`}
              >
                <Icon size={18} strokeWidth={active ? 2.5 : 1.5} />
                <span className="text-[10px] font-medium">{tab.label}</span>
                {hasBadge && (
                  <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full border border-white" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
