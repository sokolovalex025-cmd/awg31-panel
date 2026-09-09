package com.awgpanel.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private WebView webView;
    private SharedPreferences prefs;
    private static final String KEY_URL = "panel_url";
    private static final String DEFAULT_URL = "http://95.85.241.45:8080";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("awg_panel", MODE_PRIVATE);
        buildUi();
        loadPanel();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(3, 13, 28));

        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(10, 8, 10, 8);
        bar.setBackgroundColor(Color.rgb(3, 13, 28));

        TextView title = new TextView(this);
        title.setText("AWG Panel");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setTypeface(null, 1);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        bar.addView(title, titleLp);

        Button back = smallButton("‹");
        Button forward = smallButton("›");
        Button refresh = smallButton("↻");
        Button settings = smallButton("⚙");
        bar.addView(back);
        bar.addView(forward);
        bar.addView(refresh);
        bar.addView(settings);

        webView = new WebView(this);
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        ws.setSupportZoom(false);
        ws.setLoadWithOverviewMode(false);
        ws.setUseWideViewPort(false);
        ws.setUserAgentString(ws.getUserAgentString() + " AWGPanelAndroid/1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String u = request.getUrl().toString();
                return !(u.startsWith("http://") || u.startsWith("https://"));
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onCreateWindow(WebView view, boolean dialog, boolean userGesture, android.os.Message resultMsg) {
                final Dialog popup = new Dialog(MainActivity.this);
                popup.setTitle("AWG Panel");
                WebView child = new WebView(MainActivity.this);
                WebSettings s = child.getSettings();
                s.setJavaScriptEnabled(true);
                s.setDomStorageEnabled(true);
                child.setWebViewClient(new WebViewClient());
                child.setWebChromeClient(this);
                child.setBackgroundColor(Color.rgb(3, 13, 28));
                popup.setContentView(child);
                popup.getWindow();
                popup.setOnDismissListener(d -> child.destroy());
                popup.show();
                if (popup.getWindow() != null) {
                    popup.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
                }
                WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(child);
                resultMsg.sendToTarget();
                return true;
            }
        });

        back.setOnClickListener(v -> { if (webView.canGoBack()) webView.goBack(); });
        forward.setOnClickListener(v -> { if (webView.canGoForward()) webView.goForward(); });
        refresh.setOnClickListener(v -> webView.reload());
        settings.setOnClickListener(v -> showSettings());

        root.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 56));
        root.addView(webView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(root);
    }

    private Button smallButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(Color.WHITE);
        b.setTextSize(18);
        b.setMinWidth(46);
        b.setMinHeight(46);
        b.setPadding(0, 0, 0, 0);
        return b;
    }

    private String panelUrl() {
        return prefs.getString(KEY_URL, DEFAULT_URL);
    }

    private void loadPanel() {
        webView.loadUrl(panelUrl());
    }

    private void showSettings() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(panelUrl());
        input.setSelectAllOnFocus(true);
        input.setHint("http://IP:8080");
        new AlertDialog.Builder(this)
                .setTitle("Адрес AWG Panel")
                .setMessage("Укажите адрес web-панели VPS")
                .setView(input)
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Сохранить", (d, w) -> {
                    String url = input.getText().toString().trim();
                    if (!url.startsWith("http://") && !url.startsWith("https://")) url = "http://" + url;
                    prefs.edit().putString(KEY_URL, url).apply();
                    webView.loadUrl(url);
                }).show();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }
}
