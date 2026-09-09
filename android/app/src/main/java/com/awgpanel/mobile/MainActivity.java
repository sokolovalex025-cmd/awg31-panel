package com.awgpanel.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.http.SslError;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
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
import android.widget.TextView;

public class MainActivity extends Activity {
    private WebView webView;
    private TextView errorTitle, errorText;
    private LinearLayout errorView;
    private SharedPreferences prefs;
    private static final String KEY_URL = "panel_url";
    private static final String DEFAULT_URL = "http://95.85.241.45:8080";

    @Override protected void onCreate(Bundle state) {
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
        bar.setPadding(6, 4, 6, 4);
        bar.setBackgroundColor(Color.rgb(3, 13, 28));
        TextView title = new TextView(this);
        title.setText("AWG Panel"); title.setTextColor(Color.WHITE); title.setTextSize(18); title.setTypeface(null, 1);
        bar.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button back=smallButton("‹"), forward=smallButton("›"), refresh=smallButton("↻"), settings=smallButton("⚙");
        bar.addView(back); bar.addView(forward); bar.addView(refresh); bar.addView(settings);

        webView = new WebView(this);
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(true);
        ws.setSupportZoom(false);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);
        ws.setUserAgentString("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36 AWGPanelAndroid/2.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap f) { showWebView(); }
            @Override public void onPageFinished(WebView v, String url) { showWebView(); }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) showError("Не удалось открыть панель", "Адрес: " + panelUrl() + "\nКод ошибки: " + e.getErrorCode() + "\n" + e.getDescription());
            }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler h, SslError e) {
                h.cancel();
                showError("Ошибка HTTPS", "Проверьте сертификат панели или используйте HTTP-адрес.");
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                String u=r.getUrl().toString();
                return !(u.startsWith("http://") || u.startsWith("https://"));
            }
        });
        webView.setWebChromeClient(new WebChromeClient());

        errorView = new LinearLayout(this); errorView.setOrientation(LinearLayout.VERTICAL); errorView.setGravity(Gravity.CENTER); errorView.setPadding(30,30,30,30); errorView.setBackgroundColor(Color.rgb(3,13,28));
        errorTitle=new TextView(this); errorTitle.setTextColor(Color.WHITE); errorTitle.setTextSize(22); errorTitle.setGravity(Gravity.CENTER);
        errorText=new TextView(this); errorText.setTextColor(Color.LTGRAY); errorText.setTextSize(15); errorText.setGravity(Gravity.CENTER); errorText.setPadding(0,16,0,24);
        Button retry=new Button(this); retry.setText("Повторить"); retry.setOnClickListener(v->loadPanel());
        Button change=new Button(this); change.setText("Изменить адрес"); change.setOnClickListener(v->showSettings());
        errorView.addView(errorTitle); errorView.addView(errorText); errorView.addView(retry); errorView.addView(change);

        back.setOnClickListener(v->{if(webView.canGoBack())webView.goBack();});
        forward.setOnClickListener(v->{if(webView.canGoForward())webView.goForward();});
        refresh.setOnClickListener(v->loadPanel()); settings.setOnClickListener(v->showSettings());
        root.addView(bar,new LinearLayout.LayoutParams(-1,56));
        root.addView(webView,new LinearLayout.LayoutParams(-1,0,1f));
        root.addView(errorView,new LinearLayout.LayoutParams(-1,0,1f));
        setContentView(root); errorView.setVisibility(View.GONE);
    }

    private Button smallButton(String text){Button b=new Button(this);b.setText(text);b.setTextColor(Color.WHITE);b.setTextSize(18);b.setMinWidth(44);b.setMinHeight(44);return b;}
    private String panelUrl(){return prefs.getString(KEY_URL,DEFAULT_URL);}
    private void loadPanel(){showWebView();webView.loadUrl(panelUrl());}
    private void showWebView(){webView.setVisibility(View.VISIBLE);errorView.setVisibility(View.GONE);}
    private void showError(String t,String m){errorTitle.setText(t);errorText.setText(m);webView.setVisibility(View.GONE);errorView.setVisibility(View.VISIBLE);}
    private void showSettings(){
        EditText input=new EditText(this); input.setSingleLine(true); input.setText(panelUrl()); input.setSelectAllOnFocus(true);
        new AlertDialog.Builder(this).setTitle("Адрес AWG Panel").setMessage("Укажите адрес web-панели VPS").setView(input).setNegativeButton("Отмена",null).setPositiveButton("Сохранить",(d,w)->{
            String url=input.getText().toString().trim(); if(!url.startsWith("http://")&&!url.startsWith("https://"))url="http://"+url; prefs.edit().putString(KEY_URL,url).apply(); loadPanel();
        }).show();
    }
    @Override public void onBackPressed(){if(webView!=null&&webView.canGoBack())webView.goBack();else super.onBackPressed();}
}
