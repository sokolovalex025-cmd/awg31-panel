package com.nova.antizapret;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.*;
import java.net.InetSocketAddress;
import java.net.Socket;

public class MainActivity extends Activity {
    private final java.util.List<Server> servers = new java.util.ArrayList<>();
    private LinearLayout list; private TextView status;
    static class Server { String name,host,country; int port; Server(String n,String h,int p,String c){name=n;host=h;port=p;country=c;} }

    public void onCreate(Bundle b){
        super.onCreate(b);
        LinearLayout root=new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setPadding(24,24,24,16);
        TextView title=new TextView(this); title.setText("NOVA AntiZapret"); title.setTextSize(28); title.setTextColor(Color.WHITE); title.setGravity(Gravity.CENTER); title.setPadding(12,24,12,24); title.setBackgroundColor(Color.rgb(20,24,32)); root.addView(title);
        status=new TextView(this); status.setText("Не подключено"); status.setTextSize(18); status.setGravity(Gravity.CENTER); status.setPadding(8,22,8,16); root.addView(status);
        Button auto=new Button(this); auto.setText("⚡ Автовыбор лучшего сервера"); auto.setOnClickListener(v->autoSelect()); root.addView(auto);
        Button add=new Button(this); add.setText("＋ Добавить сервер"); add.setOnClickListener(v->addServerDialog()); root.addView(add);
        list=new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll=new ScrollView(this); scroll.addView(list); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root); render();
    }
    void render(){
        list.removeAllViews();
        if(servers.isEmpty()){ TextView t=new TextView(this); t.setText("Добавьте первый сервер"); t.setTextSize(16); t.setPadding(30,30,30,30); list.addView(t); }
        for(Server s:servers){
            LinearLayout row=new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setPadding(8,12,8,12);
            TextView t=new TextView(this); t.setText(s.country+"  "+s.name+"\n"+s.host+":"+s.port); t.setTextSize(16);
            row.addView(t,new LinearLayout.LayoutParams(0,-2,1));
            Button check=new Button(this); check.setText("Проверить"); check.setOnClickListener(v->ping(s)); row.addView(check);
            Button connect=new Button(this); connect.setText("Выбрать"); connect.setOnClickListener(v->select(s)); row.addView(connect);
            list.addView(row);
        }
    }
    void addServerDialog(){
        LinearLayout box=new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setPadding(24,8,24,4);
        EditText n=e("Название"),h=e("IP или домен"),p=e("Порт"),c=e("Страна/флаг");
        box.addView(n);box.addView(h);box.addView(p);box.addView(c);
        new AlertDialog.Builder(this).setTitle("Добавить сервер").setView(box)
          .setPositiveButton("Добавить",(d,w)->{servers.add(new Server(n.getText().toString(),h.getText().toString(),Integer.parseInt(p.getText().toString().isEmpty()?"1194":p.getText().toString()),c.getText().toString().isEmpty()?"🌐":c.getText().toString()));render();})
          .setNegativeButton("Отмена",null).show();
    }
    EditText e(String hint){EditText x=new EditText(this);x.setHint(hint);return x;}
    void ping(Server s){status.setText("Проверяю "+s.name+"…");new Thread(()->{long t=System.currentTimeMillis();boolean ok=false;try(Socket x=new Socket()){x.connect(new InetSocketAddress(s.host,s.port),2500);ok=true;}catch(Exception ignored){}long ms=System.currentTimeMillis()-t;runOnUiThread(()->status.setText(ok?"🟢 "+s.name+": "+ms+" ms":"🔴 "+s.name+": недоступен"));}).start();}
    void autoSelect(){if(servers.isEmpty()){status.setText("Сначала добавьте серверы");return;}status.setText("Ищу лучший сервер…");new Thread(()->{Server best=null;long bm=Long.MAX_VALUE;for(Server s:servers){long t=System.currentTimeMillis();try(Socket x=new Socket()){x.connect(new InetSocketAddress(s.host,s.port),1800);long ms=System.currentTimeMillis()-t;if(ms<bm){bm=ms;best=s;}}catch(Exception ignored){}}Server b=best;long m=bm;runOnUiThread(()->status.setText(b==null?"Нет доступных серверов":"⚡ Лучший: "+b.name+" — "+m+" ms"));}).start();}
    void select(Server s){status.setText("Выбран "+s.name+" — готов к подключению");Toast.makeText(this,"Выбран: "+s.name,Toast.LENGTH_SHORT).show();}
}