# AgriSmart Terminal — Android APK Build Guide

## Overview
The AgriSmart Terminal is packaged as a Capacitor Android APK that wraps the web app
hosted at https://agri-books.com. The APK is "live URL" mode — it always loads the
latest version of the web app. No APK rebuild is needed when the web app is updated.

The only reason to rebuild the APK is if:
- The Capacitor plugin changes (printer integration)
- Android permissions need updating
- The app ID or name changes

---

## Prerequisites (on your local machine)

1. **Android Studio** (latest stable — Hedgehog or newer)
   Download: https://developer.android.com/studio

2. **Android SDK** — API 34 (Android 14, required for H10P)
   Install via Android Studio → SDK Manager

3. **Java 17** (included with Android Studio)

4. **The Senraise printer SDK file** — `printer-release.aar`
   (Provided by your H10P supplier — Senraise)

---

## Step 1: Get the Code

If using GitHub (recommended):
```bash
git clone <your-repo-url>
cd frontend
```

Or download a ZIP from your Emergent project → "Save to GitHub" → clone.

---

## Step 2: Place the Printer SDK

Copy `printer-release.aar` (from your Senraise SDK folder) to:
```
frontend/android/app/libs/printer-release.aar
```

**This file must be present before building. Without it, the build will fail.**

---

## Step 3: Open in Android Studio

1. Open **Android Studio**
2. Click **Open** (not "New Project")
3. Navigate to and select the **`frontend/android/`** folder
4. Wait for Gradle sync to complete (first time may take 5-10 minutes — downloads dependencies)

---

## Step 4: Configure for H10P (verify these settings)

In Android Studio, open `app/build.gradle` and confirm:
- `minSdkVersion 22` (or as set in variables.gradle)
- `targetSdkVersion 34`
- The `printer-release.aar` dependency is listed

---

## Step 5: Build the APK

**Debug APK (for testing):**
- Menu: Build → Build Bundle(s) / APK(s) → Build APK(s)
- APK location: `android/app/build/outputs/apk/debug/app-debug.apk`

**Release APK (for production):**
- Menu: Build → Generate Signed Bundle / APK
- Choose APK, create or use your keystore
- APK location: `android/app/build/outputs/apk/release/app-release.apk`

---

## Step 6: Install on H10P

**Option A — Android Studio (USB):**
1. Enable Developer Options on H10P: Settings → About → tap Build Number 7 times
2. Enable USB Debugging: Settings → Developer Options → USB Debugging
3. Connect H10P via USB
4. In Android Studio: Run → Run 'app' (or use the green play button)

**Option B — Manual sideload (recommended for production):**
1. Copy the APK to H10P via USB or email/cloud storage
2. On H10P: Settings → Security → Allow Unknown Sources
3. Open the APK file on the device → Install

---

## How the App Works After Install

1. First launch shows the **Pairing Screen** (6-character code)
2. On your PC browser, go to https://agri-books.com → Settings → Connect Terminal
3. Enter the code + select the branch
4. Terminal is now paired and shows the Sales/PO/Transfers tabs
5. The built-in 58mm printer works via the native plugin

---

## Troubleshooting

**"Printer service not connected"**
- The printer SDK (recieptservice) must be installed on the H10P
- On H10P, check if "recieptservice.com.recieptservice" app is present
- Some Senraise devices ship with the service pre-installed; others need the .apk from Senraise

**"App not installed" on H10P**
- Check Unknown Sources is enabled
- Check minSdkVersion matches H10P's Android version

**Gradle sync fails**
- Verify `printer-release.aar` is in `android/app/libs/`
- File → Sync Project with Gradle Files

**White screen on launch**
- The APK loads https://agri-books.com — ensure the device has internet
- Check the server URL in `capacitor.config.ts`

---

## File Structure Reference

```
frontend/
  capacitor.config.ts          ← Capacitor config (live URL: agri-books.com)
  android/                     ← Android project (open this in Android Studio)
    app/
      libs/
        printer-release.aar    ← ⚠️ YOU MUST ADD THIS MANUALLY
        README.txt
      src/main/
        java/com/agribooks/terminal/
          MainActivity.java    ← Registers H10PPrinterPlugin
          H10PPrinterPlugin.java ← Native printer bridge (HTML→Bitmap→SDK)
        aidl/recieptservice/com/recieptservice/
          PrinterInterface.aidl  ← H10P printer AIDL interface
          PSAMCallback.aidl
          PSAMData.aidl
      build.gradle             ← Includes printer-release.aar dependency
  src/lib/
    PrintBridge.js             ← JS router: native APK → H10PPrinterPlugin
    H10PPrinterPlugin.js       ← Capacitor JS interface
    PrintEngine.js             ← Receipt HTML generator (unchanged)
```

---

## Print Flow Summary

```
User taps Print button
  ↓
PrintBridge.print({ type, data, format, businessInfo, docCode })
  ↓ (detects Capacitor.isNativePlatform() = true on H10P)
PrintEngine.generateHtml() → receipt HTML string
  ↓
H10PPrinterPlugin.printHtml({ html, format: 'thermal' })
  ↓ (Capacitor bridge → native Java)
H10PPrinterPlugin.java
  ↓ renders HTML to Bitmap via headless WebView at 384px (58mm @203DPI)
  ↓ binds to recieptservice.com.recieptservice.service.PrinterService
  ↓ printer.beginWork() → printer.printBitmap(bitmap) → printer.endWork()
  ↓
58mm thermal paper ✓
```

---

## Updating the App

Since the APK uses live URL mode pointing to https://agri-books.com:
- **Web app updates** (new features, bug fixes) → just deploy to agri-books.com. APK picks it up automatically on next launch.
- **Printer plugin updates** → rebuild APK and reinstall.
