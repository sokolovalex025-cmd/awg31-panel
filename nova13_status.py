#!/usr/bin/env python3
"""NOVA 13 Status Center.

Read-only operational dashboard. It aggregates existing Doctor, AWG diagnostics
and client telemetry without changing configuration or restarting services.
"""
from __future__ import annotations

import time
from flask import jsonify, render_template_string

PAGE = r'''
<div class="hero">
  <div>
    <div class="eyebrow">NOVA 13 STATUS CENTER</div>
    <h1>Центр состояния</h1>
    <p>Единая проверка панели, AWG 3.1, сети, сервисов и клиентов.</p>
  </div>
  <button class="btn" id="refresh">↻ Проверить сейчас</button>
</div>
<div class="grid4">
  <div class="card metric"><div class="label">Общий статус</div><div id="health" class="value">—</div><div id="healthSub" class="sub">проверка</div></div>
  <div class="card metric"><div class="label">Health Score</div><div id="score" class="value blue">—</div><div class="sub">NOVA Doctor</div></div>
  <div class="card metric"><div class="label">Клиенты</div><div id="clients" class="value">—</div><div id="clientsSub" class="sub">онлайн</div></div>
  <div class="card metric"><div class="label">AWG</div><div id="awg" class="value">—</div><div id="awgSub" class="sub">service</div></div>
</div>
<div class="dashboard-grid" style="margin-top:14px">
  <section class="card">
    <div class="toolbar"><h2>Сервисы</h2><span id="checked" class="muted">—</span></div>
    <div id="services"></div>
  </section>
  <section class="card">
    <div class="toolbar"><h2>Сеть</h2><span id="networkBadge" class="badge warn">ПРОВЕРКА</span></div>
    <div id="network"></div>
  </section>
</div>
<div class="card" style="margin-top:14px">
  <div class="toolbar"><h2>Что проверить</h2><span class="muted">только чтение</span></div>
  <div id="results"></div>
</div>
<script>
(function(){
 const $=id=>document.getElementById(id);
 const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
 function row(name,ok,detail){return '<div class="notice '+(ok?'good':'badbox')+'"><b>'+(ok?'✓ ':'✕ ')+esc(name)+'</b><div class="muted" style="margin-top:4px">'+esc(detail)+'</div></div>';}
 async function refresh(){
  try{
   const r=await fetch('/api/nova13/status',{cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status);
   const d=await r.json(), doc=d.doctor||{}, diag=d.diagnostics||{};
   const healthy=!!doc.ok;
   $('health').textContent=healthy?'ONLINE':'CHECK'; $('health').className='value '+(healthy?'ok':'bad');
   $('healthSub').textContent=healthy?'все основные проверки':'требуется внимание';
   $('score').textContent=(doc.score??0)+'%';
   $('clients').textContent=(diag.online_peers??0); $('clientsSub').textContent='онлайн из '+(diag.peer_count??0);
   const awg=doc.results?.find(x=>x.name==='AWG service');
   $('awg').textContent=awg?.ok?'ONLINE':'CHECK'; $('awg').className='value '+(awg?.ok?'ok':'bad');
   $('awgSub').textContent=esc(awg?.detail||'service');
   $('checked').textContent=new Date((d.timestamp||Date.now()/1000)*1000).toLocaleTimeString();
   const services=doc.results?.filter(x=>['AWG service','Panel service','Nginx'].includes(x.name))||[];
   $('services').innerHTML=services.map(x=>row(x.name,x.ok,x.detail)).join('')||row('Сервисы',false,'Нет данных');
   const net=doc.results?.filter(x=>['IPv4 forwarding','WAN route','NAT','AWG forwarding','DNS'].includes(x.name))||[];
   $('network').innerHTML=net.map(x=>row(x.name,x.ok,x.detail)).join('')||row('Сеть',false,'Нет данных');
   $('networkBadge').textContent=net.every(x=>x.ok)?'OK':'ВНИМАНИЕ'; $('networkBadge').className='badge '+(net.every(x=>x.ok)?'on':'warn');
   $('results').innerHTML=(doc.results||[]).map(x=>row(x.name,x.ok,x.detail+(x.ok?'':' · '+(x.hint||'')))).join('');
  }catch(e){
   $('health').textContent='ERROR';$('health').className='value bad';$('healthSub').textContent=e.message;
  }
 }
 $('refresh').addEventListener('click',refresh); refresh(); setInterval(refresh,15000);
})();
</script>
'''

def _doctor():
    try:
        import nova_resilience
        return nova_resilience.doctor()
    except Exception as exc:
        return {"ok": False, "score": 0, "results": [{"name": "Doctor", "ok": False, "detail": str(exc)}]}

def _diagnostics():
    try:
        import nova12_diagnostics
        return nova12_diagnostics.diagnose()
    except Exception as exc:
        return {"ok": False, "online_peers": 0, "peer_count": 0, "error": str(exc)}

def apply(nova11):
    app = nova11.core.app

    def page():
        return nova11.core.layout("NOVA 13 Status Center", render_template_string(PAGE), "/nova13-status")

    def api():
        return jsonify({
            "timestamp": int(time.time()),
            "doctor": _doctor(),
            "diagnostics": _diagnostics(),
        })

    app.add_url_rule("/nova13-status", "nova13_status_page", page)
    app.add_url_rule("/api/nova13/status", "nova13_status_api", api)
    return True
