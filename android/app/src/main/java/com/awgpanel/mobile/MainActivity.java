
package com.nova.antizapret;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
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
    private static final int PICK_OVPN = 1001;
    private final List<Server> servers = new ArrayList<>();
    private LinearLayout list;
    private TextView status, statusDetail;
    private int selected = -1;
    private final int bg = Color.rgb(9, 13, 20), card = Color.rgb(19, 25, 35);
    private final int text = Color.rgb(245, 247, 250), muted = Color.rgb(155, 165, 180);
    private final int accent = Color.rgb(70, 190, 120);
    private SharedPreferences prefs;

    static class Server {
        String name, host, country, profilePath;
        int port;
        Server(String n, String h, int p, String c, String profile) {
            name=n; host=h; port=p; country=c; profilePath=profile;
        }
    }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(bg);
        prefs=getSharedPreferences("nova_servers",MODE_PRIVATE);
        load(); buildUi(); render();
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
        statusDetail=tv("Добавьте сервер или импортируйте .ovpn",14,muted);
        statusDetail.setGravity(Gravity.CENTER); hero.addView(statusDetail);
        root.addView(hero,new LinearLayout.LayoutParams(-1,105));
        root.addView(new Space(this),new LinearLayout.LayoutParams(1,10));

        Button auto=new Button(this); auto.setText("⚡  АВТОВЫБОР ЛУЧШЕГО"); auto.setTextSize(15);
        auto.setTextColor(Color.WHITE); auto.setAllCaps(false); auto.setBackground(shape(accent,24));
        auto.setOnClickListener(v->autoSelectAndConnect()); root.addView(auto,new LinearLayout.LayoutParams(-1,56));

        LinearLayout titleRow=new LinearLayout(this); titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView st=tv("Серверы",20,text); st.setTypeface(null,android.graphics.Typeface.BOLD);
        titleRow.addView(st,lp(0,55,1));
        Button imp=new Button(this); imp.setText("＋ .ovpn"); imp.setTextColor(text); imp.setAllCaps(false);
        imp.setOnClickListener(v->pickOvpn()); titleRow.addView(imp,lp(-2,50,0));
        Button add=new Button(this); add.setText("＋ Добавить"); add.setTextColor(text); add.setAllCaps(false);
        add.setOnClickListener(v->addServerDialog()); titleRow.addView(add,lp(-2,50,0)); root.addView(titleRow);

        list=new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll=new ScrollView(this); scroll.setFillViewport(true); scroll.addView(list);
        root.addView(scroll,lp(-1,0,1));

        LinearLayout bottom=new LinearLayout(this); bottom.setGravity(Gravity.CENTER); bottom.setPadding(4,8,4,0);
        TextView home=tv("⌂\nГлавная",12,text); home.setGravity(Gravity.CENTER);
        TextView info=tv("ⓘ\nО приложении",12,muted); info.setGravity(Gravity.CENTER);
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
            TextView h=tv("Добавьте VPS или импортируйте OpenVPN .ovpn",14,muted);
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
            TextView addr=tv(s.host+":"+s.port+(s.profilePath!=null?"  •  OpenVPN":""),13,muted); names.addView(addr);
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
                    servers.add(new Server(name,host,port,country,null)); selected=servers.size()-1; save(); render();
                } catch(Exception ex) { Toast.makeText(this,"Проверьте адрес и порт",Toast.LENGTH_SHORT).show(); }
            }).setNegativeButton("Отмена",null).show();
    }

    private EditText e(String hint) {
        EditText x=new EditText(this); x.setHint(hint); x.setTextColor(text); x.setHintTextColor(muted); x.setSingleLine(true); return x;
    }

    private void pickOvpn() {
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("application/x-openvpn-profile"); startActivityForResult(i,PICK_OVPN);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=PICK_OVPN||resultCode!=RESULT_OK||data==null||data.getData()==null) return;
        Uri uri=data.getData();
        try {
            String host="openvpn"; int port=1194; String content;
            try(InputStream in=getContentResolver().openInputStream(uri)) {
                if(in==null) throw new Exception();
                byte[] buf=new byte[8192]; StringBuilder sb=new StringBuilder(); int n;
                while((n=in.read(buf))>0) sb.append(new String(buf,0,n,"UTF-8")); content=sb.toString();
            }
            for(String line:content.split("\\r?\\n")) {
                String t=line.trim();
                if(t.startsWith("remote ")) {
                    String[] a=t.split("\\s+"); if(a.length>=2) host=a[1];
                    if(a.length>=3) try{port=Integer.parseInt(a[2]);}catch(Exception ignored){}
                    break;
                }
            }
            File dir=new File(getFilesDir(),"profiles"); if(!dir.exists()&&!dir.mkdirs()) throw new Exception();
            File out=new File(dir,"server_"+System.currentTimeMillis()+".ovpn");
            try(FileOutputStream fos=new FileOutputStream(out)){fos.write(content.getBytes("UTF-8"));}
            servers.add(new Server("NOVA "+(servers.size()+1),host,port,"🌐",out.getAbsolutePath()));
            selected=servers.size()-1; save(); render();
            Toast.makeText(this,"OpenVPN профиль добавлен",Toast.LENGTH_SHORT).show();
        } catch(Exception ex) { Toast.makeText(this,"Не удалось импортировать .ovpn",Toast.LENGTH_LONG).show(); }
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
                else Toast.makeText(this,"Сервер выбран. Для VPN импортируйте .ovpn",Toast.LENGTH_LONG).show();
            });
        }).start();
    }

    private void select(int index){selected=index;save();render();Server s=servers.get(index);status.setText("● Выбран сервер");statusDetail.setText(s.country+"  "+s.name);}

    private void connect(int index) {
        if(index<0||index>=servers.size())return;Server s=servers.get(index);
        if(s.profilePath==null){Toast.makeText(this,"Для этого сервера нужен .ovpn профиль",Toast.LENGTH_LONG).show();return;}
        try {
            File f=new File(s.profilePath);
            Uri uri=FileProvider.getUriForFile(this,getPackageName()+".fileprovider",f);
            Intent intent=new Intent(Intent.ACTION_VIEW);intent.setDataAndType(uri,"application/x-openvpn-profile");
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(intent,"Открыть профиль в OpenVPN"));
            status.setText("● Передаю профиль OpenVPN");statusDetail.setText(s.name);
        }catch(Exception ex){Toast.makeText(this,"Установите OpenVPN-клиент для Android",Toast.LENGTH_LONG).show();}
    }

    private void save(){
        try{JSONArray a=new JSONArray();for(Server s:servers){JSONObject o=new JSONObject();
            o.put("name",s.name);o.put("host",s.host);o.put("port",s.port);o.put("country",s.country);
            o.put("profile",s.profilePath==null?"":s.profilePath);a.put(o);}
            prefs.edit().putString("servers",a.toString()).putInt("selected",selected).apply();
        }catch(Exception ignored){}
    }

    private void load(){
        servers.clear();try{
            JSONArray a=new JSONArray(prefs.getString("servers","[]"));
            for(int i=0;i<a.length();i++){JSONObject o=a.getJSONObject(i);String profile=o.optString("profile","");
                if(!profile.isEmpty()&&!new File(profile).exists())profile="";
                servers.add(new Server(o.optString("name","Server"),o.optString("host",""),o.optInt("port",1194),
                    o.optString("country","🌐"),profile.isEmpty()?null:profile));}
            selected=prefs.getInt("selected",-1);if(selected<0||selected>=servers.size())selected=-1;
        }catch(Exception ignored){selected=-1;}
    }
}
