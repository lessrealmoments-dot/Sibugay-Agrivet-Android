# AgriBooks SMS Gateway — Android App Setup Guide

## What This App Does
- Runs silently on your admin phone
- Every 30 seconds, checks your AgriBooks server for pending SMS messages
- Automatically sends them using your Globe SIM (unlimited text plan)
- Reports back to the server that the message was sent
- Shows a simple dashboard with stats

---

## STEP 1: Create New Project in Android Studio

1. Open Android Studio Panda 2
2. Click **"New Project"**
3. Select **"Empty Views Activity"** (NOT Compose) → Click Next
4. Fill in:
   - **Name:** `AgriSMS Gateway`
   - **Package name:** `com.agribooks.smsgateway`
   - **Save location:** wherever you want
   - **Language:** `Kotlin`
   - **Minimum SDK:** `API 26 (Android 8.0)`
   - **Build configuration language:** `Kotlin DSL`
5. Click **Finish** and wait for the project to load

---

## STEP 2: Update build.gradle.kts (Module: app)

Open `app/build.gradle.kts` and REPLACE the entire `dependencies { }` block with:

```kotlin
dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")

    // HTTP client
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // JSON parsing
    implementation("org.json:json:20231013")
}
```

Then click **"Sync Now"** when the yellow bar appears at the top.

---

## STEP 3: Update AndroidManifest.xml

Open `app/src/main/AndroidManifest.xml` and REPLACE its entire content with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <!-- Permissions -->
    <uses-permission android:name="android.permission.SEND_SMS" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="AgriSMS Gateway"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.Material3.DayNight.NoActionBar"
        tools:targetApi="31">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:label="AgriSMS Gateway">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <service
            android:name=".SmsGatewayService"
            android:foregroundServiceType="specialUse"
            android:exported="false" />

    </application>
</manifest>
```

---

## STEP 4: Create the Layout File

Open `app/src/main/res/layout/activity_main.xml` and REPLACE with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="24dp"
    android:background="#F5F5F0">

    <!-- Header -->
    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="AgriSMS Gateway"
        android:textSize="24sp"
        android:textStyle="bold"
        android:textColor="#1A4D2E"
        android:layout_marginBottom="4dp" />

    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Sends SMS from your AgriBooks queue"
        android:textSize="13sp"
        android:textColor="#94a3b8"
        android:layout_marginBottom="24dp" />

    <!-- Server URL -->
    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Server URL"
        android:textSize="12sp"
        android:textColor="#64748b"
        android:layout_marginBottom="4dp" />

    <EditText
        android:id="@+id/serverUrlInput"
        android:layout_width="match_parent"
        android:layout_height="48dp"
        android:hint="https://your-app.preview.emergentagent.com"
        android:inputType="textUri"
        android:textSize="14sp"
        android:background="@android:color/white"
        android:padding="12dp"
        android:layout_marginBottom="12dp" />

    <!-- Auth Token -->
    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Auth Token (from login)"
        android:textSize="12sp"
        android:textColor="#64748b"
        android:layout_marginBottom="4dp" />

    <EditText
        android:id="@+id/authTokenInput"
        android:layout_width="match_parent"
        android:layout_height="48dp"
        android:hint="Paste your JWT token here"
        android:inputType="text"
        android:textSize="14sp"
        android:background="@android:color/white"
        android:padding="12dp"
        android:layout_marginBottom="8dp" />

    <Button
        android:id="@+id/loginBtn"
        android:layout_width="match_parent"
        android:layout_height="48dp"
        android:text="Login with Credentials"
        android:textSize="13sp"
        android:backgroundTint="#1A4D2E"
        android:layout_marginBottom="24dp" />

    <!-- Status Card -->
    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:background="@android:color/white"
        android:padding="16dp"
        android:layout_marginBottom="16dp">

        <TextView
            android:id="@+id/statusText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Status: Stopped"
            android:textSize="16sp"
            android:textStyle="bold"
            android:textColor="#334155"
            android:layout_marginBottom="8dp" />

        <TextView
            android:id="@+id/statsText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Sent: 0  |  Failed: 0  |  Pending: 0"
            android:textSize="13sp"
            android:textColor="#64748b"
            android:layout_marginBottom="8dp" />

        <TextView
            android:id="@+id/lastCheckText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Last check: never"
            android:textSize="11sp"
            android:textColor="#94a3b8" />
    </LinearLayout>

    <!-- Start/Stop Button -->
    <Button
        android:id="@+id/toggleBtn"
        android:layout_width="match_parent"
        android:layout_height="56dp"
        android:text="Start Gateway"
        android:textSize="16sp"
        android:backgroundTint="#1A4D2E" />

    <!-- Log -->
    <TextView
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Recent Activity"
        android:textSize="12sp"
        android:textColor="#64748b"
        android:layout_marginTop="16dp"
        android:layout_marginBottom="4dp" />

    <ScrollView
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1">

        <TextView
            android:id="@+id/logText"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:text=""
            android:textSize="11sp"
            android:textColor="#475569"
            android:fontFamily="monospace"
            android:background="@android:color/white"
            android:padding="12dp" />
    </ScrollView>

</LinearLayout>
```

---

## STEP 5: Create SmsGatewayService.kt

Right-click on your package folder (`com.agribooks.smsgateway`) → New → Kotlin Class/File → Name: `SmsGatewayService`

REPLACE its content with:

```kotlin
package com.agribooks.smsgateway

import android.app.*
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.telephony.SmsManager
import android.util.Log
import androidx.core.app.NotificationCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*

class SmsGatewayService : Service() {

    companion object {
        const val TAG = "SmsGateway"
        const val CHANNEL_ID = "sms_gateway_channel"
        const val NOTIFICATION_ID = 1
        const val POLL_INTERVAL_MS = 30_000L // 30 seconds

        var serverUrl = ""
        var authToken = ""
        var sentCount = 0
        var failedCount = 0
        var pendingCount = 0
        var lastCheck = ""
        var logLines = mutableListOf<String>()
        var onUpdate: (() -> Unit)? = null
    }

    private val handler = Handler(Looper.getMainLooper())
    private val client = OkHttpClient()
    private var running = false

    private val pollRunnable = object : Runnable {
        override fun run() {
            if (running) {
                pollAndSend()
                handler.postDelayed(this, POLL_INTERVAL_MS)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification("Gateway running...")
        startForeground(NOTIFICATION_ID, notification)
        running = true
        addLog("Gateway started")
        handler.post(pollRunnable)
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        handler.removeCallbacks(pollRunnable)
        addLog("Gateway stopped")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun pollAndSend() {
        if (serverUrl.isEmpty() || authToken.isEmpty()) return

        val url = "$serverUrl/api/sms/queue/pending?limit=10"
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $authToken")
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                addLog("Poll failed: ${e.message}")
                updateLastCheck()
            }

            override fun onResponse(call: Call, response: Response) {
                updateLastCheck()
                if (!response.isSuccessful) {
                    addLog("Poll error: ${response.code}")
                    response.close()
                    return
                }

                val body = response.body?.string() ?: "[]"
                response.close()

                try {
                    val messages = JSONArray(body)
                    pendingCount = messages.length()

                    if (messages.length() == 0) {
                        onUpdate?.invoke()
                        return
                    }

                    addLog("Found ${messages.length()} pending")

                    for (i in 0 until messages.length()) {
                        val msg = messages.getJSONObject(i)
                        val id = msg.getString("id")
                        val phone = msg.getString("phone")
                        val text = msg.getString("message")
                        val name = msg.optString("customer_name", "")

                        sendSms(id, phone, text, name)
                    }
                } catch (e: Exception) {
                    addLog("Parse error: ${e.message}")
                }
            }
        })
    }

    private fun sendSms(id: String, phone: String, message: String, customerName: String) {
        try {
            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }

            // Split long messages
            val parts = smsManager.divideMessage(message)
            if (parts.size > 1) {
                smsManager.sendMultipartTextMessage(phone, null, parts, null, null)
            } else {
                smsManager.sendTextMessage(phone, null, message, null, null)
            }

            // Report success
            markSent(id)
            sentCount++
            addLog("Sent to $customerName ($phone)")
            updateNotification("Last sent: $customerName")

        } catch (e: Exception) {
            markFailed(id, e.message ?: "Send failed")
            failedCount++
            addLog("FAILED $customerName: ${e.message}")
        }
    }

    private fun markSent(id: String) {
        val url = "$serverUrl/api/sms/queue/$id/mark-sent"
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $authToken")
            .patch("{}".toRequestBody("application/json".toMediaType()))
            .build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {}
            override fun onResponse(call: Call, response: Response) { response.close() }
        })
    }

    private fun markFailed(id: String, error: String) {
        val url = "$serverUrl/api/sms/queue/$id/mark-failed"
        val json = JSONObject().put("error", error).toString()
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $authToken")
            .patch(json.toRequestBody("application/json".toMediaType()))
            .build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {}
            override fun onResponse(call: Call, response: Response) { response.close() }
        })
    }

    private fun updateLastCheck() {
        lastCheck = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        onUpdate?.invoke()
    }

    private fun addLog(text: String) {
        val time = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        val line = "[$time] $text"
        Log.d(TAG, line)
        handler.post {
            logLines.add(0, line)
            if (logLines.size > 50) logLines.removeAt(logLines.size - 1)
            onUpdate?.invoke()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "SMS Gateway",
                NotificationManager.IMPORTANCE_LOW
            ).apply { description = "AgriBooks SMS sending service" }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pending = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("AgriSMS Gateway")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_email)
            .setContentIntent(pending)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(text))
    }
}
```

---

## STEP 6: Update MainActivity.kt

Open `app/src/main/java/com/agribooks/smsgateway/MainActivity.kt` and REPLACE with:

```kotlin
package com.agribooks.smsgateway

import android.Manifest
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var serverUrlInput: EditText
    private lateinit var authTokenInput: EditText
    private lateinit var toggleBtn: Button
    private lateinit var loginBtn: Button
    private lateinit var statusText: TextView
    private lateinit var statsText: TextView
    private lateinit var lastCheckText: TextView
    private lateinit var logText: TextView
    private var serviceRunning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences("agri_sms", MODE_PRIVATE)

        serverUrlInput = findViewById(R.id.serverUrlInput)
        authTokenInput = findViewById(R.id.authTokenInput)
        toggleBtn = findViewById(R.id.toggleBtn)
        loginBtn = findViewById(R.id.loginBtn)
        statusText = findViewById(R.id.statusText)
        statsText = findViewById(R.id.statsText)
        lastCheckText = findViewById(R.id.lastCheckText)
        logText = findViewById(R.id.logText)

        // Load saved values
        serverUrlInput.setText(prefs.getString("server_url", ""))
        authTokenInput.setText(prefs.getString("auth_token", ""))

        // Request SMS permission
        requestPermissions()

        // Login button — get token via email/password
        loginBtn.setOnClickListener { showLoginDialog() }

        // Start/Stop toggle
        toggleBtn.setOnClickListener {
            if (serviceRunning) stopGateway() else startGateway()
        }

        // Listen for service updates
        SmsGatewayService.onUpdate = { runOnUiThread { refreshUI() } }
    }

    private fun requestPermissions() {
        val perms = mutableListOf(Manifest.permission.SEND_SMS)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val needed = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), 100)
        }
    }

    private fun startGateway() {
        val url = serverUrlInput.text.toString().trim().trimEnd('/')
        val token = authTokenInput.text.toString().trim()

        if (url.isEmpty()) {
            Toast.makeText(this, "Enter server URL first", Toast.LENGTH_SHORT).show()
            return
        }
        if (token.isEmpty()) {
            Toast.makeText(this, "Login or paste auth token first", Toast.LENGTH_SHORT).show()
            return
        }

        // Check SMS permission
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "SMS permission required!", Toast.LENGTH_LONG).show()
            requestPermissions()
            return
        }

        // Save config
        prefs.edit()
            .putString("server_url", url)
            .putString("auth_token", token)
            .apply()

        SmsGatewayService.serverUrl = url
        SmsGatewayService.authToken = token

        val intent = Intent(this, SmsGatewayService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        serviceRunning = true
        toggleBtn.text = "Stop Gateway"
        toggleBtn.setBackgroundColor(0xFFDC2626.toInt())
        statusText.text = "Status: Running"
        statusText.setTextColor(0xFF16a34a.toInt())
    }

    private fun stopGateway() {
        stopService(Intent(this, SmsGatewayService::class.java))
        serviceRunning = false
        toggleBtn.text = "Start Gateway"
        toggleBtn.setBackgroundColor(0xFF1A4D2E.toInt())
        statusText.text = "Status: Stopped"
        statusText.setTextColor(0xFF334155.toInt())
    }

    private fun refreshUI() {
        statsText.text = "Sent: ${SmsGatewayService.sentCount}  |  " +
                "Failed: ${SmsGatewayService.failedCount}  |  " +
                "Pending: ${SmsGatewayService.pendingCount}"
        lastCheckText.text = "Last check: ${SmsGatewayService.lastCheck.ifEmpty { "never" }}"
        logText.text = SmsGatewayService.logLines.joinToString("\n")
    }

    private fun showLoginDialog() {
        val url = serverUrlInput.text.toString().trim().trimEnd('/')
        if (url.isEmpty()) {
            Toast.makeText(this, "Enter server URL first", Toast.LENGTH_SHORT).show()
            return
        }

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(48, 24, 48, 0)
        }
        val emailInput = EditText(this).apply {
            hint = "Email"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
        }
        val passInput = EditText(this).apply {
            hint = "Password"
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        layout.addView(emailInput)
        layout.addView(passInput)

        AlertDialog.Builder(this)
            .setTitle("Login to AgriBooks")
            .setView(layout)
            .setPositiveButton("Login") { _, _ ->
                login(url, emailInput.text.toString(), passInput.text.toString())
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun login(url: String, email: String, password: String) {
        val json = JSONObject()
            .put("email", email)
            .put("password", password)
            .toString()

        val request = Request.Builder()
            .url("$url/api/auth/login")
            .post(json.toRequestBody("application/json".toMediaType()))
            .build()

        OkHttpClient().newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Login failed: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string() ?: ""
                response.close()
                runOnUiThread {
                    if (response.isSuccessful) {
                        try {
                            val token = JSONObject(body).getString("token")
                            authTokenInput.setText(token)
                            prefs.edit().putString("auth_token", token).apply()
                            Toast.makeText(this@MainActivity, "Login successful!", Toast.LENGTH_SHORT).show()
                        } catch (e: Exception) {
                            Toast.makeText(this@MainActivity, "Login error: ${e.message}", Toast.LENGTH_LONG).show()
                        }
                    } else {
                        Toast.makeText(this@MainActivity, "Login failed: $body", Toast.LENGTH_LONG).show()
                    }
                }
            }
        })
    }
}
```

---

## STEP 7: Build & Install

1. Connect your admin phone via USB (enable **Developer Options** + **USB Debugging**)
   - Go to phone Settings → About Phone → tap "Build Number" 7 times
   - Go to Settings → Developer Options → enable USB Debugging
2. In Android Studio, select your phone from the device dropdown (top toolbar)
3. Click the green **Run** button (▶)
4. Wait for it to build and install (first build takes 2-3 minutes)

---

## STEP 8: First Time Setup on Phone

1. Open **AgriSMS Gateway** app on your phone
2. Grant **SMS permission** when prompted
3. Enter your server URL: `https://modal-optimize.preview.emergentagent.com`
4. Tap **"Login with Credentials"** → enter your admin email + password
5. Tap **"Start Gateway"**
6. Done! The app will now automatically send SMS from your queue every 30 seconds

---

## How It Works

```
AgriBooks (your website)
    ↓ creates pending SMS
AgriSMS Gateway (this app on your phone)
    ↓ polls every 30 seconds
    ↓ sends SMS via your Globe SIM
    ↓ reports back: sent or failed
AgriBooks updates the SMS queue status
```

---

## Troubleshooting

- **"SMS permission required"** → Go to phone Settings → Apps → AgriSMS Gateway → Permissions → SMS → Allow
- **Messages not sending** → Check the log at the bottom of the app
- **Token expired** → Tap "Login with Credentials" again
- **App killed in background** → Some phones kill background apps aggressively. Go to Settings → Battery → AgriSMS Gateway → "Don't optimize" or "Allow background activity"

---

## Notes
- The app uses a Foreground Service (persistent notification) to stay alive
- Globe unlimited text plan handles all sending costs
- The app saves your server URL and token — you only configure once
- Long messages (>160 chars) are automatically split into multiple SMS parts
