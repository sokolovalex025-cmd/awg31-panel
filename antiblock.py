#!/usr/bin/env python3
"""NOVA AntiBlock Center.

Provides an operator-facing control plane for resilient connectivity: health
checks, DNS/HTTPS diagnostics, endpoint profiles and safe network repair
hints. It deliberately does not rewrite the primary awg0 configuration.
"""
import json, os, socket, subprocess, time
from pathlib import Path
from flask import request, jsonify, render_template_string

BASE = Path('/opt/awg31-panel')
DB = BASE / 'panel.db'
DEFAULT_TARGETS = [
    ('Cloudflare', '1.1.1.1', 443),
    ('Google DNS', '8.8.8.8', 443),
    ('GitHub', 'github.com', 443),
    ('Telegram', 'telegram.org', 443),
]


def _run(cmd, timeout=5):
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 99, str(e)


def _tcp(host, port, timeout=3):
    t = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, round((time.time()-t)*1000, 1), ''
    except Exception as e:
        return False, None, str(e)


def _settings():
    import sqlite3
    con = sqlite3.connect(DB)
    rows = dict(con.execute('select k,v from settings'))
    con.close()
    return rows


def _system():
    checks = {}
    checks['ipv4_forwarding'] = Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() == '1'
    checks['awg0'] = _run(['ip','link','show','awg0'])[0] == 0
    checks['nftables'] = _run(['nft','--version'])[0] == 0
    checks['iptables'] = _run(['iptables','-V'])[0] == 0
    checks['dns'] = _run(['getent','hosts','cloudflare.com'])[0] == 0
    return checks


def status():
    results=[]
    for name, host, port in DEFAULT_TARGETS:
        ok, ms, err = _tcp(host, port)
        results.append({'name':name,'host':host,'port':port,'ok':ok,'latency_ms':ms,'error':err})
    return {'time':int(time.time()), 'system':_system(), 'targets':results,
            'settings':_settings()}


def _page():
    return render_template_string(r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AntiBlock</title>
<style>:root{--bg:#070a10;--c:#101824;--line:#263348;--text:#edf3fa;--muted:#8a99ad;--ok:#4fe0bd;--bad:#ff7186;--a:#8093ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#18264a,#070a10 42%);color:var(--text);font:14px system-ui,Segoe UI,Arial;padding:28px}.wrap{max-width:1200px;margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:22px}.title{font-size:30px;font-weight:900;letter-spacing:-.04em}.sub{color:var(--muted);margin-top:5px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:rgba(16,24,36,.88);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px;box-shadow:0 20px 60px rgba(0,0,0,.28)}.label{font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:#738298;font-weight:800}.value{font-size:25px;font-weight:900;margin-top:8px}.ok{color:var(--ok)}.bad{color:var(--bad)}.targets{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.target{display:flex;justify-content:space-between;gap:15px;align-items:center}.pill{padding:5px 8px;border-radius:99px;font-size:10px;font-weight:800}.pill.ok{background:#0b3028}.pill.bad{background:#34151f}.actions{display:flex;gap:8px;margin:16px 0}.btn{border:1px solid #31425e;background:#151f2f;color:#fff;border-radius:10px;padding:10px 13px;cursor:pointer;font-weight:750}.btn.primary{background:#596ff0;border-color:#7388ff}.note{margin-top:14px;padding:13px;border-radius:11px;background:#0b111a;border:1px solid #202d40;color:#aab7c7;line-height:1.55}@media(max-width:800px){.grid,.targets{grid-template-columns:1fr 1fr}}@media(max-width:520px){body{padding:15px}.grid,.targets{grid-template-columns:1fr}}</style></head><body><div class="wrap"><div class="top"><div><div class="title">🛡️ AntiBlock</div><div class="sub">NOVA resilience & connectivity center</div></div><button class="btn primary" onclick="run()">Проверить сейчас</button></div><div class="grid"><div class="card"><div class="label">AWG</div><div id="awg" class="value">—</div></div><div class="card"><div class="label">Forwarding</div><div id="fwd" class="value">—</div></div><div class="card"><div class="label">DNS</div><div id="dns" class="value">—</div></div><div class="card"><div class="label">Сеть</div><div id="net" class="value">—</div></div></div><div class="card" style="margin-top:14px"><div class="label">Контрольные точки</div><div id="targets" class="targets"></div><div class="actions"><a class="btn" href="/">← Панель</a><a class="btn" href="/diagnostics">Диагностика</a><a class="btn" href="/network">Firewall</a></div><div class="note">AntiBlock проверяет доступность DNS/HTTPS и состояние сетевого стека, не меняя параметры основного <b>awg0</b>. Это позволяет быстро отличить блокировку/сетевой сбой от ошибки конфигурации.</div></div></div><script>async function run(){let r=await fetch('/api/antiblock/status');let d=await r.json();let s=d.system;document.querySelector('#awg').textContent=s.awg0?'ONLINE':'ERROR';document.querySelector('#awg').className='value '+(s.awg0?'ok':'bad');document.querySelector('#fwd').textContent=s.ipv4_forwarding?'ON':'OFF';document.querySelector('#fwd').className='value '+(s.ipv4_forwarding?'ok':'bad');document.querySelector('#dns').textContent=s.dns?'OK':'ERROR';document.querySelector('#dns').className='value '+(s.dns?'ok':'bad');let good=d.targets.filter(x=>x.ok).length;document.querySelector('#net').textContent=good+'/'+d.targets.length;document.querySelector('#net').className='value '+(good===d.targets.length?'ok':good?'':'bad');document.querySelector('#targets').innerHTML=d.targets.map(x=>`<div class="card target"><div><b>${x.name}</b><div class="sub">${x.host}:${x.port}</div></div><span class="pill ${x.ok?'ok':'bad'}">${x.ok?(x.latency_ms+' ms'):'FAIL'}</span></div>`).join('')}run();setInterval(run,30000)</script></body></html>''')


def apply(app):
    app.add_url_rule('/antiblock', 'antiblock_page', _page)
    app.add_url_rule('/api/antiblock/status', 'antiblock_status', lambda: jsonify(status()))
    return True
