/**
 * H10PPrinterPlugin.js — Capacitor JavaScript interface for the H10P native printer plugin.
 *
 * When running as a Capacitor APK on the H10P, this calls the native Java plugin
 * (H10PPrinterPlugin.java) which renders the HTML to a Bitmap and sends it to
 * the recieptservice printer SDK.
 *
 * When running in a web browser, falls back to window.open + window.print().
 */
import { registerPlugin } from '@capacitor/core';

/**
 * Web fallback implementation — used when running in a browser (not the APK).
 * Delegates to window.open + window.print() exactly as PrintEngine does.
 */
const H10PPrinterWeb = {
  async printHtml({ html, format }) {
    const winWidth = format === 'full_page' ? 900 : 400;
    const win = window.open('', '_blank', `width=${winWidth},height=700`);
    if (!win) {
      throw new Error('Popup blocked. Please allow popups to print.');
    }
    win.document.write(html);
    win.document.close();
    win.focus();
  },
  async checkStatus() {
    return { connected: false }; // Browser — no native printer
  },
};

/**
 * Register the Capacitor plugin.
 * On native Android: delegates to H10PPrinterPlugin.java
 * On web/browser:    delegates to H10PPrinterWeb above
 */
const H10PPrinter = registerPlugin('H10PPrinter', {
  web: () => H10PPrinterWeb,
});

export { H10PPrinter };
