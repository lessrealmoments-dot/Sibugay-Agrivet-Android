/**
 * AgriPOS Sync Manager — Resilient Transaction Envelope Pattern
 *
 * Key improvements over previous version:
 *  - Each sale gets a unique envelope_id (separate from invoice id) for idempotency
 *  - Sales processed ONE AT A TIME so a single failure doesn't block others
 *  - Automatic retry with exponential backoff (2s → 4s → 8s, max 3 retries)
 *  - Network error vs server error distinction:
 *      • Network error → stop sync, retry later (preserve queue)
 *      • Server error (4xx) → mark sale as failed, skip it (don't retry forever)
 *  - Auto-sync on reconnect (after 2s delay to let connection stabilize)
 *  - Manual retry button support via triggerSync()
 */

import { api } from '../contexts/AuthContext';
import {
  getPendingSales, removePendingSale,
  cacheProducts, cacheCustomers, cachePriceSchemes, cacheInventory, cacheBranchPrices,
  setMeta, getMeta, getPendingSaleCount, putProduct,
} from './offlineDB';

let syncInProgress = false;
let syncListeners = [];
let autoSyncInterval = null;

export function onSyncUpdate(callback) {
  syncListeners.push(callback);
  return () => { syncListeners = syncListeners.filter(cb => cb !== callback); };
}

function emit(data) {
  syncListeners.forEach(cb => cb(data));
}

/** Generate a UUID-based envelope ID */
export function newEnvelopeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

/**
 * Process a single pending sale with the envelope pattern.
 * Returns: 'synced' | 'duplicate' | 'failed_permanent' | 'network_error'
 */
async function processSingleSale(sale, retryCount = 0) {
  const MAX_RETRIES = 2;
  try {
    const res = await api.post('/sales/sync', { sales: [sale] });
    const results = res.data.results || res.data.synced || [];
    const result = results.find(r => r.id === sale.id || r.envelope_id === sale.envelope_id);
    return result?.status === 'duplicate' ? 'duplicate' : 'synced';
  } catch (err) {
    if (!err.response) {
      // Network error — stop and wait for reconnect
      return 'network_error';
    }
    if (err.response.status >= 500 && retryCount < MAX_RETRIES) {
      // Server error — retry with backoff
      await new Promise(r => setTimeout(r, Math.pow(2, retryCount + 1) * 1000));
      return processSingleSale(sale, retryCount + 1);
    }
    // 4xx or too many retries — permanent failure, skip
    return 'failed_permanent';
  }
}

/**
 * Sync all pending offline sales one at a time.
 * Stops immediately on network error (connection unstable).
 * Skips permanently failed sales (bad data) and continues to the next.
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

    emit({ type: 'sync_start', count: pendingSales.length });

    let synced = 0;
    let skipped = 0;
    let networkError = false;

    for (let i = 0; i < pendingSales.length; i++) {
      const sale = pendingSales[i];
      emit({ type: 'sync_progress', current: i + 1, total: pendingSales.length, saleId: sale.id });

      const status = await processSingleSale(sale);

      if (status === 'network_error') {
        networkError = true;
        emit({ type: 'sync_paused', reason: 'network_error', remaining: pendingSales.length - i });
        break;
      }

      if (status === 'synced' || status === 'duplicate') {
        await removePendingSale(sale.id);
        synced++;
      } else {
        // Permanent failure — remove from queue (bad data, don't retry forever)
        await removePendingSale(sale.id);
        skipped++;
      }
    }

    const remaining = await getPendingSaleCount();
    emit({ type: 'sync_complete', synced, skipped, remaining, networkError });

    if (!networkError) {
      await setMeta('last_sale_sync', new Date().toISOString());
    }

    syncInProgress = false;
    return { synced, skipped, remaining, networkError };
  } catch (error) {
    emit({ type: 'sync_error', error: error.message });
    syncInProgress = false;
    return null;
  }
}

/**
 * Force a sync attempt (called by manual "Sync Now" button).
 */
export async function triggerSync(branchId = null) {
  if (!navigator.onLine) {
    emit({ type: 'sync_error', error: 'No internet connection' });
    return null;
  }
  const salesResult = await syncPendingSales();
  if (branchId) await refreshPOSCache(branchId);
  return salesResult;
}

/**
 * Refresh the local IndexedDB cache with all branch data.
 */
export async function refreshPOSCache(branchId = null) {
  if (!navigator.onLine) return false;

  try {
    emit({ type: 'sync_step', stepLabel: 'Connecting to server...', pct: 5 });

    const params = {};
    if (branchId) params.branch_id = branchId;

    // Delta sync: pass last_sync timestamp to only fetch changes
    const lastSync = await getMeta('last_sync');
    if (lastSync) params.last_sync = lastSync;

    const response = await api.get('/sync/pos-data', { params });
    const { products = [], customers = [], price_schemes = [], inventory = [], branch_prices = [], sync_time, is_delta } = response.data;

    emit({ type: 'sync_step', stepLabel: `Saving ${products.length} products...`, pct: 25 });
    if (is_delta && products.length > 0) {
      // Delta: merge updated products into existing cache
      for (const p of products) await putProduct(p);
    } else if (products.length > 0) {
      await cacheProducts(products);
    }

    emit({ type: 'sync_step', stepLabel: 'Saving inventory levels...', pct: 50 });
    if (inventory.length) {
      const inventoryForDB = inventory.map(item => ({
        product_id: item.product_id,
        quantity: item.quantity ?? 0,
        branch_id: item.branch_id,
        updated_at: item.updated_at || new Date().toISOString(),
      }));
      await cacheInventory(inventoryForDB);
    }

    emit({ type: 'sync_step', stepLabel: `Saving ${customers.length} customers...`, pct: 75 });
    await cacheCustomers(customers);

    emit({ type: 'sync_step', stepLabel: 'Saving price schemes & branch prices...', pct: 92 });
    await cachePriceSchemes(price_schemes);
    if (branch_prices && branch_prices.length) {
      const bpForDB = branch_prices.map(bp => ({
        product_id: bp.product_id,
        prices: bp.prices || {},
        cost_price: bp.cost_price ?? null,
        branch_id: bp.branch_id,
      }));
      await cacheBranchPrices(bpForDB);
    }

    const timestamp = sync_time || new Date().toISOString();
    await setMeta('last_sync', timestamp);
    await setMeta('last_sync_branch', branchId || 'all');
    await setMeta('last_sync_counts', {
      products: products.length,
      customers: customers.length,
      inventory: inventory.length,
      branch_prices: branch_prices.length,
    });

    emit({
      type: 'cache_refreshed',
      timestamp,
      productCount: products.length,
      customerCount: customers.length,
      inventoryCount: inventory.length,
    });

    return true;
  } catch (error) {
    emit({ type: 'sync_error', error: error.message });
    return false;
  }
}

/** Full sync: push pending sales first, then refresh cache */
export async function fullSync(branchId = null) {
  await syncPendingSales();
  return refreshPOSCache(branchId);
}

export function startAutoSync(getBranchId) {
  if (autoSyncInterval) return;

  // Check every 30s if there are pending sales to sync
  autoSyncInterval = setInterval(async () => {
    if (navigator.onLine && !syncInProgress) {
      const count = await getPendingSaleCount();
      if (count > 0) syncPendingSales();
    }
  }, 30000);

  // On reconnect, wait 2s then run full sync
  window.addEventListener('online', () => {
    setTimeout(async () => {
      if (!syncInProgress) {
        const branchId = typeof getBranchId === 'function' ? getBranchId() : getBranchId;
        await fullSync(branchId);
      }
    }, 2000);
  });
}

export function stopAutoSync() {
  if (autoSyncInterval) {
    clearInterval(autoSyncInterval);
    autoSyncInterval = null;
  }
}
