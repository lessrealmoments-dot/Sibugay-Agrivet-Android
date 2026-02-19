/**
 * AgriPOS Sync Manager
 * Handles syncing offline sales to server and refreshing local cache
 */

import { api } from '../contexts/AuthContext';
import {
  getPendingSales, removePendingSale,
  cacheProducts, cacheCustomers, cachePriceSchemes,
  setMeta, getPendingSaleCount
} from './offlineDB';

let syncInProgress = false;
let syncListeners = [];

export function onSyncUpdate(callback) {
  syncListeners.push(callback);
  return () => { syncListeners = syncListeners.filter(cb => cb !== callback); };
}

function notifyListeners(data) {
  syncListeners.forEach(cb => cb(data));
}

/**
 * Sync all pending offline sales to the server
 */
export async function syncPendingSales() {
  if (syncInProgress || !navigator.onLine) return null;
  syncInProgress = true;

  try {
    const pendingSales = await getPendingSales();
    if (!pendingSales.length) {
      syncInProgress = false;
      return { synced: 0, total: 0 };
    }

    notifyListeners({ type: 'sync_start', count: pendingSales.length });

    const response = await api.post('/sales/sync', { sales: pendingSales });
    const results = response.data;

    // Remove successfully synced or duplicate sales from IndexedDB
    for (const result of results.results) {
      if (result.status === 'synced' || result.status === 'duplicate') {
        await removePendingSale(result.id);
      }
    }

    const remaining = await getPendingSaleCount();
    notifyListeners({ type: 'sync_complete', synced: results.synced, remaining });

    syncInProgress = false;
    return results;
  } catch (error) {
    console.error('Sync failed:', error);
    notifyListeners({ type: 'sync_error', error: error.message });
    syncInProgress = false;
    return null;
  }
}

/**
 * Refresh the local IndexedDB cache with latest server data
 */
export async function refreshPOSCache() {
  if (!navigator.onLine) return false;

  try {
    const response = await api.get('/sync/pos-data');
    const { products, customers, price_schemes, timestamp } = response.data;

    await Promise.all([
      cacheProducts(products),
      cacheCustomers(customers),
      cachePriceSchemes(price_schemes),
      setMeta('last_sync', timestamp),
    ]);

    notifyListeners({ type: 'cache_refreshed', timestamp });
    return true;
  } catch (error) {
    console.error('Cache refresh failed:', error);
    return false;
  }
}

/**
 * Full sync: push pending sales, then refresh cache
 */
export async function fullSync() {
  const syncResult = await syncPendingSales();
  await refreshPOSCache();
  return syncResult;
}

let autoSyncInterval = null;

/**
 * Start automatic sync every 30 seconds when online
 */
export function startAutoSync() {
  if (autoSyncInterval) return;

  autoSyncInterval = setInterval(() => {
    if (navigator.onLine) {
      syncPendingSales();
    }
  }, 30000);

  // Also sync when coming back online
  window.addEventListener('online', handleOnlineEvent);
}

export function stopAutoSync() {
  if (autoSyncInterval) {
    clearInterval(autoSyncInterval);
    autoSyncInterval = null;
  }
  window.removeEventListener('online', handleOnlineEvent);
}

async function handleOnlineEvent() {
  // Small delay to let connection stabilize
  await new Promise(r => setTimeout(r, 2000));
  await fullSync();
}
