package com.agribooks.terminal;

import com.getcapacitor.BridgeActivity;

/**
 * MainActivity — registers the H10PPrinterPlugin with the Capacitor bridge.
 * The plugin handles all communication between JavaScript (PrintBridge.js)
 * and the H10P device's built-in thermal printer SDK.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(android.os.Bundle savedInstanceState) {
        // Register H10P printer plugin BEFORE super.onCreate()
        registerPlugin(H10PPrinterPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
