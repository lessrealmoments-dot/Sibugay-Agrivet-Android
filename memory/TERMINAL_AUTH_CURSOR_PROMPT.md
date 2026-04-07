# AgriSmart Terminal — Device Authentication Hardening

## Web (Emergent) + Android (Cursor) coordination

**Created:** 2026-04-06  
**Repo copy:** `memory/TERMINAL_AUTH_CURSOR_PROMPT.md`

### Android status (Cursor)

- [x] `DeviceIdentityPlugin.java` — `getDeviceId()` → `Settings.Secure.ANDROID_ID`
- [x] `MainActivity.java` — `registerPlugin(DeviceIdentityPlugin.class)`
- [ ] `frontend/src/plugins/DeviceIdentityPlugin.js` — Emergent
- [ ] Pairing + `DocViewerPage` + backend — Emergent

Plugin name must match JS: **`DeviceIdentity`** ↔ `registerPlugin('DeviceIdentity', ...)`.

**Do not** change printer/scanner files for this feature (`PrintEngine.js`, `PrintBridge.js`, `H10PPrinterPlugin.*`) unless fixing unrelated bugs.

---

## 1. Purpose

Bind each terminal session to the **physical Android device** that paired, so copying `localStorage` to another browser/device cannot reuse `terminal_id` for QR actions.

---

## 2. Ownership map

| Component | Owner |
|-----------|--------|
| `TerminalPairScreen.jsx` | Emergent — send `device_id` when pairing |
| `TerminalShell.jsx` | Emergent — keep `deviceId` in session / navigate to doc |
| `DocViewerPage.jsx` | Emergent — pass `device_id` on QR actions |
| `DeviceIdentityPlugin.java` | **Cursor** |
| `MainActivity.java` | **Cursor** |
| `frontend/src/plugins/DeviceIdentityPlugin.js` | Emergent |
| `backend/routes/terminal.py` | Emergent — store `device_id` |
| `backend/routes/qr_actions.py` | Emergent — verify in `_verify_terminal_session` |

---

## 3. Security gap (today)

`terminal_sessions` checks `terminal_id` + active. It does **not** prove the caller is the same device. Stolen or copied session data can be replayed from another client.

---

## 4. Fix — Android ID

Use **`Settings.Secure.ANDROID_ID`** (no `READ_PHONE_STATE`). Send on pair; store on session; resend on each QR action; backend compares.

---

## 5. Android implementation reference

### `DeviceIdentityPlugin.java`

Path: `frontend/android/app/src/main/java/com/agribooks/terminal/DeviceIdentityPlugin.java`

- `@CapacitorPlugin(name = "DeviceIdentity")`
- `@PluginMethod getDeviceId` → `{ deviceId: "<hex or unknown>" }`

### `MainActivity.java`

Register **before** `super.onCreate()`:

```java
registerPlugin(H10PPrinterPlugin.class);
registerPlugin(DeviceIdentityPlugin.class);
super.onCreate(savedInstanceState);
```

No `AndroidManifest.xml` permission changes for `ANDROID_ID`.

---

## 6. Web + backend (Emergent)

See Emergent spec: JS `DeviceIdentity` bridge, pairing bodies, `TerminalShell` / `DocViewerPage` query param or session, `terminal.py` session document field `device_id`, `qr_actions.py` `_verify_terminal_session(terminal_id, device_id)` with backward compatibility when `stored_device_id` is empty.

### Backward compatibility

If session has **no** `device_id`, do not reject solely on device mismatch (legacy sessions). If session **has** `device_id`, require match when client sends `device_id`.

---

## 7. Flow after full rollout

```
Pair:  getDeviceId() → POST pair with device_id → DB stores device_id → localStorage includes deviceId
Action: POST qr-actions/... with terminal_id + device_id → verify match → PIN → proceed
```

---

## 8. Testing

1. New pair → MongoDB `terminal_sessions.device_id` set  
2. Action from same device → OK  
3. Copy `agrismart_terminal` to desktop browser → expect **403 / DEVICE_MISMATCH** once backend + JS enforce (browser fallback id ≠ Android id)  
4. Legacy session without `device_id` → still works until expired / re-paired  

---

## 9. Optional admin

Expire sessions missing `device_id` to force re-pair (Emergent endpoint as in original design doc).
