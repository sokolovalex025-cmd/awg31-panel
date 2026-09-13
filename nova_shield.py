#!/usr/bin/env python3
"""NOVA Shield: defensive connectivity resilience and failover telemetry.

This module does not modify awg0 or attempt to evade network controls. It
provides health scoring for configured endpoints, DNS/IPv4/IPv6/TCP checks,
MTU probing, and an operator dashboard for diagnosing failures.
"""
import socket, subprocess, time
from flask import jsonify, render_template_string

TARGETS = [
    ("Cloudflare", "1.1.1.1", 443),
    ("Google", "8.8.8.8", 443),
    ("GitHub", "github.com", 443),
    ("Telegram", "telegram.org", 443),
]

def _run(cmd, timeout=4):
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 99, str(e)

def _tcp(host, port, timeout=3):
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, round((time.monotonic()-started)*1000, 1), ""
    except Exception as e:
        return False, None, str(e)

def _dns(host):
    try:
        infos = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)
        addrs = sorted({x[4][0] for x in infos})
        return True, addrs
    except Exception as e:
        return False, [str(e)]

def _mtu():
    # Safe DF probes against a well-known public IPv4 endpoint. We only report
    # results; no routing or interface configuration is changed.
    for size in (1200, 1100, 1000):
        rc, out = _run(["ping", "-4", "-M", "do", "-c", "1", "-W", "2", "-s", str(size), "1.1.1.1"], 3)
        if rc == 0:
            return {"ok": True, "largest_tested": size, "output": out[-300:]}
    return {"ok": False, "largest_tested": None}

def status():
    rows=[]
    for name, host, port in TARGETS:
        dns_ok, addrs = _dns(host)
        tcp_ok, latency, error = _tcp(host, port)
        score = (50 if tcp_ok else 0) + (25 if dns_ok else 0) + (25 if latency is not None and latency < 250 else 10 if latency is not None else 0)
        rows.append({"name":name,"host":host,"port":port,"dns":dns_ok,"addresses":addrs[:6],"tcp":tcp_ok,"latency_ms":latency,"score":score,"error":error})
    awg = _run(["ip","link","show","awg0"])[0] == 0
    fwd = _run(["sysctl","-n","net.ipv4.ip_forward"])[1] == "1"
    return {"time":int(time.time()),"awg0":awg,"forwarding":fwd,"mtu":_mtu(),"targets":rows}

PAGE = r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA Shield</title><style>body{margin:0;background:#070a10;color:#edf3fa;font:14px system-ui,Segoe UI,Arial;padding:28px}.wrap{max-width:1200px;margin:auto}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.title{font-size:30px;font-weight:900}.sub{color:#8a99ad;margin-top:5px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{background:#101824;border:1px solid #263348;border-radius:16px;padding:18px}.label{color:#738298;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.value{font-size:24px;font-weight:900;margin-top:8px}.ok{color:#4fe0bd}.bad{color:#ff7186}.row{display:grid;grid-template-columns:1.2fr .8fr .7fr .7fr;gap:10px;align-items:center;padding:13px 0;border-bottom:1px solid #202b3c}.row:last-child{border:0}.pill{display:inline-block;padding:5px 9px;border-radius:99px;background:#172233}.btn{border:1px solid #31425e;background:#151f2f;color:#fff;border-radius:10px;padding:10px 13px;text-decoration:none;font-weight:750}.note{margin-top:14px;color:#aab7c7;line-height:1.55}@media(max-width:700px){.grid{grid-template-columns:1fr}.row{grid-template-columns:1fr 1fr}} </style></head><body><div class="wrap"><div class="top"><div><div class="title">🛡️ NOVA Shield</div><div class="sub">Resilience & failover diagnostics</div></div><button class="btn" onclick="run()">Проверить</button></div><div class="grid"><div class="card"><div class="label">AWG0</div><div id="awg" class="value">—</div></div><div class="card"><div class="label">Forwarding</div><div id="fwd" class="value">—</div></div><div class="card"><div class="label">MTU / DF</div><div id="mtu" class="value">—</div></div></div><div class="card" style="margin-top:14px"><div class="label">Endpoint health</div><div id="rows"></div><div class="note">Shield только наблюдает и диагностирует. Производственный awg0 и его параметры не изменяются автоматически.</div><div style="margin-top:15px"><a class="btn" href="/">← Панель</a><a class="btn" href="/antiblock">AntiBlock</a></div></div></div><script>async function run(){const d=await (await fetch('/api/shield/status')).json();const set=(id,t,c)=>{let e=document.getElementById(id);e.textContent=t;e.className='value '+c};set('awg',d.awg0?'ONLINE':'ERROR',d.awg0?'ok':'bad');set('fwd',d.forwarding?'ON':'OFF',d.forwarding?'ok':'bad');set('mtu',d.mtu.ok?('≥ '+d.mtu.largest_tested):'FAIL',d.mtu.ok?'ok':'bad');document.getElementById('rows').innerHTML=d.targets.map(x=>`<div class="row"><div><b>${x.name}</b><div class="sub">${x.host}:${x.port}</div></div><span class="pill ${x.dns?'ok':'bad'}">DNS ${x.dns?'OK':'FAIL'}</span><span class="pill ${x.tcp?'ok':'bad'}">TCP ${x.tcp?'OK':'FAIL'}</span><span class="pill">${x.latency_ms??'—'} ms / ${x.score}</span></div>`).join('')}run();setInterval(run,30000)</script></body></html>'''

def apply(app):
    app.add_url_rule('/shield', 'nova_shield_page', lambda: render_template_string(PAGE))
    app.add_url_rule('/api/shield/status', 'nova_shield_status', lambda: jsonify(status()))
    return True
