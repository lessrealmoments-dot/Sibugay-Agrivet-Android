# Thermal receipt — font, color, and QR spec (for Emergent + local APK)

**Source of truth in this repo:** `frontend/src/lib/PrintEngine.js`, `frontend/src/lib/PrintBridge.js`  
**Applies to:** `format: 'thermal'` (58mm), captured as a **384 CSS px** wide bitmap in the H10P native path.

---

## 1. Layout viewport (why test prints look “clearer”)

Thermal HTML includes:

```html
<meta name="viewport" content="width=384, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
```

**Meaning:** The printable layout is locked to **384px** logical width so text and tables match the **~58mm / ~384px** bitmap the native printer captures. Without this, high-DPI phone WebViews scale layout ~2× and content can look clipped or fuzzy.

**Emergent:** Keep this meta on **all** thermal `generateHtml()` output; do not rely on Java or the printer SDK to set CSS viewport.

---

## 2. Thermal typography (font family + sizes)

| Selector / use | Font | Size | Weight / notes |
|----------------|------|------|----------------|
| `body` | `'Courier New', monospace` | **11px** | `line-height: 1.35`, `color: #000` |
| `.header .biz-name` | (inherits) | **13px** | `bold`, `uppercase` |
| `.header .biz-detail` | (inherits) | **9px** | — |
| `.doc-title` | (inherits) | **12px** | `bold`, dashed top/bottom border |
| `.meta-row` | (inherits) | **10px** | flex row |
| `.meta-row .label` | (inherits) | **10px** | `color: #444` |
| `.items-table` | (inherits) | **10px** | `table-layout: fixed` |
| `.items-table .item-detail` | (inherits) | **9px** | `color: #333` |
| `.items-table .item-total` | (inherits) | **10px** | `bold`, right-aligned, tabular nums |
| `.totals .row` | (inherits) | **10px** | — |
| `.totals .grand` | (inherits) | **13px** | `bold`, solid top border |
| `.payment-info` | (inherits) | **10px** | — |
| `.trust-terms` | (inherits) | **8px** | body text |
| `.trust-terms .terms-title` | (inherits) | **9px** | `bold`, centered |
| `.signature-line .sig-label` | (inherits) | **8px** | `color: #666` |
| `.footer` | (inherits) | **8px** | `color: #666` |
| `.qr-code-text` | (inherits) | **11px** | `bold`, `letter-spacing: 1px` (`qrImgTagPlain` uses inline **9px** for plain text under QR) |
| `.qr-hint` | (inherits) | **8px** | `color: #666` |

**Page / shell:** `@page { size: 58mm auto; margin: 0; }` — `body` padding **2px 3px**.

---

## 3. Thermal colors (effective on thermal paper)

Thermal output is **monochrome**. CSS colors map to **black vs lighter gray** when rasterized:

| Color | Typical use |
|-------|-------------|
| `#000` | Primary body text |
| `#333` | Item sub-lines |
| `#444` | Meta labels |
| `#666` | Footer, hints, signature labels |

**Tuning tip:** Darker text (`#000` only) can look slightly sharper but less hierarchy; slightly lighter labels (`#444` / `#666`) reduce visual noise. Avoid colors that won’t rasterize well (very light grays may disappear).

---

## 4. QR code — protocol and payload

### 4.1 Image generation (HTTP API)

QRs are **PNG images** from a public generator (not an in-app QR library):

**Base URL:** `https://api.qrserver.com/v1/create-qr-code/`

**Query parameters (both modes):**

| Parameter | Value | Notes |
|-----------|--------|--------|
| `size` | `{N}x{N}` | Pixel dimensions of the **image** (see sizes below) |
| `data` | URL-encoded string | **Payload** scanned by the phone (see 4.2) |
| `margin` | `4` | Quiet zone around the module pattern |

**Example pattern (document link):**

```text
https://api.qrserver.com/v1/create-qr-code/?size=92x92&data=<URL_ENCODED>&margin=4
```

### 4.2 Payload semantics (what the QR *contains*)

**Mode A — `qrImgTag(code, size)`** (when `docCode` is present)

- Encoded string is a **full document URL**, not the bare code:
- **Formula:** `{window.location.origin}/doc/{code}`
- **Example:** `https://agri-books.com/doc/ABC123` (exact origin depends on where the WebView is loaded)

**Mode B — `qrImgTagPlain(text, size)`** (fallback when there is no `docCode`)

- Encoded string is **plain text**, e.g. `Invoice INV-2024-001`
- Used on thermal order slip when `docCode` is missing but `invoice_number` exists.

**Emergent:** If you change routing (e.g. deep links), keep **either** full HTTPS URLs **or** a documented plain-text format so scanners and support docs stay aligned.

### 4.3 Sizes used in this codebase

| Context | Typical `size` (px) |
|---------|---------------------|
| Thermal order slip / trust / PO / branch transfer / return (with doc) | **92** |
| Full-page order / trust / PO / branch transfer | **100** |
| Full-page expense / return / statement | **80** |
| `qrImgTag` default if caller omits size | **120** |
| `qrImgTagPlain` default | **80** (thermal order slip passes **92**) |

HTML wraps the image in `.qr-block` with optional captions:

- `.qr-code-text` — human-readable code or invoice line under the image  
- `.qr-hint` — e.g. “Scan to view document” / “Scan for reference”

---

## 5. Native APK vs browser (QR reliability)

| Path | Behavior |
|------|----------|
| **Capacitor / H10P** (`PrintBridge.print`) | `PrintEngine.generateHtml()` → **`inlineQrServerImages()`** fetches each `api.qrserver.com` URL and replaces it with a **`data:image/png;base64,...`** URL so the off-screen WebView **always** paints the QR before the SDK captures the bitmap. |
| **Browser** (`PrintEngine.print`) | Injected script waits for **`img.onload` / `onerror`** for all images, then `window.print()`; **6s** safety timeout. |

**Emergent:** Any new thermal template that adds QR images must either use the same `api.qrserver.com` pattern (so `PrintBridge` inlines it) or use **data URLs** / same-origin images so native capture does not race.

---

## 6. Quick reference for tuning (no layout change)

To adjust **only** clarity (as you asked), the lowest-touch knobs in `PrintEngine.js` are:

1. **`thermalCSS`** — `body` `font-size` (default **11px**), `color` (**#000**), and label grays (**#444**, **#666**).  
2. **QR `size` argument** in `qrImgTag(docCode, 92)` / `qrImgTagPlain(..., 92)` — larger **N** = more modules printed (often easier to scan; uses more vertical space).  
3. **`margin=4`** on the QR API — increasing (e.g. **6–8**) can help cheap scanners; must stay in the generator URL.  
4. **Keep `THERMAL_VIEWPORT_META`** — changing font sizes without keeping width=384 can reintroduce clipping.

---

## 7. Machine-readable summary (Emergent)

```json
{
  "thermal_viewport_css_px": 384,
  "thermal_body": { "fontFamily": "Courier New, monospace", "fontSizePx": 11, "color": "#000" },
  "qr_image_api": "https://api.qrserver.com/v1/create-qr-code/",
  "qr_query_params": { "size": "NxN", "data": "url-encoded payload", "margin": 4 },
  "qr_payload_document_mode": "{origin}/doc/{docCode}",
  "qr_payload_plain_mode": "arbitrary string e.g. Invoice {invoice_number}",
  "thermal_qr_image_size_px": 92,
  "native_print_qr_handling": "fetch api.qrserver.com → inline data URL before H10P bitmap capture"
}
```

---

## 8. File map

| Concern | File | Symbols |
|---------|------|---------|
| Thermal CSS + QR HTML | `PrintEngine.js` | `thermalCSS`, `THERMAL_VIEWPORT_META`, `qrImgTag`, `qrImgTagPlain`, `*Thermal()` builders |
| Native QR inlining | `PrintBridge.js` | `inlineQrServerImages` |

If the **live** `agri-books.com` bundle differs from this repo, merge this spec into the Emergent codebase or treat this file as the **terminal APK** contract.
