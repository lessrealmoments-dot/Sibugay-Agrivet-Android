package com.agribooks.terminal;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import com.sr.SrPrinter;

import java.lang.reflect.Field;

/**
 * H10PPrinterPlugin — Senraise H10P: HTML → WebView → Bitmap → SrPrinter.
 * WebView must use Activity context and be attached to the window for layout/draw on many devices.
 */
@CapacitorPlugin(name = "H10PPrinter")
public class H10PPrinterPlugin extends Plugin {

    private static final String TAG = "H10PPrinter";

    /** JSON numbers from JS often arrive as Double in JSObject. */
    private static int optInt(PluginCall call, String key, int def) {
        try {
            Object v = call.getData().opt(key);
            if (v == null) return def;
            if (v instanceof Integer) return (Integer) v;
            if (v instanceof Double) return ((Double) v).intValue();
            if (v instanceof Long) return ((Long) v).intValue();
            if (v instanceof String) return Integer.parseInt((String) v);
        } catch (Exception ignored) {
        }
        return def;
    }

    private static boolean waitForSrPrinterReady(Context appContext, long timeoutMs) {
        SrPrinter.getInstance(appContext);
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            try {
                Field f = SrPrinter.class.getDeclaredField("printerInterface");
                f.setAccessible(true);
                if (f.get(null) != null) {
                    Log.e(TAG, "waitForSrPrinterReady: bound OK");
                    return true;
                }
            } catch (NoSuchFieldException e) {
                Log.e(TAG, "SrPrinter field printerInterface missing", e);
                return false;
            } catch (Exception e) {
                Log.e(TAG, "waitForSrPrinterReady reflect error", e);
                return false;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
        Log.e(TAG, "waitForSrPrinterReady: TIMEOUT — try printing anyway (SrPrinter may still work)");
        return true;
    }

    private static boolean isSrPrinterBound() {
        try {
            Field f = SrPrinter.class.getDeclaredField("printerInterface");
            f.setAccessible(true);
            return f.get(null) != null;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public void load() {
        try {
            SrPrinter.getInstance(getContext().getApplicationContext());
        } catch (Exception e) {
            Log.w(TAG, "SrPrinter warm-up", e);
        }
    }

    /**
     * Trim blank rows from bottom of receipt bitmap so the printer does not feed endless white paper.
     */
    private static Bitmap trimTrailingBlank(Bitmap src) {
        if (src == null || src.isRecycled()) return src;
        int w = src.getWidth();
        int h = src.getHeight();
        if (h < 30 || w < 8) return src;
        final int whiteThreshold = 250;
        int bottom = h - 1;
        while (bottom > 24) {
            if (!isRowMostlyBlank(src, w, bottom, whiteThreshold)) break;
            bottom--;
        }
        bottom += 16;
        if (bottom >= h - 2) return src;
        try {
            Bitmap out = Bitmap.createBitmap(src, 0, 0, w, bottom + 1);
            if (out != src) src.recycle();
            Log.e(TAG, "trimTrailingBlank " + h + " -> " + (bottom + 1));
            return out;
        } catch (Exception e) {
            Log.e(TAG, "trimTrailingBlank failed", e);
            return src;
        }
    }

    private static boolean isRowMostlyBlank(Bitmap b, int width, int y, int thr) {
        int step = Math.max(1, width / 40);
        for (int x = 0; x < width; x += step) {
            int p = b.getPixel(x, y);
            if (Color.red(p) < thr || Color.green(p) < thr || Color.blue(p) < thr) {
                return false;
            }
        }
        return true;
    }

    @PluginMethod
    public void printHtml(PluginCall call) {
        final String html = call.getString("html");
        final String format = call.getString("format", "thermal");
        final int feedLinesAfter = optInt(call, "feedLinesAfter", 4);

        Log.e(TAG, "printHtml ENTRY len=" + (html != null ? html.length() : 0));

        if (html == null || html.isEmpty()) {
            call.reject("html is required");
            return;
        }

        final int widthPx = "full_page".equals(format) ? 576 : 384;
        final Context appCtx = getContext().getApplicationContext();

        new Thread(() -> {
            boolean waited = waitForSrPrinterReady(appCtx, 12000);
            if (!waited) {
                Log.e(TAG, "wait returned false (unexpected)");
            }

            final Activity activity = getActivity();
            if (activity == null) {
                Log.e(TAG, "getActivity() null");
                call.reject("Cannot print: app activity is not ready.");
                return;
            }

            activity.runOnUiThread(() -> renderHtmlToBitmap(activity, html, widthPx, bitmap -> {
                if (bitmap == null) {
                    Log.e(TAG, "bitmap null after WebView render");
                    call.reject("Failed to render receipt HTML to bitmap");
                    return;
                }

                Bitmap toPrint = trimTrailingBlank(bitmap);

                try {
                    SrPrinter sp = SrPrinter.getInstance(appCtx);
                    Log.e(TAG, "Printing bitmap " + toPrint.getWidth() + "x" + toPrint.getHeight()
                        + " cfg=" + toPrint.getConfig());
                    try {
                        sp.printBitmap(toPrint);
                    } catch (Exception e1) {
                        Log.e(TAG, "printBitmap err, try immediately", e1);
                        sp.printBitmapImmediately(toPrint);
                    }
                    int feed = Math.max(0, Math.min(feedLinesAfter, 24));
                    if (feed > 0) sp.nextLine(feed);
                    toPrint.recycle();
                    call.resolve(new JSObject().put("success", true));
                    Log.e(TAG, "printHtml SUCCESS");
                } catch (Exception e) {
                    Log.e(TAG, "SrPrinter failed", e);
                    try {
                        toPrint.recycle();
                    } catch (Exception ignored) {
                    }
                    call.reject("Print failed: " + e.getMessage());
                }
            }));
        }, "h10p-print-wait").start();
    }

    /**
     * Advance paper without printing (e.g. align tear line after an uneven cut).
     * lines: typically 4–12 for a few mm on 58mm printers.
     */
    @PluginMethod
    public void feedPaper(PluginCall call) {
        int lines = optInt(call, "lines", 6);
        lines = Math.max(1, Math.min(lines, 40));
        final int feed = lines;
        final Context appCtx = getContext().getApplicationContext();
        final Activity activity = getActivity();
        if (activity == null) {
            call.reject("Activity not ready");
            return;
        }
        activity.runOnUiThread(() -> {
            try {
                SrPrinter.getInstance(appCtx).nextLine(feed);
                call.resolve(new JSObject().put("success", true));
            } catch (Exception e) {
                Log.e(TAG, "feedPaper", e);
                call.reject("Feed failed: " + e.getMessage());
            }
        });
    }

    @PluginMethod
    public void checkStatus(PluginCall call) {
        new Thread(() -> {
            Context appCtx = getContext().getApplicationContext();
            SrPrinter.getInstance(appCtx);
            waitForSrPrinterReady(appCtx, 4000);
            JSObject result = new JSObject();
            result.put("connected", isSrPrinterBound());
            call.resolve(result);
        }, "h10p-status").start();
    }

    /**
     * Attach WebView to activity content so Chromium lays out; then capture to bitmap.
     */
    private void renderHtmlToBitmap(Activity activity, String html, int widthPx, BitmapCallback callback) {
        Log.e(TAG, "renderHtmlToBitmap start widthPx=" + widthPx);

        final ViewGroup root = activity.findViewById(android.R.id.content);
        final WebView webView = new WebView(activity);
        webView.setBackgroundColor(Color.WHITE);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(false);
        settings.setLoadWithOverviewMode(false);
        settings.setUseWideViewPort(false);
        settings.setTextZoom(100);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        final int maxHeight = 16000;
        FrameLayout.LayoutParams wvLp = new FrameLayout.LayoutParams(widthPx, maxHeight);
        wvLp.leftMargin = -10000;
        wvLp.topMargin = 0;
        webView.setLayoutParams(wvLp);

        final FrameLayout holder = new FrameLayout(activity);
        FrameLayout.LayoutParams holderLp = new FrameLayout.LayoutParams(widthPx, maxHeight);
        holderLp.leftMargin = -10000;
        holder.setLayoutParams(holderLp);
        holder.addView(webView);

        final Runnable[] cleanup = new Runnable[1];
        cleanup[0] = () -> {
            try {
                root.removeView(holder);
            } catch (Exception ignored) {
            }
            try {
                webView.destroy();
            } catch (Exception ignored) {
            }
        };

        final boolean[] done = {false};
        final Runnable finishFail = () -> {
            if (done[0]) return;
            done[0] = true;
            cleanup[0].run();
            callback.onBitmap(null);
        };

        final Handler main = new Handler(Looper.getMainLooper());
        main.postDelayed(() -> {
            if (!done[0]) {
                Log.e(TAG, "WebView capture TIMEOUT");
                finishFail.run();
            }
        }, 25000);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int progress) {
                if (progress == 100) {
                    Log.e(TAG, "WebView progress 100");
                }
            }
        });

        final boolean hasRemoteImg = html != null && html.contains("<img");
        final long captureDelayMs = hasRemoteImg ? 2400L : 600L;

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                Log.e(TAG, "onPageFinished url=" + url + " captureDelayMs=" + captureDelayMs);
                view.postDelayed(() -> captureToBitmap(view, widthPx, bitmap -> {
                    if (done[0]) return;
                    done[0] = true;
                    cleanup[0].run();
                    callback.onBitmap(bitmap);
                }), captureDelayMs);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                Log.e(TAG, "onReceivedError " + errorCode + " " + description + " " + failingUrl);
                view.postDelayed(() -> {
                    if (done[0]) return;
                    done[0] = true;
                    int h = Math.max(view.getContentHeight(), 400);
                    captureSized(view, widthPx, h, bitmap -> {
                        cleanup[0].run();
                        callback.onBitmap(bitmap);
                    });
                }, 500);
            }
        });

        root.addView(holder);
        Log.e(TAG, "loadDataWithBaseURL…");
        webView.loadDataWithBaseURL(
            "https://agri-books.com",
            html,
            "text/html",
            "UTF-8",
            null
        );
    }

    private void captureToBitmap(WebView view, int widthPx, BitmapCallback callback) {
        int contentHeight = view.getContentHeight();
        Log.e(TAG, "capture contentHeight=" + contentHeight);
        if (contentHeight <= 0) {
            contentHeight = 1200;
        }
        contentHeight = Math.min(contentHeight + 40, 8000);
        captureSized(view, widthPx, contentHeight, callback);
    }

    private void captureSized(WebView view, int widthPx, int heightPx, BitmapCallback callback) {
        try {
            view.measure(
                View.MeasureSpec.makeMeasureSpec(widthPx, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(heightPx, View.MeasureSpec.EXACTLY)
            );
            view.layout(0, 0, widthPx, heightPx);

            Bitmap bitmap = Bitmap.createBitmap(widthPx, heightPx, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            canvas.drawColor(Color.WHITE);
            view.draw(canvas);
            Log.e(TAG, "captureSized OK " + widthPx + "x" + heightPx);
            callback.onBitmap(bitmap);
        } catch (OutOfMemoryError e) {
            Log.e(TAG, "OOM bitmap", e);
            callback.onBitmap(null);
        } catch (Exception e) {
            Log.e(TAG, "captureSized", e);
            callback.onBitmap(null);
        }
    }

    interface BitmapCallback {
        void onBitmap(Bitmap bitmap);
    }
}
