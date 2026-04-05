/**
 * PrintBridge.js — Environment-aware print router.
 *
 * SINGLE entry point for ALL printing in the AgriSmart Terminal.
 * Routes print calls to the correct execution path:
 *
 *   Capacitor APK (H10P device):
 *     PrintEngine.generateHtml() → H10PPrinterPlugin.printHtml() → native SDK → 58mm paper
 *
 *   Web browser (desktop admin / dev):
 *     PrintEngine.print() → window.open() + window.print() → browser print dialog
 *
 * IMPORTANT: Do NOT call PrintEngine.print() directly from terminal components.
 *            Always use PrintBridge.print() so the H10P printer works.
 *
 * Affected call sites (these import PrintBridge instead of PrintEngine):
 *   - TerminalSales.jsx       (sale receipt after checkout)
 *   - TerminalShell.jsx       (QuickScan sheet reprint buttons)
 *   - DocViewerPage.jsx       (Tier 2 reprint buttons)
 *
 * Non-terminal pages (SalesPage, BranchTransferPage, etc.) continue using
 * PrintEngine.print() directly — they are desktop admin pages, not H10P pages.
 */
import { Capacitor } from '@capacitor/core';
import PrintEngine from './PrintEngine';
import { H10PPrinter } from './H10PPrinterPlugin';

let _nativePrinterReady = null; // Cached status check promise

/** Embed remote QR images as data URLs so the Android print WebView captures them reliably. */
async function inlineQrServerImages(html) {
  if (!html || !html.includes('api.qrserver.com')) return html;
  const urlRegex = /https:\/\/api\.qrserver\.com\/v1\/create-qr-code\/[^"'>\s]+/g;
  const urls = [...new Set(html.match(urlRegex) || [])];
  let out = html;
  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const buf = await res.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = '';
      for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
      const b64 = btoa(binary);
      const ct = res.headers.get('content-type') || 'image/png';
      const dataUrl = `data:${ct};base64,${b64}`;
      out = out.split(url).join(dataUrl);
    } catch (e) {
      console.warn('[PrintBridge] QR inline failed', e);
    }
  }
  return out;
}

const PrintBridge = {
  /**
   * Main print function — matches PrintEngine.print() signature exactly.
   * Drop-in replacement: swap `import PrintEngine` → `import PrintBridge`.
   */
  /**
   * @param {object} opts
   * @param {number} [opts.feedLinesAfter] - Blank lines after bitmap (default 4). Use 6–10 if tear cut is tight.
   */
  async print({ type, data, format = 'thermal', businessInfo = {}, docCode = '', feedLinesAfter } = {}) {
    if (Capacitor.isNativePlatform()) {
      // Native H10P path: generate HTML then send to the printer SDK
      try {
        let html = PrintEngine.generateHtml({ type, data, format, businessInfo, docCode });
        html = await inlineQrServerImages(html);
        const payload = { html, format };
        if (feedLinesAfter != null && Number.isFinite(Number(feedLinesAfter))) {
          payload.feedLinesAfter = Math.max(0, Math.min(24, Math.round(Number(feedLinesAfter))));
        }
        await H10PPrinter.printHtml(payload);
      } catch (err) {
        console.error('[PrintBridge] Native print failed:', err);
        // Fallback: let the user know the printer isn't ready
        throw err;
      }
    } else {
      // Browser path: use existing PrintEngine (opens popup + window.print())
      PrintEngine.print({ type, data, format, businessInfo, docCode });
    }
  },

  /**
   * Check if the native printer is connected (H10P only).
   * Returns { connected: true/false }.
   * Always returns { connected: false } in a browser.
   */
  async checkPrinterStatus() {
    if (!Capacitor.isNativePlatform()) {
      return { connected: false };
    }
    try {
      return await H10PPrinter.checkStatus();
    } catch {
      return { connected: false };
    }
  },

  /** True when running inside the Capacitor APK */
  isNative() {
    return Capacitor.isNativePlatform();
  },

  /** Pass-through so callers don't need to import PrintEngine for doc type detection */
  getDocType(invoice) {
    return PrintEngine.getDocType(invoice);
  },

  /** Advance paper only (H10P / SrPrinter). No-op in browser. */
  async feedPaper(lines = 8) {
    if (!Capacitor.isNativePlatform()) return;
    const n = Math.max(1, Math.min(40, Math.round(Number(lines)) || 8));
    await H10PPrinter.feedPaper({ lines: n });
  },
};

export default PrintBridge;
