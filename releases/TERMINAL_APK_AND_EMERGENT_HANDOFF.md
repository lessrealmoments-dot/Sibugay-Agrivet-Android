# AgriSmart Terminal (H10P) — APK + handoff for Emergent / web deploy

Repo: [Sibugay-Agrivet-Android](https://github.com/lessrealmoments-dot/Sibugay-Agrivet-Android)  
Coordination doc: [`memory/H10_PRINTER_COORDINATION.md`](../memory/H10_PRINTER_COORDINATION.md)

## What’s in `releases/`

| File | Purpose |
|------|---------|
| **`AgriSmart-Terminal-debug.apk`** | Debug build of the Capacitor shell (`com.agribooks.terminal`). Install on the H10 for testing. **Rebuild locally** after any Java change; this file is a snapshot only. |

- **Package:** `com.agribooks.terminal`  
- **App name:** AgriSmart Terminal  
- **Live URL:** The APK loads **`https://agri-books.com`** (see `frontend/capacitor.config.ts`). **Most UI/print logic is the hosted web app**, not the APK.

---

## Two pipelines (read this carefully)

### A) **Web (Emergent / deploy)** — what users see on the terminal

These files ship in the **built frontend bundle** served at **agri-books.com**:

| Area | Files (paths from repo root) |
|------|------------------------------|
| Receipt HTML/CSS (fonts, layout, QR block content) | `frontend/src/lib/PrintEngine.js` (`thermalCSS`, thermal builders) |
| Native print routing, QR image inlining (`fetch` → data URL), `feedLinesAfter` | `frontend/src/lib/PrintBridge.js` |
| Capacitor JS plugin surface (`printHtml`, `feedPaper`) | `frontend/src/lib/H10PPrinterPlugin.js` |
| Terminal sale print UI (`docCode`, extra feed, “Done”) | `frontend/src/pages/terminal/TerminalSales.jsx` |
| QuickScan / doc reprint | `frontend/src/pages/terminal/TerminalShell.jsx`, `frontend/src/pages/DocViewerPage.jsx` |

**If fonts, QR, or print buttons don’t change on the device:** production **agri-books.com** is probably still serving an **old build**. **Pushing to GitHub is not enough** — run **`yarn build`** (or your CI) and **deploy the `build/` output** to the host that serves the live site.

### B) **Android APK (local / Cursor)** — printer driver + WebView capture

| File | Role |
|------|------|
| `frontend/android/app/src/main/java/com/agribooks/terminal/H10PPrinterPlugin.java` | `SrPrinter` API, WebView→bitmap, trim blank tail, `feedLinesAfter`, `feedPaper`, delays for `<img>` |
| `frontend/android/app/src/main/java/com/agribooks/terminal/MainActivity.java` | Registers `H10PPrinterPlugin` |
| `frontend/android/app/libs/printer-release.aar` | Senraise SDK (**gitignored** — each builder must copy from supplier) |

**If paper feeds forever:** ensure a **new APK** is built after `H10PPrinterPlugin.java` changes (trim / capture height / `nextLine`).

---

## Build APK locally (maintainers)

1. Place **`printer-release.aar`** in `frontend/android/app/libs/` (from supplier **Printer SDK**).
2. Open **`frontend/android/`** in Android Studio → **Build → Build APK(s)**.  
   Or: `cd frontend/android` → `gradlew.bat assembleDebug` (Windows).
3. Output: `frontend/android/app/build/outputs/apk/debug/app-debug.apk`  
4. Optional: copy to `releases/AgriSmart-Terminal-debug.apk` and commit for sharing.

Install: sideload APK on device or `adb install -r …`.

---

## What to tell Emergent (copy-paste)

1. **Terminal = WebView + live site.** All **PrintEngine / PrintBridge / TerminalSales** changes require **`yarn build` + deploy to agri-books.com**. Git-only updates will not show on the H10 until deploy completes.  
2. **Printer reliability** depends on **both**: deployed JS (HTML, inline QR, `docCode`) **and** the installed APK (`H10PPrinterPlugin.java`).  
3. Use repo **`Sibugay-Agrivet-Android`** as the Android + full-stack source of truth; use **`memory/H10_PRINTER_COORDINATION.md`** for print architecture.  
4. **`printer-release.aar`** is not in Git; Android builders must add it per `frontend/ANDROID_BUILD_GUIDE.md`.

---

## Security / hygiene note

Debug APKs use the **debug keystore**. For Play Store or wide distribution, use **release** signing and prefer **GitHub Releases** for large binaries long-term so `git clone` stays lighter.
