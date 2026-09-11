package com.awgpanel.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String PREFS = "nova_network";
    private static final String KEY_URL = "panel_url";
    private static final String DEFAULT_URL = "http://95.85.241.45:8080";
    private WebView webView;
    private LinearLayout errorView;
    private TextView errorTitle, errorText, addressText;
    private ProgressBar progress;
    private SharedPreferences prefs;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        Window w = getWindow();
        w.setStatusBarColor(Color.rgb(3, 13, 28));
        w.setNavigationBarColor(Color.rgb(3, 13, 28));
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        buildUi();
        if (state != null) webView.restoreState(state); else loadPanel();
    }
    private int dp(float v) { return (int) (v * getResources().getDisplayMetrics().density + .5f); }
    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(Color.rgb(3, 13, 28));
        LinearLayout top = new LinearLayout(this); top.setGravity(Gravity.CENTER_VERTICAL); top.setPadding(dp(16), dp(6), dp(10), dp(4)); top.setBackgroundColor(Color.rgb(3, 13, 28));
        LinearLayout titleBox = new LinearLayout(this); titleBox.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("NOVA", Color.WHITE, 18, true); addressText = text(panelUrl(), Color.rgb(145, 165, 185), 11, false); addressText.setSingleLine(true); titleBox.addView(title); titleBox.addView(addressText);
        top.addView(titleBox, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button refresh = toolButton("↻"), settings = toolButton("⚙"); top.addView(refresh); top.addView(settings); refresh.setOnClickListener(v -> loadPanel()); settings.setOnClickListener(v -> showSettings());
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); progress.setMax(100); progress.setVisibility(View.GONE);
        root.addView(top, new LinearLayout.LayoutParams(-1, dp(62))); root.addView(progress, new LinearLayout.LayoutParams(-1, dp(2)));
        webView = new WebView(this); WebSettings ws = webView.getSettings(); ws.setJavaScriptEnabled(true); ws.setDomStorageEnabled(true); ws.setDatabaseEnabled(true); ws.setAllowFileAccess(false); ws.setAllowContentAccess(true); ws.setSupportZoom(false); ws.setBuiltInZoomControls(false); ws.setDisplayZoomControls(false); ws.setLoadWithOverviewMode(false); ws.setUseWideViewPort(false); ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW); ws.setCacheMode(WebSettings.LOAD_DEFAULT); ws.setTextZoom(100); ws.setUserAgentString("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36 NOVAMobile/1.0");
        CookieManager cm = CookieManager.getInstance(); cm.setAcceptCookie(true); cm.setAcceptThirdPartyCookies(webView, true); webView.setBackgroundColor(Color.rgb(3, 13, 28)); webView.setVerticalScrollBarEnabled(false); webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap favicon) { addressText.setText(url); progress.setProgress(10); progress.setVisibility(View.VISIBLE); showWebView(); }
            @Override public void onPageFinished(WebView v, String url) { addressText.setText(url); progress.setProgress(100); progress.postDelayed(() -> progress.setVisibility(View.GONE), 180); showWebView(); }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) { if (r.isForMainFrame()) showError("Не удалось открыть NOVA", "Проверьте интернет и адрес VPS.\n\n" + e.getDescription()); }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler h, SslError e) { h.cancel(); showError("Ошибка HTTPS", "Сертификат панели не прошёл проверку. Проверьте адрес и сертификат."); }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) { String u = r.getUrl().toString(); if (u.startsWith("http://") || u.startsWith("https://")) return false; try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u))); } catch (Exception ignored) {} return true; }
        });
        webView.setWebChromeClient(new WebChromeClient() { @Override public void onProgressChanged(WebView view, int newProgress) { progress.setProgress(newProgress); progress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE); } @Override public void onReceivedTitle(WebView view, String t) { if (t != null && !t.trim().isEmpty()) addressText.setText(t); } });
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> { try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { showError("Не удалось открыть файл", "На телефоне нет приложения для этого типа файла."); } });
        errorView = new LinearLayout(this); errorView.setOrientation(LinearLayout.VERTICAL); errorView.setGravity(Gravity.CENTER); errorView.setPadding(dp(28), dp(28), dp(28), dp(28)); errorView.setBackgroundColor(Color.rgb(3, 13, 28)); errorTitle = text("", Color.WHITE, 22, true); errorTitle.setGravity(Gravity.CENTER); errorText = text("", Color.LTGRAY, 15, false); errorText.setGravity(Gravity.CENTER); errorText.setPadding(0, dp(14), 0, dp(20)); Button retry = actionButton("Повторить"), change = actionButton("Изменить адрес"); errorView.addView(errorTitle); errorView.addView(errorText); errorView.addView(retry); errorView.addView(change); retry.setOnClickListener(v -> loadPanel()); change.setOnClickListener(v -> showSettings());
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1f)); root.addView(errorView, new LinearLayout.LayoutParams(-1, 0, 1f));
        LinearLayout bottom = new LinearLayout(this); bottom.setGravity(Gravity.CENTER); bottom.setPadding(dp(6), dp(4), dp(6), dp(5)); bottom.setBackgroundColor(Color.rgb(3, 13, 28)); Button back = toolButton("‹"), forward = toolButton("›"), home = toolButton("⌂"), reload = toolButton("↻"); bottom.addView(back, new LinearLayout.LayoutParams(0, dp(50), 1f)); bottom.addView(forward, new LinearLayout.LayoutParams(0, dp(50), 1f)); bottom.addView(home, new LinearLayout.LayoutParams(0, dp(50), 1f)); bottom.addView(reload, new LinearLayout.LayoutParams(0, dp(50), 1f)); back.setOnClickListener(v -> { if (webView.canGoBack()) webView.goBack(); }); forward.setOnClickListener(v -> { if (webView.canGoForward()) webView.goForward(); }); home.setOnClickListener(v -> loadPanel()); reload.setOnClickListener(v -> webView.reload()); root.addView(bottom, new LinearLayout.LayoutParams(-1, dp(58)));
        setContentView(root); errorView.setVisibility(View.GONE);
    }
    private TextView text(String value, int color, float size, boolean bold) { TextView t = new TextView(this); t.setText(value); t.setTextColor(color); t.setTextSize(size); if (bold) t.setTypeface(null, android.graphics.Typeface.BOLD); return t; }
    private Button toolButton(String value) { Button b = new Button(this); b.setText(value); b.setTextColor(Color.WHITE); b.setTextSize(20); b.setAllCaps(false); b.setMinWidth(0); b.setMinHeight(0); b.setPadding(dp(4), 0, dp(4), 0); return b; }
    private Button actionButton(String value) { Button b = new Button(this); b.setText(value); b.setAllCaps(false); b.setMinHeight(dp(48)); return b; }
    private String panelUrl() { return prefs.getString(KEY_URL, DEFAULT_URL); }
    private void loadPanel() { addressText.setText(panelUrl()); showWebView(); webView.loadUrl(panelUrl()); }
    private void showWebView() { webView.setVisibility(View.VISIBLE); errorView.setVisibility(View.GONE); }
    private void showError(String title, String message) { progress.setVisibility(View.GONE); errorTitle.setText(title); errorText.setText(message); webView.setVisibility(View.GONE); errorView.setVisibility(View.VISIBLE); }
    private void showSettings() { EditText input = new EditText(this); input.setSingleLine(true); input.setText(panelUrl()); input.setSelectAllOnFocus(true); input.setHint("http://IP:8080 или https://домен"); new AlertDialog.Builder(this).setTitle("Адрес NOVA").setMessage("Адрес web-панели VPS").setView(input).setNegativeButton("Отмена", null).setNeutralButton("Сбросить", (d, w) -> { prefs.edit().remove(KEY_URL).apply(); loadPanel(); }).setPositiveButton("Сохранить", (d, w) -> { String url = input.getText().toString().trim(); if (!url.startsWith("http://") && !url.startsWith("https://")) url = "http://" + url; prefs.edit().putString(KEY_URL, url).apply(); loadPanel(); }).show(); }
    @Override protected void onSaveInstanceState(Bundle out) { webView.saveState(out); super.onSaveInstanceState(out); }
    @Override public void onBackPressed() { if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed(); }
    @Override protected void onDestroy() { if (webView != null) { webView.stopLoading(); webView.destroy(); } super.onDestroy(); }
}
