package com.argus.attendance;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class MainActivity extends BridgeActivity {
    private static final int PERMISSION_REQUEST_CODE = 1001;
    private TextToSpeech nativeTts;
    private volatile boolean ttsReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestRequiredRuntimePermissions();
        initNativeTts();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
    }

    private void initNativeTts() {
        nativeTts = new TextToSpeech(this, status -> {
            ttsReady = (status == TextToSpeech.SUCCESS);
        });
        if (this.bridge != null && this.bridge.getWebView() != null) {
            WebView wv = this.bridge.getWebView();
            wv.addJavascriptInterface(new NativeTtsBridge(), "ArgusNativeTTS");
        }
    }

    private Locale resolveLocale(String lang) {
        if (lang != null && lang.toLowerCase(Locale.ROOT).startsWith("ta")) {
            return new Locale("ta", "IN");
        }
        Locale enIn = new Locale("en", "IN");
        if (nativeTts != null && nativeTts.isLanguageAvailable(enIn) >= TextToSpeech.LANG_AVAILABLE) {
            return enIn;
        }
        return Locale.US;
    }

    public class NativeTtsBridge {
        @JavascriptInterface
        public boolean isAvailable() {
            return ttsReady && nativeTts != null;
        }

        @JavascriptInterface
        public boolean isLanguageAvailable(String lang) {
            if (!ttsReady || nativeTts == null) return false;
            Locale loc = resolveLocale(lang);
            int res = nativeTts.isLanguageAvailable(loc);
            return res >= TextToSpeech.LANG_AVAILABLE;
        }

        @JavascriptInterface
        public boolean speak(String text, String lang, float rate) {
            if (!ttsReady || nativeTts == null || text == null || text.trim().isEmpty()) {
                return false;
            }
            Locale loc = resolveLocale(lang);
            int avail = nativeTts.isLanguageAvailable(loc);
            if (avail < TextToSpeech.LANG_AVAILABLE) {
                return false;
            }
            nativeTts.setLanguage(loc);
            nativeTts.setSpeechRate(Math.max(0.5f, Math.min(2.0f, rate > 0 ? rate : 1.0f)));
            int rc = nativeTts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "argus_tts_" + System.currentTimeMillis());
            return rc == TextToSpeech.SUCCESS;
        }

        @JavascriptInterface
        public void stop() {
            if (nativeTts != null) {
                nativeTts.stop();
            }
        }
    }

    private void requestRequiredRuntimePermissions() {
        String[] perms = new String[] {
            Manifest.permission.CAMERA,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        };
        List<String> missing = new ArrayList<>();
        for (String p : perms) {
            if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) {
                missing.add(p);
            }
        }
        if (!missing.isEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toArray(new String[0]), PERMISSION_REQUEST_CODE);
        }
    }

    @Override
    public void onDestroy() {
        if (nativeTts != null) {
            nativeTts.stop();
            nativeTts.shutdown();
            nativeTts = null;
            ttsReady = false;
        }
        super.onDestroy();
    }
}
