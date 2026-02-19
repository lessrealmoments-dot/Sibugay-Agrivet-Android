/**
 * AgriPOS Offline Database (IndexedDB)
 * Stores products, customers, price schemes, and pending offline sales
 */

const DB_NAME = 'agripos_offline';
const DB_VERSION = 2;

const STORES = {
  PRODUCTS: 'products',
  CUSTOMERS: 'customers',
  PRICE_SCHEMES: 'price_schemes',
  PENDING_SALES: 'pending_sales',
  META: 'meta',
};

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      Object.values(STORES).forEach((store) => {
        if (!db.objectStoreNames.contains(store)) {
          const keyPath = store === STORES.META ? 'key' : 'id';
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
