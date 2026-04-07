package com.agribooks.terminal;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;

import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;

/**
 * Registers Capacitor plugins and configures the WebView for Smart Sync:
 * IndexedDB-friendly storage settings and offline-first HTTP cache behavior.
 */
public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(H10PPrinterPlugin.class);
        registerPlugin(DeviceIdentityPlugin.class);
        super.onCreate(savedInstanceState);
        runOnUiThread(this::applyWebViewSmartSyncBasics);
    }

    @Override
    public void onResume() {
        super.onResume();
        runOnUiThread(this::applyConnectivityWebSettingsAndNotifyJs);
    }

    /** DOM / DB storage and default cache — run after {@code super.onCreate()}. */
    private void applyWebViewSmartSyncBasics() {
        WebView webView = getWebViewOrNull();
        if (webView == null) {
            return;
        }
        WebSettings settings = webView.getSettings();
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
    }

    private void applyConnectivityWebSettingsAndNotifyJs() {
        WebView webView = getWebViewOrNull();
        if (webView == null) {
            return;
        }
        WebSettings settings = webView.getSettings();
        if (isNetworkOnline()) {
            settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        } else {
            settings.setCacheMode(WebSettings.LOAD_CACHE_ELSE_NETWORK);
        }

        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        boolean metered = cm != null && cm.isActiveNetworkMetered();
        webView.evaluateJavascript("window.__isMeteredConnection=" + metered + ";", null);
        webView.evaluateJavascript(
            "if(window.__triggerBackgroundSync)window.__triggerBackgroundSync();",
            null
        );
    }

    private WebView getWebViewOrNull() {
        Bridge bridge = getBridge();
        if (bridge == null) {
            return null;
        }
        return bridge.getWebView();
    }

    @SuppressWarnings("deprecation")
    private boolean isNetworkOnline() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) {
            return false;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Network network = cm.getActiveNetwork();
            if (network == null) {
                return false;
            }
            NetworkCapabilities caps = cm.getNetworkCapabilities(network);
            if (caps == null) {
                return false;
            }
            return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        }
        NetworkInfo ni = cm.getActiveNetworkInfo();
        return ni != null && ni.isConnected();
    }
}
