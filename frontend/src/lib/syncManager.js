/**
 * AgriPOS Sync Manager
 * Handles syncing offline sales to server and refreshing local cache.
 * Emits step-by-step progress events so the UI can show a download bar.
 */

import { api } from '../contexts/AuthContext';
import {
  getPendingSales, removePendingSale,
  cacheProducts, cacheCustomers, cachePriceSchemes, cacheInventory,
  setMeta, getPendingSaleCount,
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

    for (const result of results.results || []) {
      if (result.status === 'synced' || result.status === 'duplicate') {
        await removePendingSale(result.id);
      }
    }

    const remaining = await getPendingSaleCount();
    notifyListeners({ type: 'sync_complete', synced: results.total_synced || 0, remaining });

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
 * Refresh the local IndexedDB cache with all branch data.
 * Emits sync_step events with pct (0-100) and stepLabel so the UI can
 * show a progress bar. Branch-specific inventory is cached when branchId
 * is provided.
 *
 * @param {string|null} branchId - The branch to cache inventory for
 */
export async function refreshPOSCache(branchId = null) {
  if (!navigator.onLine) return false;

  try {
    // Step 0: Connecting
    notifyListeners({ type: 'sync_step', stepLabel: 'Connecting to server...', pct: 5 });

    const params = {};
    if (branchId) params.branch_id = branchId;
    const response = await api.get('/sync/pos-data', { params });
    const { products = [], customers = [], price_schemes = [], inventory = [], sync_time } = response.data;

    // Step 1: Cache products
    notifyListeners({ type: 'sync_step', stepLabel: `Saving ${products.length} products...`, pct: 25 });
    await cacheProducts(products);

    // Step 2: Cache inventory (branch-specific)
    notifyListeners({ type: 'sync_step', stepLabel: 'Saving inventory levels...', pct: 50 });
    if (inventory.length) {
      // Normalize to use product_id as the IndexedDB key
      const inventoryForDB = inventory.map(item => ({
        product_id: item.product_id,
        quantity: item.quantity ?? 0,
        branch_id: item.branch_id,
        updated_at: item.updated_at || new Date().toISOString(),
      }));
      await cacheInventory(inventoryForDB);
    }

    // Step 3: Cache customers
    notifyListeners({ type: 'sync_step', stepLabel: `Saving ${customers.length} customers...`, pct: 75 });
    await cacheCustomers(customers);

    // Step 4: Cache price schemes + finalise
    notifyListeners({ type: 'sync_step', stepLabel: 'Saving price schemes...', pct: 92 });
    await cachePriceSchemes(price_schemes);

    const timestamp = sync_time || new Date().toISOString();
    await setMeta('last_sync', timestamp);
    await setMeta('last_sync_branch', branchId || 'all');
    await setMeta('last_sync_counts', {
      products: products.length,
      customers: customers.length,
      inventory: inventory.length,
    });

    notifyListeners({
      type: 'cache_refreshed',
      timestamp,
      productCount: products.length,
      customerCount: customers.length,
      inventoryCount: inventory.length,
    });

    return true;
  } catch (error) {
    console.error('Cache refresh failed:', error);
    notifyListeners({ type: 'sync_error', error: error.message });
    return false;
  }
}

/**
 * Full sync: push pending sales first, then refresh cache
 */
export async function fullSync(branchId = null) {
  await syncPendingSales();
  return refreshPOSCache(branchId);
}

let autoSyncInterval = null;

export function startAutoSync(getBranchId) {
  if (autoSyncInterval) return;

  autoSyncInterval = setInterval(() => {
    if (navigator.onLine) {
      syncPendingSales();
    }
  }, 30000);

  window.addEventListener('online', () => handleOnlineEvent(getBranchId));
}

export function stopAutoSync() {
  if (autoSyncInterval) {
    clearInterval(autoSyncInterval);
    autoSyncInterval = null;
  }
}

async function handleOnlineEvent(getBranchId) {
  await new Promise(r => setTimeout(r, 2000));
  const branchId = typeof getBranchId === 'function' ? getBranchId() : getBranchId;
  await fullSync(branchId);
}
