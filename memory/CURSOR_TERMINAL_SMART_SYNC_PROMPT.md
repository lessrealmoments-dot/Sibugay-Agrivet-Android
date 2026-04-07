# AgriSmart Terminal — Smart Sync Android Enhancements (Cursor AI Prompt)

## Context

The web app (loaded in Capacitor WebView at `https://agri-books.com`) has been upgraded with a **Smart Sync** system:

1. **Instant Load**: Terminal opens instantly from IndexedDB cache (no network wait)
2. **Background Delta Sync**: Only changed records fetched since `last_sync` timestamp
3. **Inventory Pulse**: Lightweight stock-level polling every 60 seconds via `/api/sync/inventory-pulse`
4. **Sync Indicator**: Header shows "Syncing..." / "Up to date" / "Sync failed" non-blocking

All sync logic runs in JavaScript (IndexedDB). The Android APK is a Capacitor WebView wrapper.

---

## Android implementation status (this repo)

| Item | Status |
|------|--------|
| `MainActivity` — `WebSettings` (DOM storage, DB, cache mode, `onResume` hooks) | Done |
| `AndroidManifest.xml` — `singleTask` + `configChanges` | Already present |
| Optional `NetworkReceiver` | Not added (optional) |
| Web: `window.__triggerBackgroundSync` | Emergent must expose (see §4) |

---

## What to implement (reference)

### 1. WebView IndexedDB persistence

**File:** `frontend/android/app/src/main/java/com/agribooks/terminal/MainActivity.java`

After `super.onCreate()`, configure the Capacitor WebView:

- `setDomStorageEnabled(true)`
- `setDatabaseEnabled(true)` (legacy flag; harmless on modern WebView)
- `setCacheMode(WebSettings.LOAD_DEFAULT)`

### 2. WebView cache mode for offline resilience

In `onResume()`, detect connectivity and set:

- Online: `LOAD_DEFAULT`
- Offline: `LOAD_CACHE_ELSE_NETWORK`

Use `ConnectivityManager` + `NetworkCapabilities` on API 23+, with a fallback to `NetworkInfo` for API 22 (`minSdk`).

### 3. Process / activity lifecycle

**File:** `frontend/android/app/src/main/AndroidManifest.xml`

`MainActivity` should use `android:launchMode="singleTask"` and `android:configChanges` including orientation and screen size — **already configured** in this project.

### 4. (Optional) Background sync trigger from native

In `onResume()`:

```java
getBridge().getWebView().evaluateJavascript(
    "if(window.__triggerBackgroundSync) window.__triggerBackgroundSync();",
    null
);
```

**Web (Emergent):** expose the hook, for example:

```javascript
window.__triggerBackgroundSync = () => {
  if (typeof backgroundSync === 'function') backgroundSync(false);
};
```

### 5. Network state — metered

In `onResume()`:

```java
boolean isMetered = cm.isActiveNetworkMetered();
webView.evaluateJavascript("window.__isMeteredConnection=" + isMetered + ";", null);
```

The web sync layer can read `window.__isMeteredConnection` before auto-polling (e.g. skip on metered unless user taps "Sync Now").

---

## Files to modify

| File | Changes |
|------|---------|
| `MainActivity.java` | WebSettings, cache mode in `onResume`, JS hooks |
| `AndroidManifest.xml` | `singleTask`, `configChanges` (already satisfied) |
| (Optional) `NetworkReceiver.java` | Connectivity broadcasts → update cache mode |

---

## Testing

1. Open terminal → pair → scan a product  
2. Force-close the app (swipe away from recent apps)  
3. Reopen → terminal should load quickly from cache when the web Smart Sync layer is deployed  
4. Airplane mode → cached shell should still load where HTTP cache allows  
5. Online → inventory pulse / delta sync as implemented in JS  

---

## Important notes

- The web app owns sync logic; Android ensures **WebView storage and cache behavior** and exposes **optional JS hooks**.  
- **Do not** change `printer-release.aar` integration for this work.  
- If the APK is not updated, Smart Sync in JS still runs; cache persistence across kills may be weaker on some devices.  
- `ACCESS_NETWORK_STATE` is already declared in `AndroidManifest.xml`.

---

## Handoff for Emergent — persistence caveat and recommendations

### Caveat (Cursor / Android)

**WebView `WebSettings` alone does not guarantee IndexedDB survives every real-world event.** IndexedDB and HTTP cache live inside the WebView profile. They usually persist across normal app restarts and “swipe away” from recents, but can still be lost when:

- The user clears **app storage** or **cache** for the terminal app in system settings  
- The OEM or WebView update **resets** or **migrates** the profile (rare but documented in edge cases)  
- Aggressive battery optimization **evicts** the process and, on some devices, storage behavior differs  
- **Low storage** triggers Android cleanup  

So: **Smart Sync in JS + our MainActivity tuning is the right first step**, but marketing “never full re-download” as an absolute guarantee would be misleading without a native or hybrid backup.

### Recommendations (better options — pick by effort)

1. **Treat IndexedDB as a cache, not the only source of truth**  
   Always assume cold start may need a **delta or full sync** from the server. UX: instant paint from whatever is on disk, then background reconcile (you already lean this way with `last_sync`).

2. **Mirror critical sync metadata in Capacitor Preferences (small JSON)**  
   Store **`last_sync`**, **branch id**, **terminal session id** (non-secret handles only — not PINs/tokens if avoidable) via `@capacitor/preferences` so a wiped IDB still knows *what* to request on next online window. Full product blobs stay in IDB or refetched.

3. **Optional native plugin: “sync snapshot” file**  
   For highest durability on warehouse devices: a thin native plugin writes **encrypted or plain JSON snapshot** to `context.getFilesDir()` on a schedule (after successful sync). On boot, JS reads snapshot first, then merges with server. Heavier work; only if IDB loss is observed in the field.

4. **Service Worker + Cache API (PWA layer)**  
   If the shell is ever served with a SW, static assets and some API responses can be cached separately from IDB. Partial overlap with Capacitor remote URL loading — evaluate whether agri-books.com already uses a SW for the terminal route.

5. **Instrumentation**  
   Log (privacy-safe) events: `idb_open_failed`, `sync_full_after_empty_cache`, `cold_start_ms`. That proves whether the caveat matters on H10P fleets.

**Suggested priority for Emergent:** (1) + (2) + (5) first; (3) only if field data shows IDB wipes; (4) if architecture already supports SW on that origin.
