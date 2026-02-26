/**
 * AgriPOS Offline Database (IndexedDB)
 * Stores products, customers, price schemes, inventory, and pending offline sales.
 * Org-scoped: each company gets its own database to prevent cross-tenant data leaks.
 */

let _currentOrgId = null;

function getDBName() {
  return _currentOrgId ? `agripos_offline_${_currentOrgId}` : 'agripos_offline';
}

/** Set the current organization for DB scoping. Call on login. */
export function setOfflineOrg(orgId) {
  if (orgId && orgId !== _currentOrgId) {
    _currentOrgId = orgId;
  }
}

/** Get current org ID */
export function getOfflineOrg() {
  return _currentOrgId;
}

const DB_VERSION = 4;

const STORES = {
  PRODUCTS: 'products',
  CUSTOMERS: 'customers',
  PRICE_SCHEMES: 'price_schemes',
  INVENTORY: 'inventory',
  BRANCH_PRICES: 'branch_prices',
  PENDING_SALES: 'pending_sales',
  META: 'meta',
};

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      // Custom key paths per store
      const keyPaths = {
        [STORES.META]: 'key',
        [STORES.INVENTORY]: 'product_id',
        [STORES.BRANCH_PRICES]: 'product_id', // one branch cached at a time
      };
      Object.values(STORES).forEach((store) => {
        if (!db.objectStoreNames.contains(store)) {
          const keyPath = keyPaths[store] || 'id';
          db.createObjectStore(store, { keyPath });
        }
      });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function clearAndPut(storeName, items) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    store.clear();
    items.forEach((item) => store.put(item));
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function getAll(storeName) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).getAll();
    request.onsuccess = () => { db.close(); resolve(request.result); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

async function putOne(storeName, item) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).put(item);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function deleteOne(storeName, key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).delete(key);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function countStore(storeName) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).count();
    request.onsuccess = () => { db.close(); resolve(request.result); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

// ==================== Public API ====================

export async function cacheProducts(products) {
  await clearAndPut(STORES.PRODUCTS, products);
}

export async function getProducts() {
  return getAll(STORES.PRODUCTS);
}

export async function cacheCustomers(customers) {
  await clearAndPut(STORES.CUSTOMERS, customers);
}

export async function getCustomers() {
  return getAll(STORES.CUSTOMERS);
}

export async function cachePriceSchemes(schemes) {
  await clearAndPut(STORES.PRICE_SCHEMES, schemes);
}

export async function getPriceSchemes() {
  return getAll(STORES.PRICE_SCHEMES);
}

export async function addPendingSale(sale) {
  await putOne(STORES.PENDING_SALES, sale);
}

export async function getPendingSales() {
  return getAll(STORES.PENDING_SALES);
}

export async function removePendingSale(saleId) {
  await deleteOne(STORES.PENDING_SALES, saleId);
}

export async function getPendingSaleCount() {
  return countStore(STORES.PENDING_SALES);
}

export async function setMeta(key, value) {
  await putOne(STORES.META, { key, value, updated_at: new Date().toISOString() });
}

export async function getMeta(key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.META, 'readonly');
    const request = tx.objectStore(STORES.META).get(key);
    request.onsuccess = () => { db.close(); resolve(request.result?.value || null); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

// Branch price overrides cache (keyed by product_id — one branch at a time)
export async function cacheBranchPrices(items) {
  await clearAndPut(STORES.BRANCH_PRICES, items);
}

export async function getBranchPrice(productId) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.BRANCH_PRICES, 'readonly');
    const request = tx.objectStore(STORES.BRANCH_PRICES).get(productId);
    request.onsuccess = () => { db.close(); resolve(request.result || null); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}

// Inventory cache (keyed by product_id — one branch at a time)
export async function cacheInventory(items) {
  await clearAndPut(STORES.INVENTORY, items);
}

export async function getInventory() {
  return getAll(STORES.INVENTORY);
}

export async function getInventoryItem(productId) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.INVENTORY, 'readonly');
    const request = tx.objectStore(STORES.INVENTORY).get(productId);
    request.onsuccess = () => { db.close(); resolve(request.result || null); };
    request.onerror = () => { db.close(); reject(request.error); };
  });
}
