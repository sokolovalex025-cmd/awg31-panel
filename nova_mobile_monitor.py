#!/usr/bin/env python3
"""NOVA Live Monitor: read-only live AWG connection monitor.

Stores only aggregate, non-secret connection telemetry in SQLite:
timestamp, online peer count, peer count, RX and TX totals.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from flask import jsonify, render_template_string

DB = Path("/opt/awg31-panel/panel.db")
MAX_ROWS = 720


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS nova_live_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        online INTEGER NOT NULL,
        peers INTEGER NOT NULL,
        rx INTEGER NOT NULL,
        tx INTEGER NOT NULL
    )""")
    c.commit()
    return c


def _diag():
    try:
        import nova12_diagnostics
        return nova12_diagnostics.diagnose()
    except Exception as exc:
        return {
            "ok": False, "online_peers": 0, "peer_count": 0,
            "peers": [], "port": "?", "mtu": "?",
            "error": str(exc), "timestamp": int(time.time())
        }


def _snapshot(data):
    rx = sum(int(p.get("rx") or 0) for p in data.get("peers", []))
    tx = sum(int(p.get("tx") or 0) for p in data.get("peers", []))
    c = _db()
    c.execute(
        "INSERT INTO nova_live_history(ts,online,peers,rx,tx) VALUES(?,?,?,?,?)",
        (int(time.time()), int(data.get("online_peers", 0)),
         int(data.get("peer_count", 0)), rx, tx),
    )
    c.execute(
        "DELETE FROM nova_live_history WHERE id NOT IN "
        "(SELECT id FROM nova_live_history ORDER BY id DESC LIMIT ?)",
        (MAX_ROWS,),
    )
    c.commit()
    c.close()


def _history(limit=120):
    c = _db()
    rows = c.execute(
        "SELECT ts,online,peers,rx,tx FROM nova_live_history "
        "ORDER BY id DESC LIMIT ?", (max(1, min(limit, MAX_ROWS)),)
    ).fetchall()
    c.close()
    return [
        {"ts": r[0], "online": r[1], "peers": r[2], "rx": r[3], "tx": r[4]}
        for r in reversed(rows)
    ]


PAGE = r'''
<div class="hero">
  <div><div class="eyebrow">NOVA LIVE MONITOR</div>
  <h1>Монитор подключений</h1>
  <p>Живой статус AWG и история агрегированного трафика без приватных ключей.</p></div>
  <button class="btn" id="lm-refresh">↻ Обновить</button>
</div>
<div class="grid4">
  <div class="card metric"><div class="label">AWG</div><div id="lm-awg" class="value">—</div><div id="lm-awg-sub" class="sub">проверка</div></div>
  <div class="card metric"><div class="label">Онлайн</div><div id="lm-online" class="value ok">—</div><div id="lm-peers" class="sub">peer(s)</div></div>
  <div class="card metric"><div class="label">UDP</div><div id="lm-udp" class="value blue">—</div><div id="lm-mtu" class="sub">MTU —</div></div>
  <div class="card metric"><div class="label">Последняя проверка</div><div id="lm-time" class="value" style="font-size:20px">—</div><div class="sub">автообновление 5 сек.</div></div>
</div>
<div class="card" style="margin-top:14px">
 <div class="toolbar"><h2>Клиенты</h2><span id="lm-state" class="badge warn">ПРОВЕРКА</span></div>
 <div class="table-wrap"><table><thead><tr><th>Endpoint</th><th>Статус</th><th>Последний handshake</th><th>RX</th><th>TX</th></tr></thead>
 <tbody id="lm-peers-table"><tr><td colspan="5" class="muted">Загрузка…</td></tr></tbody></table></div>
</div>
<div class="card" style="margin-top:14px">
 <div class="toolbar"><h2>История</h2><span class="muted">до 120 последних снимков</span></div>
 <div id="lm-history" class="code" style="max-height:280px">Загрузка…</div>
</div>
<script>
(function(){
 const $=id=>document.getElementById(id);
 const fmt=n=>{n=Number(n||0);const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++;}return n.toFixed(n>=10?0:1)+' '+u[i];};
 const ago=ts=>{if(!ts)return '—';const s=Math.max(0,Math.floor(Date.now()/1000-Number(ts)));return s<60?s+' сек. назад':s<3600?Math.floor(s/60)+' мин. назад':Math.floor(s/3600)+' ч. назад';};
 const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
 async function refresh(){
  try{
   const r=await fetch('/api/nova/live-monitor',{cache:'no-store'}); if(!r.ok)throw new Error('HTTP '+r.status);
   const d=await r.json();
   $('lm-awg').textContent=d.ok?'ONLINE':'CHECK'; $('lm-awg').className='value '+(d.ok?'ok':'bad');
   $('lm-awg-sub').textContent=d.ok?'AWG 3.1':'диагностика';
   $('lm-online').textContent=d.online_peers; $('lm-peers').textContent='из '+d.peer_count+' peer(s)';
   $('lm-udp').textContent=d.port; $('lm-mtu').textContent='MTU '+d.mtu;
   $('lm-time').textContent=new Date(d.timestamp*1000).toLocaleTimeString();
   $('lm-state').textContent=d.ok?'ONLINE':'CHECK'; $('lm-state').className='badge '+(d.ok?'on':'warn');
   const peers=d.peers||[];
   $('lm-peers-table').innerHTML=peers.length?peers.map(p=>'<tr><td>'+esc(p.endpoint)+'</td><td><span class="badge '+(p.online?'on':'off')+'">'+(p.online?'ONLINE':'OFFLINE')+'</span></td><td>'+ago(p.handshake)+'</td><td>'+fmt(p.rx)+'</td><td>'+fmt(p.tx)+'</td></tr>').join(''):'<tr><td colspan="5" class="muted">Peers не найдены.</td></tr>';
   const h=d.history||[];
   $('lm-history').textContent=h.length?h.map(x=>new Date(x.ts*1000).toLocaleTimeString()+'  online='+x.online+'/'+x.peers+'  RX='+fmt(x.rx)+'  TX='+fmt(x.tx)).join('\n'):'История появится после первой проверки.';
  }catch(e){$('lm-awg').textContent='ERROR';$('lm-awg').className='value bad';$('lm-state').textContent='ОШИБКА';$('lm-state').className='badge off';}
 }
 $('lm-refresh').addEventListener('click',refresh); refresh(); setInterval(refresh,5000);
})();
</script>
'''


def apply(nova11):
    app = nova11.core.app

    def page():
        return nova11.core.layout("Live Monitor", render_template_string(PAGE), "/live-monitor")

    def api():
        data = _diag()
        _snapshot(data)
        data["history"] = _history()
        return jsonify(data)

    app.add_url_rule("/live-monitor", "nova_live_monitor", page)
    app.add_url_rule("/api/nova/live-monitor", "nova_live_monitor_api", api)
    old_nav = nova11.core.nav

    if not getattr(nova11.core, "_nova_live_monitor_nav", False):
        def nav(path):
            html = old_nav(path)
            marker = '<div class="section">СИСТЕМА</div>'
            item = '<a class="%s" href="/live-monitor"><i>📡</i>Монитор подключений</a>' % (
                "active" if path == "/live-monitor" else ""
            )
            if marker in html and "/live-monitor" not in html:
                html = html.replace(marker, item + marker, 1)
            return html
        nova11.core.nav = nav
        for rule in list(app.url_map.iter_rules()):
            view = app.view_functions.get(rule.endpoint)
            if view is not None and getattr(view, "__module__", None) == "app":
                view.__globals__["nav"] = nav
        nova11.core._nova_live_monitor_nav = True
    return True
