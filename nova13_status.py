#!/usr/bin/env python3
"""NOVA 13 Status Center.

Read-only operational dashboard. It aggregates existing Doctor, AWG diagnostics
and client telemetry without changing configuration or restarting services.
"""
from __future__ import annotations

import time
from flask import jsonify, render_template_string

PAGE = r'''
<style>
.n13{--n13-bg:#07101b;--n13-card:rgba(13,22,34,.86);--n13-line:rgba(255,255,255,.08);--n13-muted:#8190a5;--n13-text:#edf4ff;--n13-blue:#7b8cff;--n13-green:#43d9c0;--n13-red:#ff7186;max-width:1380px;margin:0 auto}
.n13 *{box-sizing:border-box}.n13-hero{position:relative;overflow:hidden;padding:26px;border:1px solid var(--n13-line);border-radius:24px;background:radial-gradient(circle at 85% 15%,rgba(123,140,255,.18),transparent 32%),linear-gradient(135deg,rgba(18,29,45,.96),rgba(7,14,23,.98));box-shadow:0 24px 70px rgba(0,0,0,.25);display:flex;justify-content:space-between;gap:24px;align-items:center}
.n13-hero:after{content:"";position:absolute;width:180px;height:180px;border:1px solid rgba(67,217,192,.16);border-radius:50%;right:-70px;bottom:-100px}
.n13-eyebrow{font-size:10px;letter-spacing:.2em;color:var(--n13-blue);font-weight:800}.n13 h1{margin:7px 0 6px;font-size:30px;letter-spacing:-.04em;color:var(--n13-text)}.n13-lead{margin:0;color:var(--n13-muted);font-size:13px}
.n13-actions{display:flex;align-items:center;gap:9px;position:relative;z-index:1}.n13-refresh{white-space:nowrap}.n13-live{display:flex;align-items:center;gap:7px;color:#9cabbc;font-size:11px}.n13-dot{width:8px;height:8px;border-radius:50%;background:var(--n13-green);box-shadow:0 0 12px rgba(67,217,192,.65)}
.n13-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px}.n13-card{border:1px solid var(--n13-line);border-radius:18px;background:var(--n13-card);box-shadow:0 14px 45px rgba(0,0,0,.16);backdrop-filter:blur(12px)}
.n13-metric{padding:18px;position:relative;overflow:hidden}.n13-metric:before{content:"";position:absolute;inset:auto -20px -45px auto;width:110px;height:110px;border-radius:50%;background:rgba(123,140,255,.07)}.n13-label{font-size:10px;color:#718095;text-transform:uppercase;letter-spacing:.12em}.n13-value{font-size:27px;font-weight:800;letter-spacing:-.04em;margin-top:9px;color:var(--n13-text)}.n13-value.ok{color:var(--n13-green)}.n13-value.bad{color:var(--n13-red)}.n13-value.blue{color:var(--n13-blue)}.n13-sub{font-size:10px;color:var(--n13-muted);margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.n13-main{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.n13-panel{padding:18px}.n13-panel-wide{margin-top:12px}.n13-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:13px}.n13-toolbar h2{font-size:14px;margin:0;color:var(--n13-text)}.n13-muted{font-size:10px;color:var(--n13-muted)}
.n13-list{display:grid;gap:7px}.n13-row{display:grid;grid-template-columns:30px minmax(90px,170px) 1fr;gap:10px;align-items:center;padding:11px 12px;border:1px solid rgba(255,255,255,.055);border-radius:12px;background:rgba(255,255,255,.018)}.n13-icon{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;font-size:12px;background:rgba(67,217,192,.1);color:var(--n13-green)}.n13-row.bad .n13-icon{background:rgba(255,113,134,.1);color:var(--n13-red)}.n13-name{font-size:11px;font-weight:700;color:#dce6f4}.n13-detail{font-size:10px;color:var(--n13-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.n13-badge{display:inline-flex;align-items:center;gap:5px;padding:5px 8px;border-radius:999px;font-size:9px;font-weight:800;letter-spacing:.08em}.n13-badge.ok{background:rgba(67,217,192,.1);color:var(--n13-green)}.n13-badge.warn{background:rgba(255,181,71,.1);color:#ffb547}
.n13-score{height:6px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;margin-top:9px}.n13-score span{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--n13-blue),var(--n13-green));border-radius:99px;transition:width .5s ease}
.n13-empty{padding:20px;text-align:center;color:var(--n13-muted);font-size:11px}.n13-footer{display:flex;justify-content:space-between;gap:10px;margin-top:10px;color:#617086;font-size:9px}
@media(max-width:900px){.n13-metrics{grid-template-columns:repeat(2,1fr)}.n13-main{grid-template-columns:1fr}.n13-hero{align-items:flex-start;flex-direction:column}.n13-actions{width:100%;justify-content:space-between}}
@media(max-width:560px){.n13{margin:0 -2px}.n13-hero{padding:20px;border-radius:18px}.n13 h1{font-size:24px}.n13-metrics{gap:8px}.n13-metric{padding:14px}.n13-value{font-size:22px}.n13-row{grid-template-columns:26px 1fr}.n13-detail{grid-column:2}.n13-actions{flex-wrap:wrap}}
</style>
<div class="n13">
  <section class="n13-hero">
    <div>
      <div class="n13-eyebrow">NOVA 13 · STATUS CENTER</div>
      <h1>Центр состояния</h1>
      <p class="n13-lead">Панель · AWG 3.1 · сеть · сервисы · клиенты — в одном экране.</p>
    </div>
    <div class="n13-actions">
      <span class="n13-live"><i class="n13-dot"></i><span id="n13Live">LIVE · 15 сек</span></span>
      <button class="btn n13-refresh" id="n13Refresh">↻ Проверить сейчас</button>
    </div>
  </section>

  <section class="n13-metrics">
    <div class="n13-card n13-metric"><div class="n13-label">Общий статус</div><div id="n13Health" class="n13-value">—</div><div id="n13HealthSub" class="n13-sub">Проверка…</div></div>
    <div class="n13-card n13-metric"><div class="n13-label">Health Score</div><div id="n13Score" class="n13-value blue">—</div><div class="n13-score"><span id="n13ScoreBar"></span></div><div class="n13-sub">NOVA Doctor</div></div>
    <div class="n13-card n13-metric"><div class="n13-label">Клиенты</div><div id="n13Clients" class="n13-value">—</div><div id="n13ClientsSub" class="n13-sub">онлайн</div></div>
    <div class="n13-card n13-metric"><div class="n13-label">AWG 3.1</div><div id="n13Awg" class="n13-value">—</div><div id="n13AwgSub" class="n13-sub">service</div></div>
  </section>

  <section class="n13-main">
    <div class="n13-card n13-panel"><div class="n13-toolbar"><h2>Сервисы</h2><span id="n13Checked" class="n13-muted">—</span></div><div id="n13Services" class="n13-list"></div></div>
    <div class="n13-card n13-panel"><div class="n13-toolbar"><h2>Сеть</h2><span id="n13NetworkBadge" class="n13-badge warn">ПРОВЕРКА</span></div><div id="n13Network" class="n13-list"></div></div>
  </section>

  <section class="n13-card n13-panel n13-panel-wide">
    <div class="n13-toolbar"><h2>Диагностика</h2><span class="n13-muted">только чтение</span></div>
    <div id="n13Results" class="n13-list"></div>
    <div class="n13-footer"><span>Автообновление включено</span><span id="n13Updated">—</span></div>
  </section>
</div>

<script>
(function(){
'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function row(x){
  const ok=!!x.ok;
  return '<div class="n13-row '+(ok?'':'bad')+'"><span class="n13-icon">'+(ok?'✓':'!')+'</span><span class="n13-name">'+esc(x.name)+'</span><span class="n13-detail">'+esc(x.detail||'Нет данных')+(ok?'':' · '+esc(x.hint||''))+'</span></div>';
}
function setValue(id,text,state){const e=$(id);e.textContent=text;e.className='n13-value '+(state||'');}
async function refresh(){
  $('n13Live').textContent='ОБНОВЛЕНИЕ…';
  try{
    const r=await fetch('/api/nova13/status',{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d=await r.json(),doc=d.doctor||{},diag=d.diagnostics||{},results=doc.results||[];
    const healthy=!!doc.ok, score=Math.max(0,Math.min(100,Number(doc.score||0)));
    setValue('n13Health',healthy?'ONLINE':'CHECK',healthy?'ok':'bad');
    $('n13HealthSub').textContent=healthy?'Основные проверки пройдены':'Требуется внимание';
    setValue('n13Score',score+'%','blue');$('n13ScoreBar').style.width=score+'%';
    setValue('n13Clients',diag.online_peers??0);$('n13ClientsSub').textContent='онлайн из '+(diag.peer_count??0);
    const awg=results.find(x=>x.name==='AWG service');
    setValue('n13Awg',awg?.ok?'ONLINE':'CHECK',awg?.ok?'ok':'bad');$('n13AwgSub').textContent=awg?.detail||'service';
    const services=results.filter(x=>['AWG service','Panel service','Nginx'].includes(x.name));
    const net=results.filter(x=>['IPv4 forwarding','WAN route','NAT','AWG forwarding','DNS'].includes(x.name));
    $('n13Services').innerHTML=services.length?services.map(row).join(''):'<div class="n13-empty">Нет данных о сервисах</div>';
    $('n13Network').innerHTML=net.length?net.map(row).join(''):'<div class="n13-empty">Нет данных о сети</div>';
    const netOk=net.length>0&&net.every(x=>x.ok);
    $('n13NetworkBadge').textContent=netOk?'OK':'ВНИМАНИЕ';$('n13NetworkBadge').className='n13-badge '+(netOk?'ok':'warn');
    $('n13Results').innerHTML=results.length?results.map(row).join(''):'<div class="n13-empty">Диагностика не вернула результатов</div>';
    const ts=(d.timestamp||Date.now()/1000)*1000;
    $('n13Checked').textContent=new Date(ts).toLocaleTimeString();
    $('n13Updated').textContent='Последняя проверка: '+new Date(ts).toLocaleTimeString();
    $('n13Live').textContent='LIVE · 15 сек';
  }catch(e){
    setValue('n13Health','ERROR','bad');$('n13HealthSub').textContent=e.message;$('n13Live').textContent='ОШИБКА · повтор через 15 сек';
  }
}
$('n13Refresh').addEventListener('click',refresh);refresh();setInterval(refresh,15000);
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
