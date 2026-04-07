package com.agribooks.terminal;

import android.provider.Settings;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Exposes {@link Settings.Secure#ANDROID_ID} for binding AgriSmart Terminal sessions
 * to the physical device. No extra permissions required.
 */
@CapacitorPlugin(name = "DeviceIdentity")
public class DeviceIdentityPlugin extends Plugin {

    @PluginMethod
    public void getDeviceId(PluginCall call) {
        String androidId = Settings.Secure.getString(
            getContext().getContentResolver(),
            Settings.Secure.ANDROID_ID
        );
        JSObject result = new JSObject();
        result.put("deviceId", androidId != null ? androidId : "unknown");
        call.resolve(result);
    }
}
