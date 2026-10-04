
package com.nova.antizapret;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.*;
import androidx.core.content.FileProvider;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private static final int PICK_CONFIG = 1001;
    private final List<Server> servers = new ArrayList<>();
    private LinearLayout list;
    private TextView status, statusDetail;
    private int selected = -1;
    private final int bg = Color.rgb(9, 13, 20), card = Color.rgb(19, 25, 35);
    private final int text = Color.rgb(245, 247, 250), muted = Color.rgb(155, 165, 180);
    private final int accent = Color.rgb(70, 190, 120);
    private SharedPreferences prefs;

    static class Server {
        String name, host, country, profilePath, protocol;
        int port;
        Server(String n, String h, int p, String c, String profile, String proto) {
            name=n; host=h; port=p; country=c; profilePath=profile; protocol=proto;
        }
    }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(bg);
        prefs=getSharedPreferences("nova_servers",MODE_PRIVATE);
        load(); buildUi(); render();
        handleIncomingIntent(getIntent());
        checkForUpdates(false);
    }

    private TextView tv(String value,float size,int color) {
        TextView v=new TextView(this); v.setText(value); v.setTextSize(size); v.setTextColor(color); return v;
    }
    private GradientDrawable shape(int color,float radius) {
        GradientDrawable g=new GradientDrawable(); g.setColor(color); g.setCornerRadius(radius); return g;
    }
    private LinearLayout.LayoutParams lp(int w,int h,float weight) {
        return new LinearLayout.LayoutParams(w,h,weight);
    }

    private void buildUi() {
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(bg); root.setPadding(18,10,18,12);

        LinearLayout header=new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo=tv("NOVA",25,text); logo.setTypeface(null,android.graphics.Typeface.BOLD);
        header.addView(logo,lp(0,60,1)); TextView sub=tv("AntiZapret",14,muted);
        sub.setGravity(Gravity.CENTER_VERTICAL); header.addView(sub,lp(-2,60,0)); root.addView(header);

        LinearLayout hero=new LinearLayout(this); hero.setOrientation(LinearLayout.VERTICAL);
        hero.setGravity(Gravity.CENTER); hero.setPadding(18,18,18,18); hero.setBackground(shape(card,28));
        status=tv("● Не подключено",22,text); status.setGravity(Gravity.CENTER); hero.addView(status);
        statusDetail=tv("Импортируйте .conf AWG 3.1 или .ovpn",14,muted);
        statusDetail.setGravity(Gravity.CENTER); hero.addView(statusDetail);
        root.addView(hero,new LinearLayout.LayoutParams(-1,105));
        root.addView(new Space(this),new LinearLayout.LayoutParams(1,10));

        Button auto=new Button(this); auto.setText("⚡  АВТОВЫБОР ЛУЧШЕГО"); auto.setTextSize(15);
        auto.setTextColor(Color.WHITE); auto.setAllCaps(false); auto.setBackground(shape(accent,24));
        auto.setOnClickListener(v->autoSelectAndConnect()); root.addView(auto,new LinearLayout.LayoutParams(-1,56));

        LinearLayout titleRow=new LinearLayout(this); titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView st=tv("Серверы",20,text); st.setTypeface(null,android.graphics.Typeface.BOLD);
        titleRow.addView(st,lp(0,55,1));
        Button imp=new Button(this); imp.setText("＋ Импорт"); imp.setTextColor(text); imp.setAllCaps(false);
        imp.setOnClickListener(v->pickConfig()); titleRow.addView(imp,lp(-2,50,0));
        Button add=new Button(this); add.setText("＋ Добавить"); add.setTextColor(text); add.setAllCaps(false);
        add.setOnClickListener(v->addServerDialog()); titleRow.addView(add,lp(-2,50,0)); root.addView(titleRow);

        list=new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll=new ScrollView(this); scroll.setFillViewport(true); scroll.addView(list);
        root.addView(scroll,lp(-1,0,1));

        LinearLayout bottom=new LinearLayout(this); bottom.setGravity(Gravity.CENTER); bottom.setPadding(4,8,4,0);
        TextView home=tv("⌂\nГлавная",12,text); home.setGravity(Gravity.CENTER);
        TextView info=tv("ⓘ\nО приложении",12,muted); info.setGravity(Gravity.CENTER);
        info.setOnClickListener(v->showAbout());
        bottom.addView(home,lp(0,55,1)); bottom.addView(info,lp(0,55,1)); root.addView(bottom);
        setContentView(root);
    }

    private void render() {
        list.removeAllViews();
        if(servers.isEmpty()) {
            LinearLayout empty=new LinearLayout(this); empty.setOrientation(LinearLayout.VERTICAL);
            empty.setGravity(Gravity.CENTER); empty.setPadding(20,35,20,35);
            TextView icon=tv("＋",38,muted); icon.setGravity(Gravity.CENTER); empty.addView(icon);
            TextView t=tv("Нет серверов",18,text); t.setGravity(Gravity.CENTER); empty.addView(t);
            TextView h=tv("Один импорт — AWG 3.1 .conf или OpenVPN .ovpn",14,muted);
            h.setGravity(Gravity.CENTER); empty.addView(h); list.addView(empty); return;
        }
        for(int i=0;i<servers.size();i++) {
            final int index=i; Server s=servers.get(i);
            LinearLayout cardView=new LinearLayout(this); cardView.setOrientation(LinearLayout.VERTICAL);
            cardView.setPadding(16,13,12,13); cardView.setBackground(shape(card,22));
            LinearLayout top=new LinearLayout(this); top.setGravity(Gravity.CENTER_VERTICAL);
            TextView flag=tv(s.country,25,text); top.addView(flag,lp(45,48,0));
            LinearLayout names=new LinearLayout(this); names.setOrientation(LinearLayout.VERTICAL);
            TextView name=tv((index==selected?"✓ ":"")+s.name,17,text);
            name.setTypeface(null,android.graphics.Typeface.BOLD); names.addView(name);
            TextView addr=tv(s.host+":"+s.port+(s.profilePath!=null?"  •  "+protocolLabel(s.protocol):""),13,muted); names.addView(addr);
            top.addView(names,lp(0,48,1));
            Button choose=new Button(this); choose.setText("Выбрать"); choose.setTextSize(12); choose.setAllCaps(false);
            choose.setOnClickListener(v->select(index)); top.addView(choose,lp(90,48,0)); cardView.addView(top);

            LinearLayout actions=new LinearLayout(this); actions.setGravity(Gravity.CENTER_VERTICAL);
            TextView ping=tv("○ Не проверен",13,muted); actions.addView(ping,lp(0,45,1));
            Button check=new Button(this); check.setText("Проверить"); check.setTextSize(12); check.setAllCaps(false);
            check.setOnClickListener(v->ping(s,ping)); actions.addView(check,lp(105,45,0));
            if(s.profilePath!=null) {
                Button connect=new Button(this); connect.setText("Подключить"); connect.setTextSize(12); connect.setAllCaps(false);
                connect.setOnClickListener(v->connect(index)); actions.addView(connect,lp(110,45,0));
            }
            cardView.addView(actions); LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(-1,-2);
            cp.setMargins(0,0,0,10); list.addView(cardView,cp);
        }
    }

    private void addServerDialog() {
        LinearLayout box=new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setPadding(24,4,24,0);
        EditText n=e("Название, например 🇳🇱 Нидерланды"), h=e("IP или домен");
        EditText p=e("Порт OpenVPN (1194)"), c=e("Флаг, например 🇳🇱");
        box.addView(n); box.addView(h); box.addView(p); box.addView(c);
        new AlertDialog.Builder(this).setTitle("Новый сервер").setView(box)
            .setPositiveButton("Добавить",(d,w)->{
                try {
                    String host=h.getText().toString().trim(); if(host.isEmpty()) throw new Exception();
                    int port=Integer.parseInt(p.getText().toString().trim().isEmpty()?"1194":p.getText().toString().trim());
                    if(port<1||port>65535) throw new Exception();
                    String name=n.getText().toString().trim().isEmpty()?host:n.getText().toString().trim();
                    String country=c.getText().toString().trim().isEmpty()?"🌐":c.getText().toString().trim();
                    servers.add(new Server(name,host,port,country,null,"manual")); selected=servers.size()-1; save(); render();
                } catch(Exception ex) { Toast.makeText(this,"Проверьте адрес и порт",Toast.LENGTH_SHORT).show(); }
            }).setNegativeButton("Отмена",null).show();
    }

    private EditText e(String hint) {
        EditText x=new EditText(this); x.setHint(hint); x.setTextColor(text); x.setHintTextColor(muted); x.setSingleLine(true); return x;
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
    }

    private void handleIncomingIntent(Intent intent) {
        if(intent==null) return;
        String action=intent.getAction();
        if(Intent.ACTION_VIEW.equals(action) && intent.getData()!=null) {
            importConfig(intent.getData());
        } else if(Intent.ACTION_SEND.equals(action) && intent.getParcelableExtra(Intent.EXTRA_STREAM)!=null) {
            Uri uri=intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if(uri!=null) importConfig(uri);
        }
    }

    private void pickConfig() {
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/x-openvpn-profile","application/x-wireguard-profile","application/octet-stream","text/plain"});
        startActivityForResult(i,PICK_CONFIG);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=PICK_CONFIG||resultCode!=RESULT_OK||data==null) return;
        if(data.getClipData()!=null){
            for(int i=0;i<data.getClipData().getItemCount();i++) importConfig(data.getClipData().getItemAt(i).getUri());
        } else if(data.getData()!=null) importConfig(data.getData());
    }
    private void importConfig(Uri uri) {
        try {
            String name=fileName(uri);
            String content;
            try(InputStream in=getContentResolver().openInputStream(uri)) {
                if(in==null) throw new Exception();
                java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
                byte[] buf=new byte[8192]; int n;
                while((n=in.read(buf))>0) out.write(buf,0,n);
                content=out.toString("UTF-8");
            }
            String protocol=detectProtocol(name,content);
            if(protocol==null) throw new Exception("unknown config");
            String host=protocol.equals("awg")?parseAwgHost(content):parseOpenVpnHost(content);
            int port=protocol.equals("awg")?parseAwgPort(content):parseOpenVpnPort(content);
            if(host==null||host.trim().isEmpty()) host=protocol.equals("awg")?"amneziawg":"openvpn";

            File dir=new File(getFilesDir(),"profiles");
            if(!dir.exists()&&!dir.mkdirs()) throw new Exception();
            String ext=protocol.equals("awg")?".conf":".ovpn";
            File outFile=new File(dir,"server_"+System.currentTimeMillis()+ext);
            try(FileOutputStream fos=new FileOutputStream(outFile)){fos.write(content.getBytes("UTF-8"));}

            String base=name;
            int dot=base.lastIndexOf('.');
            if(dot>0) base=base.substring(0,dot);
            if(base.trim().isEmpty()) base="NOVA "+(servers.size()+1);
            servers.add(new Server(base,host,port,"🌐",outFile.getAbsolutePath(),protocol));
            selected=servers.size()-1; save(); render();
            Toast.makeText(this,protocol.equals("awg")?"AWG 3.1 профиль добавлен":"OpenVPN профиль добавлен",Toast.LENGTH_SHORT).show();
        } catch(Exception ex) {
            Toast.makeText(this,"Не удалось импортировать конфиг. Нужен .conf AWG 3.1 или .ovpn",Toast.LENGTH_LONG).show();
        }
    }

    private String fileName(Uri uri) {
        String n=null;
        try {
            android.database.Cursor cur=getContentResolver().query(uri,null,null,null,null);
            if(cur!=null){ try{ if(cur.moveToFirst()){
                int i=cur.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                if(i>=0)n=cur.getString(i);
            }}finally{cur.close();}}
        } catch(Exception ignored){}
        if(n==null||n.isEmpty()) n=String.valueOf(uri.getLastPathSegment());
        return n==null?"config":n;
    }

    private String detectProtocol(String fileName,String content) {
        String lower=(fileName==null?"":fileName).toLowerCase(java.util.Locale.US);
        String l=(content==null?"":content).toLowerCase(java.util.Locale.US);
        if(lower.endsWith(".conf") || (l.contains("[interface]") && l.contains("[peer]") &&
            (l.contains("privatekey") || l.contains("publickey") || l.contains("endpoint")))) return "awg";
        if(lower.endsWith(".ovpn") || l.contains("client") || l.contains("dev tun") ||
            l.contains("<ca>") || l.contains("remote ")) return "ovpn";
        return null;
    }

    private String parseOpenVpnHost(String content) {
        for(String line:content.split("\\r?\\n")) {
            String t=line.trim();
            if(t.startsWith("remote ")) {
                String[] a=t.split("\\s+");
                if(a.length>=2) return a[1];
            }
        }
        return null;
    }

    private int parseOpenVpnPort(String content) {
        for(String line:content.split("\\r?\\n")) {
            String t=line.trim();
            if(t.startsWith("remote ")) {
                String[] a=t.split("\\s+");
                if(a.length>=3) try{return Integer.parseInt(a[2]);}catch(Exception ignored){}
            }
        }
        return 1194;
    }

    private String parseAwgHost(String content) {
        for(String line:content.split("\\r?\\n")) {
            String t=line.trim();
            if(t.startsWith("Endpoint")) {
                int eq=t.indexOf('=');
                if(eq>=0){
                    String ep=t.substring(eq+1).trim();
                    if(ep.startsWith("[")){
                        int close=ep.indexOf(']');
                        if(close>1)return ep.substring(1,close);
                    }
                    int colon=ep.lastIndexOf(':');
                    return colon>0?ep.substring(0,colon):ep;
                }
            }
        }
        return null;
    }

    private int parseAwgPort(String content) {
        for(String line:content.split("\\r?\\n")) {
            String t=line.trim();
            if(t.startsWith("Endpoint")) {
                int eq=t.indexOf('=');
                if(eq>=0){
                    String ep=t.substring(eq+1).trim();
                    if(ep.startsWith("[")){
                        int close=ep.indexOf(']');
                        int colon=ep.indexOf(':',close);
                        if(colon>0) try{return Integer.parseInt(ep.substring(colon+1));}catch(Exception ignored){}
                    } else {
                        int colon=ep.lastIndexOf(':');
                        if(colon>0) try{return Integer.parseInt(ep.substring(colon+1));}catch(Exception ignored){}
                    }
                }
            }
        }
        return 51820;
    }

    private String protocolLabel(String protocol) {
        if("awg".equals(protocol)) return "AmneziaWG 3.1";
        if("ovpn".equals(protocol)) return "OpenVPN";
        return "Сервер";
    }

    private void ping(Server s,TextView result) {
        status.setText("● Проверяю"); statusDetail.setText(s.name); result.setText("⏳ Проверка…");
        new Thread(()->{
            long t=System.currentTimeMillis(); boolean ok=false;
            try(Socket x=new Socket()){x.connect(new InetSocketAddress(s.host,s.port),2500);ok=true;}catch(Exception ignored){}
            long ms=System.currentTimeMillis()-t; final boolean reachable=ok;
            runOnUiThread(()->{
                if(reachable){result.setText("● "+ms+" ms");result.setTextColor(accent);status.setText("● Сервер доступен");statusDetail.setText(s.name+"  •  "+ms+" ms");}
                else{result.setText("● Недоступен");result.setTextColor(Color.rgb(235,85,85));status.setText("● Сервер недоступен");statusDetail.setText(s.name);}
            });
        }).start();
    }

    private void autoSelectAndConnect() {
        if(servers.isEmpty()){status.setText("● Нет серверов");statusDetail.setText("Добавьте хотя бы один VPS");return;}
        status.setText("● Ищу лучший сервер…");statusDetail.setText("Проверяю доступность");
        new Thread(()->{
            int best=-1;long bm=Long.MAX_VALUE;
            for(int i=0;i<servers.size();i++){Server s=servers.get(i);long t=System.currentTimeMillis();
                try(Socket x=new Socket()){x.connect(new InetSocketAddress(s.host,s.port),1800);long ms=System.currentTimeMillis()-t;if(ms<bm){bm=ms;best=i;}}catch(Exception ignored){}
            }
            final int bi=best;final long m=bm;
            runOnUiThread(()->{
                if(bi<0){status.setText("● Нет доступных серверов");statusDetail.setText("Проверьте IP, порт и интернет");return;}
                selected=bi;save();render();status.setText("⚡ Лучший сервер");
                statusDetail.setText(servers.get(bi).country+"  "+servers.get(bi).name+"  •  "+m+" ms");
                if(servers.get(bi).profilePath!=null)connect(bi);
                else Toast.makeText(this,"Сервер выбран. Для VPN импортируйте профиль",Toast.LENGTH_LONG).show();
            });
        }).start();
    }

    private void select(int index){selected=index;save();render();Server s=servers.get(index);status.setText("● Выбран сервер");statusDetail.setText(s.country+"  "+s.name);}

    private void connect(int index) {
        if(index<0||index>=servers.size())return;
        Server s=servers.get(index);
        if(s.profilePath==null){Toast.makeText(this,"Для этого сервера нужен профиль",Toast.LENGTH_LONG).show();return;}
        try {
            File f=new File(s.profilePath);
            Uri uri=FileProvider.getUriForFile(this,getPackageName()+".fileprovider",f);
            Intent intent=new Intent(Intent.ACTION_VIEW);
            String mime="awg".equals(s.protocol) ? "application/x-wireguard-profile" : "application/x-openvpn-profile";
            intent.setDataAndType(uri,mime);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            String title="awg".equals(s.protocol)?"Открыть профиль в AmneziaWG":"Открыть профиль в OpenVPN";
            startActivity(Intent.createChooser(intent,title));
            status.setText("● Передаю профиль");
            statusDetail.setText(s.name+"  •  "+protocolLabel(s.protocol));
        }catch(Exception ex){
            Toast.makeText(this,"Не найден подходящий VPN-клиент. Установите AmneziaWG или OpenVPN.",Toast.LENGTH_LONG).show();
        }
    }

    private void showAbout() {
        new AlertDialog.Builder(this).setTitle("NOVA VPN")
            .setMessage("Версия " + BuildConfig.VERSION_NAME + "\n\nПроверить наличие новой версии?")
            .setPositiveButton("Проверить",(d,w)->checkForUpdates(true))
            .setNegativeButton("Закрыть",null).show();
    }

    private void checkForUpdates(boolean manual) {
        // Debug APKs are signed by the CI runner's debug key and cannot be safely
        // upgraded to the production release APK. Only release builds use the
        // permanent NOVA signing key and participate in in-app updates.
        if (BuildConfig.DEBUG) {
            if (manual) runOnUiThread(() -> Toast.makeText(this,
                "Это debug-версия. Обновления устанавливаются только из release APK.",
                Toast.LENGTH_LONG).show());
            return;
        }
        new Thread(() -> {
            try {
                java.net.HttpURLConnection con=(java.net.HttpURLConnection)new java.net.URL(
                    "https://api.github.com/repos/sokolovalex025-cmd/awg31-panel/releases/latest").openConnection();
                con.setConnectTimeout(5000); con.setReadTimeout(7000);
                con.setRequestProperty("Accept","application/vnd.github+json");
                con.setRequestProperty("User-Agent","NOVA-AntiZapret");
                if(con.getResponseCode()!=200) throw new Exception();
                java.io.InputStream in=con.getInputStream();
                java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
                byte[] buf=new byte[8192]; int n;
                while((n=in.read(buf))>0) out.write(buf,0,n);
                in.close(); con.disconnect();
                JSONObject release=new JSONObject(out.toString("UTF-8"));
                String tag=release.optString("tag_name","");
                String latest=tag.startsWith("v")?tag.substring(1):tag;
                String assetUrl="";
                JSONArray assets=release.optJSONArray("assets");
                if(assets!=null) for(int i=0;i<assets.length();i++){
                    JSONObject a=assets.getJSONObject(i);
                    if("NOVA-AntiZapret.apk".equals(a.optString("name"))){
                        assetUrl=a.optString("browser_download_url",""); break;
                    }
                }
                if(assetUrl.isEmpty()) assetUrl="https://github.com/sokolovalex025-cmd/awg31-panel/releases/latest/download/NOVA-AntiZapret.apk";
                final String version=latest, downloadUrl=assetUrl;
                if(isNewer(version,BuildConfig.VERSION_NAME))
                    runOnUiThread(()->showUpdateDialog(version,downloadUrl));
                else if(manual)
                    runOnUiThread(()->Toast.makeText(this,"У вас последняя версия "+BuildConfig.VERSION_NAME,Toast.LENGTH_SHORT).show());
            } catch(Exception ex) {
                if(manual) runOnUiThread(()->Toast.makeText(this,"Не удалось проверить обновления",Toast.LENGTH_SHORT).show());
            }
        }).start();
    }

    private boolean isNewer(String remote,String local) {
        try {
            String[] a=remote.split("\\."); String[] b=local.split("\\.");
            int n=Math.max(a.length,b.length);
            for(int i=0;i<n;i++){
                int x=i<a.length?Integer.parseInt(a[i].replaceAll("[^0-9].*","")):0;
                int y=i<b.length?Integer.parseInt(b[i].replaceAll("[^0-9].*","")):0;
                if(x!=y) return x>y;
            }
        } catch(Exception ignored) {}
        return false;
    }

    private void showUpdateDialog(String version,String downloadUrl) {
        new AlertDialog.Builder(this).setTitle("Доступно обновление")
            .setMessage("Новая версия: "+version+"\nТекущая: "+BuildConfig.VERSION_NAME)
            .setPositiveButton("Обновить",(d,w)->downloadAndInstall(downloadUrl))
            .setNegativeButton("Позже",null).show();
    }

    private void downloadAndInstall(String downloadUrl) {
        status.setText("● Скачиваю обновление…"); statusDetail.setText("NOVA AntiZapret");
        new Thread(() -> {
            try {
                File dir=new File(getCacheDir(),"updates");
                if(!dir.exists()&&!dir.mkdirs()) throw new Exception();
                File apk=new File(dir,"NOVA-AntiZapret.apk");
                java.net.HttpURLConnection con=(java.net.HttpURLConnection)new java.net.URL(downloadUrl).openConnection();
                con.setConnectTimeout(10000); con.setReadTimeout(30000);
                con.setRequestProperty("User-Agent","NOVA-AntiZapret");
                if(con.getResponseCode()!=200) throw new Exception();
                try(InputStream in=con.getInputStream(); FileOutputStream fos=new FileOutputStream(apk)){
                    byte[] buf=new byte[8192]; int n;
                    while((n=in.read(buf))>0) fos.write(buf,0,n);
                }
                con.disconnect(); runOnUiThread(()->installApk(apk));
            } catch(Exception ex) {
                runOnUiThread(()->{
                    status.setText("● Ошибка обновления"); statusDetail.setText("Не удалось скачать APK");
                    Toast.makeText(this,"Не удалось скачать обновление",Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private void installApk(File apk) {
        try {
            if(Build.VERSION.SDK_INT>=26 && !getPackageManager().canRequestPackageInstalls()){
                new AlertDialog.Builder(this).setTitle("Разрешение на установку")
                    .setMessage("Разрешите NOVA AntiZapret устанавливать обновления из APK.")
                    .setPositiveButton("Открыть настройки",(d,w)->{
                        Intent i=new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:"+getPackageName())); startActivity(i);
                    }).setNegativeButton("Отмена",null).show();
                return;
            }
            Uri uri=FileProvider.getUriForFile(this,getPackageName()+".fileprovider",apk);
            Intent i=new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(uri,"application/vnd.android.package-archive");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(i);
        } catch(Exception ex) {
            Toast.makeText(this,"Не удалось запустить установку APK",Toast.LENGTH_LONG).show();
        }
    }

    private void save(){
        try{JSONArray a=new JSONArray();for(Server s:servers){JSONObject o=new JSONObject();
            o.put("name",s.name);o.put("host",s.host);o.put("port",s.port);o.put("country",s.country);
            o.put("profile",s.profilePath==null?"":s.profilePath); o.put("protocol",s.protocol==null?"manual":s.protocol); a.put(o);}
            prefs.edit().putString("servers",a.toString()).putInt("selected",selected).apply();
        }catch(Exception ignored){}
    }

    private void load(){
        servers.clear();try{
            JSONArray a=new JSONArray(prefs.getString("servers","[]"));
            for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);String profile=o.optString("profile","");
                if(!profile.isEmpty()&&!new File(profile).exists())profile="";
                servers.add(new Server(o.optString("name","Server"),o.optString("host",""),o.optInt("port",1194),
                    o.optString("country","🌐"),profile.isEmpty()?null:profile,o.optString("protocol","ovpn")));}
            selected=prefs.getInt("selected",-1);if(selected<0||selected>=servers.size())selected=-1;
        }catch(Exception ignored){selected=-1;}
    }
}
