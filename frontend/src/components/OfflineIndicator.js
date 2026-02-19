import { useState, useEffect } from 'react';
import { getPendingSaleCount } from '../lib/offlineDB';
import { syncPendingSales, onSyncUpdate } from '../lib/syncManager';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Wifi, WifiOff, RefreshCw, CloudOff, Download } from 'lucide-react';
import { toast } from 'sonner';

export default function OfflineIndicator() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [installPrompt, setInstallPrompt] = useState(null);

  useEffect(() => {
    const updateOnline = () => setIsOnline(navigator.onLine);
    window.addEventListener('online', updateOnline);
    window.addEventListener('offline', updateOnline);

    // Listen for install prompt
    const handleInstallPrompt = (e) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleInstallPrompt);

    // Load pending count
    getPendingSaleCount().then(setPendingCount);

    // Listen for sync updates
    const unsub = onSyncUpdate((data) => {
      if (data.type === 'sync_start') setSyncing(true);
      if (data.type === 'sync_complete') {
        setSyncing(false);
        setPendingCount(data.remaining || 0);
      }
      if (data.type === 'sync_error') setSyncing(false);
    });

    // Poll pending count every 5s
    const countInterval = setInterval(() => {
      getPendingSaleCount().then(setPendingCount);
    }, 5000);

    return () => {
      window.removeEventListener('online', updateOnline);
      window.removeEventListener('offline', updateOnline);
      window.removeEventListener('beforeinstallprompt', handleInstallPrompt);
      unsub();
      clearInterval(countInterval);
    };
  }, []);

  const handleManualSync = async () => {
    if (!navigator.onLine) {
      toast.error('Cannot sync while offline');
      return;
    }
    setSyncing(true);
    const result = await syncPendingSales();
    setSyncing(false);
    if (result) {
      toast.success(`Synced ${result.synced} sale(s)`);
      setPendingCount(0);
    }
  };

  const handleInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') {
      toast.success('AgriPOS installed!');
    }
    setInstallPrompt(null);
  };

  return (
    <div className="space-y-2 px-3 py-2">
      {/* Online/Offline Status */}
      <div className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium ${
        isOnline ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
      }`}>
        {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
        <span>{isOnline ? 'Online' : 'Offline Mode'}</span>
        {!isOnline && <CloudOff size={12} className="ml-auto opacity-60" />}
      </div>

      {/* Pending Sales */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between px-3 py-2 rounded-md bg-amber-500/10">
          <div className="flex items-center gap-2 text-xs text-amber-400">
            <RefreshCw size={12} className={syncing ? 'animate-spin' : ''} />
            <span>{pendingCount} pending sale{pendingCount > 1 ? 's' : ''}</span>
          </div>
          {isOnline && (
            <button
              data-testid="manual-sync-btn"
              onClick={handleManualSync}
              disabled={syncing}
              className="text-[10px] text-amber-300 hover:text-amber-200 underline"
            >
              {syncing ? 'Syncing...' : 'Sync now'}
            </button>
          )}
        </div>
      )}

      {/* Install PWA Button */}
      {installPrompt && (
        <Button
          data-testid="install-pwa-btn"
          onClick={handleInstall}
          variant="outline"
          size="sm"
          className="w-full h-8 text-xs border-white/10 text-slate-300 hover:text-white hover:bg-white/5"
        >
          <Download size={12} className="mr-2" /> Install App
        </Button>
      )}
    </div>
  );
}
