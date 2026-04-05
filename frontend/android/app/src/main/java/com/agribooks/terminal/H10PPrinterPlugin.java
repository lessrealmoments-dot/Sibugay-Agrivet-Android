package com.agribooks.terminal;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import recieptservice.com.recieptservice.PrinterInterface;

/**
 * H10PPrinterPlugin — Capacitor native bridge to the H10P built-in 58mm thermal printer.
 *
 * Service: recieptservice.com.recieptservice.service.PrinterService
 * SDK:     printer-release.aar (in app/libs/)
 *
 * Flow:
 *   JS calls printHtml({ html, format })
 *     → renders HTML to Bitmap via headless WebView (same receipt as browser)
 *     → binds to PrinterService
 *     → printer.beginWork() → printer.printBitmap(bitmap) → printer.endWork()
 *
 * Printer width:
 *   58mm thermal  = 384px @ 203 DPI
 *   Full page     = 576px (A4 width approximation)
 */
@CapacitorPlugin(name = "H10PPrinter")
public class H10PPrinterPlugin extends Plugin {

    private static final String TAG = "H10PPrinter";

    private PrinterInterface printer = null;
    private boolean printerConnected = false;

    private final ServiceConnection printerServiceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            printer = PrinterInterface.Stub.asInterface(service);
            printerConnected = true;
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            printer = null;
            printerConnected = false;
        }
    };

    @Override
    public void load() {
        bindPrinterService();
    }

    /**
     * Binds to the vendor printer service (separate APK: recieptservice).
     * Returns false if bind could not be queued (package missing, etc.).
     */
    private boolean bindPrinterService() {
        try {
            Intent intent = new Intent();
            intent.setClassName(
                "recieptservice.com.recieptservice",
                "recieptservice.com.recieptservice.service.PrinterService"
            );
            boolean ok = getContext().bindService(intent, printerServiceConnection, Context.BIND_AUTO_CREATE);
            if (!ok) {
                Log.e(TAG, "bindService returned false — is the Receipt Printer service (recieptservice.com.recieptservice) installed on this device?");
            }
            return ok;
        } catch (Exception e) {
            Log.e(TAG, "bindPrinterService failed", e);
            return false;
        }
    }

    /**
     * bindService() is asynchronous; onServiceConnected runs later. Printing immediately
     * used to always fail. Wait up to timeoutMs for the connection.
     */
    private boolean waitForPrinterConnection(long timeoutMs) {
        bindPrinterService();
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (printerConnected && printer != null) {
                return true;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        if (!printerConnected || printer == null) {
            Log.e(TAG, "Printer service not ready after " + timeoutMs + "ms (connected=" + printerConnected + ", printer=" + (printer != null) + ")");
        }
        return printerConnected && printer != null;
    }

    /**
     * printHtml — accepts HTML string from PrintBridge.js, renders it to bitmap,
     * and sends to the H10P printer SDK.
     *
     * Called from JS:
     *   H10PPrinter.printHtml({ html: '<html>...</html>', format: 'thermal' | 'full_page' })
     */
    @PluginMethod
    public void printHtml(PluginCall call) {
        final String html = call.getString("html");
        final String format = call.getString("format", "thermal");

        if (html == null || html.isEmpty()) {
            call.reject("html is required");
            return;
        }

        // 58mm @ 203 DPI = 384px; full page approximation = 576px
        final int widthPx = "full_page".equals(format) ? 576 : 384;

        // Wait for AIDL bind off the UI thread (bind is async; immediate print always lost the race).
        new Thread(() -> {
            boolean ready = waitForPrinterConnection(12000);
            if (!ready) {
                call.reject("Printer service not connected. On H10P/Senraise devices, ensure the Receipt Printer service app (package recieptservice.com.recieptservice) is installed — ask your supplier if printing still fails.");
                return;
            }

            android.app.Activity activity = getActivity();
            if (activity == null) {
                call.reject("Cannot print: app activity is not ready.");
                return;
            }

            activity.runOnUiThread(() -> renderHtmlToBitmap(html, widthPx, bitmap -> {
                if (bitmap == null) {
                    call.reject("Failed to render receipt HTML to bitmap");
                    return;
                }

                new Thread(() -> {
                    try {
                        printer.beginWork();
                        printer.printBitmap(bitmap);
                        printer.nextLine(3);   // Feed 3 blank lines so receipt tears cleanly
                        printer.endWork();
                        bitmap.recycle();
                        call.resolve(new JSObject().put("success", true));
                    } catch (RemoteException e) {
                        call.reject("Print SDK error: " + e.getMessage());
                    } catch (Exception e) {
                        call.reject("Print failed: " + e.getMessage());
                    }
                }).start();
            }));
        }, "h10p-print-wait").start();
    }

    /**
     * checkStatus — returns whether the printer service is bound and ready.
     * Called from JS as a health check before showing print buttons.
     */
    @PluginMethod
    public void checkStatus(PluginCall call) {
        new Thread(() -> {
            waitForPrinterConnection(4000);
            JSObject result = new JSObject();
            result.put("connected", printerConnected && printer != null);
            call.resolve(result);
        }, "h10p-status").start();
    }

    /**
     * Render an HTML string to a Bitmap using a headless (off-screen) WebView.
     * The WebView is sized to widthPx wide and expands vertically to fit content.
     * Callback is called on the main thread with the rendered Bitmap.
     */
    private void renderHtmlToBitmap(String html, int widthPx, BitmapCallback callback) {
        WebView webView = new WebView(getContext());
        webView.setBackgroundColor(Color.WHITE);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(false); // No JS needed for receipt rendering
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setTextZoom(100);

        // Initial measure at the target width
        webView.measure(
            View.MeasureSpec.makeMeasureSpec(widthPx, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        );

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                view.post(() -> {
                    // Determine rendered content height
                    int contentHeight = view.getContentHeight();
                    if (contentHeight <= 0) contentHeight = 2000;

                    // Lay out at the final size
                    view.measure(
                        View.MeasureSpec.makeMeasureSpec(widthPx, View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(contentHeight, View.MeasureSpec.EXACTLY)
                    );
                    view.layout(0, 0, widthPx, contentHeight);

                    // Render to bitmap
                    try {
                        Bitmap bitmap = Bitmap.createBitmap(widthPx, contentHeight, Bitmap.Config.RGB_565);
                        Canvas canvas = new Canvas(bitmap);
                        canvas.drawColor(Color.WHITE);
                        view.draw(canvas);
                        callback.onBitmap(bitmap);
                    } catch (OutOfMemoryError e) {
                        callback.onBitmap(null);
                    } finally {
                        view.destroy();
                    }
                });
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                // Still attempt to render whatever loaded
                view.post(() -> {
                    int h = Math.max(view.getContentHeight(), 200);
                    view.measure(
                        View.MeasureSpec.makeMeasureSpec(widthPx, View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY)
                    );
                    view.layout(0, 0, widthPx, h);
                    Bitmap bitmap = Bitmap.createBitmap(widthPx, h, Bitmap.Config.RGB_565);
                    Canvas canvas = new Canvas(bitmap);
                    canvas.drawColor(Color.WHITE);
                    view.draw(canvas);
                    callback.onBitmap(bitmap);
                    view.destroy();
                });
            }
        });

        // Load the HTML. Note: no base URL needed (receipt is self-contained except QR image).
        // External QR image (api.qrserver.com) loads over internet — H10P has 4G.
        webView.loadDataWithBaseURL(
            "https://agri-books.com",   // baseUrl for relative resource resolution
            html,
            "text/html",
            "UTF-8",
            null
        );
    }

    interface BitmapCallback {
        void onBitmap(Bitmap bitmap);
    }
}
