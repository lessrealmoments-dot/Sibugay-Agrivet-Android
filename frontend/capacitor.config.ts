import type { CapacitorConfig } from '@capacitor/cli';

/**
 * AgriSmart Terminal — Capacitor APK config
 *
 * LIVE URL mode: The APK always loads agri-books.com (no rebuild needed for updates).
 * The WebView is locked to agri-books.com only.
 *
 * Printer: Native H10P plugin bridges window.PrintBridge calls to the
 * recieptservice.com.recieptservice.service.PrinterService AIDL service.
 */
const config: CapacitorConfig = {
  appId: 'com.agribooks.terminal',
  appName: 'AgriSmart Terminal',
  webDir: 'build',

  // Live update: APK always loads the deployed web app — no rebuild for updates
  server: {
    url: 'https://agri-books.com',
    cleartext: false,
    androidScheme: 'https',
  },

  android: {
    // Allow HID scanner keyboard input (hardware barcode scanner)
    captureInput: true,
    // Disable remote debugging in production
    webContentsDebuggingEnabled: false,
    // App label shown on home screen
    backgroundColor: '#1A4D2E',
  },

  plugins: {
    // H10P printer plugin is a custom native plugin — no Capacitor plugin config needed
    // It is registered manually in MainActivity.kt
  },
};

export default config;
