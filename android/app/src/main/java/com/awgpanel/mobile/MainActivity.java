package com.nova.antizapret;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import java.net.InetSocketAddress;
import java.net.Socket;

public class MainActivity extends Activity {
    private final java.util.List<Server> servers = new java.util.ArrayList<>();
    private LinearLayout list;
    private TextView status, statusDetail;
    private TextView selectedName;
    private int bg = Color.rgb(9, 13, 20);
    private int card = Color.rgb(19, 25, 35);
    private int text = Color.rgb(245, 247, 250);
    private int muted = Color.rgb(155, 165, 180);
    private int accent = Color.rgb(70, 190, 120);

    static class Server {
        String name, host, country;
        int port;
        Server(String n, String h, int p, String c) { name=n; host=h; port=p; country=c; }
    }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(bg);
        buildUi();
        render();
    }

    private TextView tv(String value, float size, int color) {
        TextView v = new TextView(this);
        v.setText(value); v.setTextSize(size); v.setTextColor(color);
        return v;
    }

    private GradientDrawable shape(int color, float radius) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color); g.setCornerRadius(radius);
        return g;
    }

    private LinearLayout.LayoutParams lp(int w, int h, float weight) {
        return new LinearLayout.LayoutParams(w, h, weight);
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg);
        root.setPadding(18, 10, 18, 12);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo = tv("NOVA", 25, text);
        logo.setTypeface(null, android.graphics.Typeface.BOLD);
        header.addView(logo, lp(0, 60, 1));
        TextView sub = tv("AntiZapret", 14, muted);
        sub.setGravity(Gravity.CENTER_VERTICAL);
        header.addView(sub, lp(-2, 60, 0));
        root.addView(header);

        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setGravity(Gravity.CENTER);
        hero.setPadding(18, 18, 18, 18);
        hero.setBackground(shape(card, 28));
        status = tv("● Не подключено", 22, text);
        status.setGravity(Gravity.CENTER);
        hero.addView(status);
        statusDetail = tv("Выберите сервер для проверки", 14, muted);
        statusDetail.setGravity(Gravity.CENTER);
        hero.addView(statusDetail);
        root.addView(hero, new LinearLayout.LayoutParams(-1, 105));

        Space sp = new Space(this);
        root.addView(sp, new LinearLayout.LayoutParams(1, 10));

        Button auto = new Button(this);
        auto.setText("⚡  АВТОВЫБОР ЛУЧШЕГО");
        auto.setTextSize(15); auto.setTextColor(Color.WHITE);
        auto.setAllCaps(false);
        auto.setBackground(shape(accent, 24));
        auto.setOnClickListener(v -> autoSelect());
        root.addView(auto, new LinearLayout.LayoutParams(-1, 56));

        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView st = tv("Серверы", 20, text);
        st.setTypeface(null, android.graphics.Typeface.BOLD);
        titleRow.addView(st, lp(0, 55, 1));
        Button add = new Button(this);
        add.setText("＋ Добавить");
        add.setTextColor(text); add.setAllCaps(false);
        add.setOnClickListener(v -> addServerDialog());
        titleRow.addView(add, lp(-2, 50, 0));
        root.addView(titleRow);

        list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(list);
        root.addView(scroll, lp(-1, 0, 1));

        LinearLayout bottom = new LinearLayout(this);
        bottom.setGravity(Gravity.CENTER);
        bottom.setPadding(4, 8, 4, 0);
        TextView home = tv("⌂\nГлавная", 12, text); home.setGravity(Gravity.CENTER);
        TextView info = tv("ⓘ\nО приложении", 12, muted); info.setGravity(Gravity.CENTER);
        bottom.addView(home, lp(0, 55, 1)); bottom.addView(info, lp(0, 55, 1));
        root.addView(bottom);

        setContentView(root);
    }

    private void render() {
        list.removeAllViews();
        if (servers.isEmpty()) {
            LinearLayout empty = new LinearLayout(this);
            empty.setOrientation(LinearLayout.VERTICAL);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(20, 35, 20, 35);
            TextView icon = tv("＋", 38, muted); icon.setGravity(Gravity.CENTER);
            empty.addView(icon);
            TextView t = tv("Нет серверов", 18, text); t.setGravity(Gravity.CENTER);
            empty.addView(t);
            TextView h = tv("Добавьте свои AntiZapret VPS", 14, muted); h.setGravity(Gravity.CENTER);
            empty.addView(h);
            list.addView(empty);
            return;
        }

        for (Server s : servers) {
            LinearLayout cardView = new LinearLayout(this);
            cardView.setOrientation(LinearLayout.VERTICAL);
            cardView.setPadding(16, 13, 12, 13);
            cardView.setBackground(shape(card, 22));

            LinearLayout top = new LinearLayout(this);
            top.setGravity(Gravity.CENTER_VERTICAL);
            TextView flag = tv(s.country, 25, text);
            top.addView(flag, lp(45, 48, 0));
            LinearLayout names = new LinearLayout(this);
            names.setOrientation(LinearLayout.VERTICAL);
            TextView name = tv(s.name, 17, text);
            name.setTypeface(null, android.graphics.Typeface.BOLD);
            names.addView(name);
            TextView addr = tv(s.host + ":" + s.port, 13, muted);
            names.addView(addr);
            top.addView(names, lp(0, 48, 1));
            Button choose = new Button(this);
            choose.setText("Выбрать");
            choose.setTextSize(12); choose.setAllCaps(false);
            choose.setOnClickListener(v -> select(s));
            top.addView(choose, lp(90, 48, 0));
            cardView.addView(top);

            LinearLayout actions = new LinearLayout(this);
            actions.setGravity(Gravity.CENTER_VERTICAL);
            TextView ping = tv("○ Не проверен", 13, muted);
            actions.addView(ping, lp(0, 45, 1));
            Button check = new Button(this);
            check.setText("Проверить");
            check.setTextSize(12); check.setAllCaps(false);
            check.setOnClickListener(v -> ping(s, ping));
            actions.addView(check, lp(105, 45, 0));
            cardView.addView(actions);

            LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
            cp.setMargins(0, 0, 0, 10);
            list.addView(cardView, cp);
        }
    }

    private void addServerDialog() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(24, 4, 24, 0);
        EditText n=e("Название, например 🇳🇱 Нидерланды");
        EditText h=e("IP или домен");
        EditText p=e("Порт OpenVPN (1194)");
        EditText c=e("Флаг, например 🇳🇱");
        box.addView(n); box.addView(h); box.addView(p); box.addView(c);
        new AlertDialog.Builder(this).setTitle("Новый сервер").setView(box)
            .setPositiveButton("Добавить", (d,w) -> {
                try {
                    int port = Integer.parseInt(p.getText().toString().trim().isEmpty() ? "1194" : p.getText().toString().trim());
                    String country = c.getText().toString().trim().isEmpty() ? "🌐" : c.getText().toString().trim();
                    servers.add(new Server(n.getText().toString().trim(), h.getText().toString().trim(), port, country));
                    render();
                } catch(Exception ex) {
                    Toast.makeText(this, "Проверьте порт", Toast.LENGTH_SHORT).show();
                }
            }).setNegativeButton("Отмена", null).show();
    }

    private EditText e(String hint) {
        EditText x = new EditText(this);
        x.setHint(hint); x.setTextColor(text); x.setHintTextColor(muted);
        x.setSingleLine(true);
        return x;
    }

    private void ping(Server s, TextView result) {
        status.setText("● Проверяю");
        statusDetail.setText(s.name);
        result.setText("⏳ Проверка…");
        new Thread(() -> {
            long t = System.currentTimeMillis(); boolean ok=false;
            try(Socket x=new Socket()) {
                x.connect(new InetSocketAddress(s.host,s.port),2500); ok=true;
            } catch(Exception ignored) {}
            long ms=System.currentTimeMillis()-t; final boolean reachable=ok;
            runOnUiThread(() -> {
                if(reachable) {
                    result.setText("● " + ms + " ms");
                    result.setTextColor(accent);
                    status.setText("● Сервер доступен");
                    statusDetail.setText(s.name + "  •  " + ms + " ms");
                } else {
                    result.setText("● Недоступен");
                    result.setTextColor(Color.rgb(235,85,85));
                    status.setText("● Сервер недоступен");
                    statusDetail.setText(s.name);
                }
            });
        }).start();
    }

    private void autoSelect() {
        if(servers.isEmpty()){ status.setText("● Нет серверов"); statusDetail.setText("Добавьте хотя бы один VPS"); return; }
        status.setText("● Ищу лучший сервер…"); statusDetail.setText("Проверяю доступность");
        new Thread(() -> {
            Server best=null; long bm=Long.MAX_VALUE;
            for(Server s:servers) {
                long t=System.currentTimeMillis();
                try(Socket x=new Socket()) {
                    x.connect(new InetSocketAddress(s.host,s.port),1800);
                    long ms=System.currentTimeMillis()-t;
                    if(ms<bm){bm=ms;best=s;}
                } catch(Exception ignored) {}
            }
            Server b=best; long m=bm;
            runOnUiThread(() -> {
                if(b==null){ status.setText("● Нет доступных серверов"); statusDetail.setText("Проверьте IP и порт"); }
                else { status.setText("⚡ Лучший сервер"); statusDetail.setText(b.country+"  "+b.name+"  •  "+m+" ms"); }
            });
        }).start();
    }

    private void select(Server s) {
        status.setText("● Выбран сервер");
        statusDetail.setText(s.country+"  "+s.name);
        Toast.makeText(this, "Выбран: "+s.name, Toast.LENGTH_SHORT).show();
    }
}