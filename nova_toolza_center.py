"""NOVA AWG Toolz 2.0 — unified, read-only AWG/network operations dashboard.

The dashboard is intentionally non-destructive: it reads AWG, routing, firewall/NAT,
DNS and a small set of connectivity probes. It never writes awg0.conf, firewall
rules, routes or service state.
"""
from __future__ import annotations
import re
import socket
import subprocess
from flask import jsonify, request

PARAMS = {
    "Jc":"4","Jmin":"40","Jmax":"120",
    "S1":"16","S2":"16","S3":"16","S4":"16",
    "H1":"1","H2":"2","H3":"3","H4":"4",
    "RandomTrailers":"on","DisableCookies":"on",
}
SAFE_KEYS = tuple(PARAMS)

RU_TARGETS = [
    ("Gosuslugi", "gosuslugi.ru", 443),
    ("Yandex", "yandex.ru", 443),
    ("RZD", "rzd.ru", 443),
]

def _run(*args, timeout=3):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip()
    except Exception:
        return ""

def _version():
    tools = _run("awg", "--version")
    loaded = _run("bash", "-lc", "cat /sys/module/amneziawg/version 2>/dev/null")
    return {"tools": tools or "unknown", "loaded_module": loaded or "unknown"}

def _listen_port():
    out = _run("bash", "-lc", "ss -lunH 2>/dev/null | awk '{print $5}'")
    ports = []
    for line in out.splitlines():
        m = re.search(r":(\d+)$", line)
        if m:
            ports.append(int(m.group(1)))
    return sorted(set(ports))

def _config():
    path = "/etc/amnezia/amneziawg/awg0.conf"
    try:
        data = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:
        return {}
    result = {}
    for line in data:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k in SAFE_KEYS or k == "ListenPort":
            result[k] = v
    return result

def _route():
    out = _run("ip", "-4", "route", "show", "default")
    return out.splitlines()[0] if out else "unknown"

def _forwarding():
    try:
        return open("/proc/sys/net/ipv4/ip_forward").read().strip() == "1"
    except Exception:
        return False

def _nat():
    ipt = _run("iptables", "-t", "nat", "-S", "POSTROUTING")
    nft = _run("nft", "list", "chain", "ip", "nat", "postrouting")
    return bool(re.search(r"MASQUERADE", ipt, re.I) or re.search(r"masquerade", nft, re.I))

def _public_ipv4():
    out = _run("curl", "-4", "-fsS", "--max-time", "3", "https://api.ipify.org", timeout=5)
    return out if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", out or "") else "unknown"

def _dns():
    out = _run("resolvectl", "dns")
    return [x.strip() for x in re.findall(r"(?:Global|Link[^:]*):\s*(.*)", out) if x.strip()]

def _tcp(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _probe(name, host, port):
    try:
        ips = sorted({x[4][0] for x in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)})
    except Exception:
        ips = []
    return {
        "name": name, "host": host, "port": port, "ipv4": ips,
        "dns_ok": bool(ips),
        "tcp_ok": any(_tcp(ip, port) for ip in ips),
    }

def _awg_state():
    out = _run("awg", "show", "awg0")
    return {
        "up": bool(out),
        "interface": "awg0" if out else "missing",
        "has_private_key": False,
        "raw": None,
    }

def _daemon():
    try:
        import urllib.request, pathlib
        t=pathlib.Path("/etc/awg-toolz/token").read_text().strip()
        req=urllib.request.Request("http://127.0.0.1:9090/v1/status",headers={"X-NOVA-Toolz-Token":t})
        with urllib.request.urlopen(req,timeout=2) as f: return __import__("json").load(f)
    except Exception as e: return {"ok":False,"error":str(e)}

def snapshot():
    cfg = _config()
    mismatches = {k: {"expected": v, "actual": cfg.get(k)}
                  for k, v in PARAMS.items() if cfg.get(k) != v}
    return {
        "mode": "read-only",
        "daemon": _daemon(),
        "awg": _version(),
        "awg_state": _awg_state(),
        "udp_ports": _listen_port(),
        "listen_port": cfg.get("ListenPort"),
        "profile": cfg,
        "expected_profile": PARAMS,
        "mismatches": mismatches,
        "profile_ok": not mismatches,
        "network": {
            "public_ipv4": _public_ipv4(),
            "default_route": _route(),
            "forwarding": _forwarding(),
            "nat": _nat(),
            "dns": _dns(),
        },
        "probes": [_probe(*x) for x in RU_TARGETS],
    }

HTML = r'''<style>
.nova-tz{max-width:1260px;margin:22px auto;padding:0 18px;font-family:inherit;color:#e8eef7}
.nova-tz *{box-sizing:border-box}
.nova-tz-hero{position:relative;overflow:hidden;padding:24px 26px;margin-bottom:16px;border:1px solid rgba(120,170,255,.18);border-radius:24px;background:linear-gradient(135deg,rgba(18,30,48,.98),rgba(25,39,63,.92));box-shadow:0 18px 50px rgba(0,0,0,.18)}
.nova-tz-hero:after{content:"";position:absolute;width:260px;height:260px;right:-90px;top:-120px;border-radius:50%;background:rgba(75,170,255,.12);filter:blur(5px)}
.nova-tz-head{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:18px}
.nova-tz-title{display:flex;align-items:center;gap:12px;margin:0;font-size:28px;letter-spacing:-.4px}
.nova-tz-title-icon{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:rgba(85,223,185,.12);border:1px solid rgba(85,223,185,.2)}
.nova-tz-sub{margin:7px 0 0;color:#91a4bc;font-size:14px}
.nova-tz-refresh,.nova-tz-action{border:1px solid rgba(255,255,255,.13);border-radius:12px;padding:10px 14px;background:rgba(255,255,255,.06);color:#edf4ff;cursor:pointer;transition:.18s ease}
.nova-tz-refresh:hover,.nova-tz-action:hover{background:rgba(255,255,255,.11);transform:translateY(-1px)}
.nova-tz-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.nova-tz-card{min-height:104px;padding:17px 18px;border:1px solid rgba(125,160,205,.14);border-radius:18px;background:linear-gradient(145deg,rgba(25,37,55,.96),rgba(17,27,42,.96));box-shadow:0 8px 24px rgba(0,0,0,.08)}
.nova-tz-card b{display:block;max-width:100%;font-size:20px;line-height:1.2;overflow:hidden;text-overflow:ellipsis}
.nova-tz-card small{display:block;color:#8fa1b8;margin-top:8px;font-size:12px}
.nova-tz-card .tz-muted{font-size:15px;color:#c9d4e2}
.nova-tz-ok{color:#55dfb9!important}.nova-tz-bad{color:#ff7186!important}.nova-tz-warn{color:#f3c969!important}.nova-tz-blue{color:#79b9ff!important}
.nova-tz-panel{margin-top:14px;padding:19px 20px;border:1px solid rgba(125,160,205,.14);border-radius:20px;background:rgba(17,27,42,.94);box-shadow:0 10px 28px rgba(0,0,0,.08)}
.nova-tz-panel-title{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:17px;font-weight:700}
.nova-tz-panel-sub{color:#8195ad;font-size:12px;margin-top:4px}
.nova-tz-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:15px}
.nova-tz-action{font-weight:600}
.nova-tz-action.primary{background:rgba(85,223,185,.1);border-color:rgba(85,223,185,.24)}
.nova-tz-action.danger{background:rgba(255,113,134,.08);border-color:rgba(255,113,134,.18)}
.nova-tz-note{display:block;color:#8195ad;margin-top:11px;font-size:12px}
.nova-tz-profile{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:15px}
.nova-tz-param{padding:11px 12px;border-radius:12px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.06)}
.nova-tz-param span{display:block;color:#8094ac;font-size:11px}.nova-tz-param strong{display:block;margin-top:3px;color:#eaf1fa;font:600 14px ui-monospace,SFMono-Regular,Menlo,monospace}
.nova-tz-status{margin-top:14px;padding:11px 13px;border-radius:12px;background:rgba(85,223,185,.07);border:1px solid rgba(85,223,185,.12)}
.nova-tz-table{width:100%;border-collapse:collapse;margin-top:12px}.nova-tz-table td,.nova-tz-table th{padding:11px 9px;border-bottom:1px solid rgba(255,255,255,.07);text-align:left}.nova-tz-table th{color:#8498b0;font-size:11px;text-transform:uppercase;letter-spacing:.06em}.nova-tz-table td{font-size:13px}.nova-tz-table small{display:block;color:#71849b;margin-top:2px}
.nova-tz-pre{white-space:pre-wrap;font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;color:#c8d4e2;background:rgba(0,0,0,.13);padding:13px;border-radius:12px;margin:13px 0 0}
.nova-tz-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;font-size:11px;background:rgba(255,255,255,.06);color:#a9b8c9}
@media(max-width:980px){.nova-tz-grid{grid-template-columns:repeat(2,1fr)}.nova-tz-profile{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.nova-tz{padding:0 10px}.nova-tz-head{align-items:flex-start;flex-direction:column}.nova-tz-title{font-size:23px}.nova-tz-grid,.nova-tz-profile{grid-template-columns:1fr}.nova-tz-table{font-size:12px}.nova-tz-table th:nth-child(2),.nova-tz-table td:nth-child(2){display:none}}
</style>
<section class="nova-tz">
<div class="nova-tz-hero">
  <div class="nova-tz-head">
    <div>
      <h2 class="nova-tz-title"><span class="nova-tz-title-icon">🛠️</span>NOVA AWG Toolz <span class="nova-tz-badge">2.0</span></h2>
      <div class="nova-tz-sub">AWG 3.1 • единый центр состояния, диагностики и подтверждённых операций</div>
    </div>
    <button class="nova-tz-refresh" onclick="novaToolzaLoad()">↻ Обновить</button>
  </div>
</div>

<div class="nova-tz-grid">
<div class="nova-tz-card"><b id="tz-awg">—</b><small>AWG interface</small></div>
<div class="nova-tz-card"><b id="tz-tools" class="tz-muted">—</b><small>AWG Tools</small></div>
<div class="nova-tz-card"><b id="tz-port" class="nova-tz-blue">—</b><small>UDP listener</small></div>
<div class="nova-tz-card"><b id="tz-profile">—</b><small>NOVA profile</small></div>
<div class="nova-tz-card"><b id="tz-ip" class="tz-muted">—</b><small>Public IPv4</small></div>
<div class="nova-tz-card"><b id="tz-route" class="tz-muted">—</b><small>Default route</small></div>
<div class="nova-tz-card"><b id="tz-fwd">—</b><small>IPv4 forwarding</small></div>
<div class="nova-tz-card"><b id="tz-nat">—</b><small>NAT / MASQUERADE</small></div>
</div>

<div class="nova-tz-panel">
  <div class="nova-tz-panel-title"><span>⚙️ Управление сервером</span><span class="nova-tz-badge">требует подтверждения</span></div>
  <div class="nova-tz-panel-sub">Операции выполняются локальным Toolz daemon и не доступны напрямую из интернета.</div>
  <div class="nova-tz-actions">
    <button class="nova-tz-action primary" onclick="novaToolzaAction('apply-profile')">✓ Применить профиль</button>
    <button class="nova-tz-action" onclick="novaToolzaAction('repair-nat')">🔧 Исправить NAT</button>
    <button class="nova-tz-action" onclick="novaToolzaAction('restart-awg')">↻ Перезапустить AWG</button>
    <button class="nova-tz-action danger" onclick="novaToolzaAction('repair-all')">🛠️ Исправить всё</button>
  </div>
  <small class="nova-tz-note">Каждая изменяющая операция запрашивает подтверждение перед выполнением.</small>
</div>

<div class="nova-tz-panel">
  <div class="nova-tz-panel-title"><span>📱 NOVA Strong Mobile</span><span class="nova-tz-badge">AWG 3.1 canonical</span></div>
  <div class="nova-tz-panel-sub">Параметры профиля, которые использует сервер и генератор клиентских конфигураций.</div>
  <div class="nova-tz-profile" id="tz-profile-grid">Загрузка…</div>
  <div class="nova-tz-status" id="tz-result">Проверяем профиль…</div>
</div>

<div class="nova-tz-panel">
  <div class="nova-tz-panel-title"><span>🌐 RU Access</span><span class="nova-tz-badge">TCP/443</span></div>
  <div class="nova-tz-panel-sub">Быстрый контроль DNS и TCP-доступности выбранных российских ресурсов с VPS.</div>
  <table class="nova-tz-table"><thead><tr><th>Ресурс</th><th>IPv4</th><th>DNS</th><th>TCP/443</th></tr></thead><tbody id="tz-probes"><tr><td colspan="4">Проверяем…</td></tr></tbody></table>
</div>

<div class="nova-tz-panel">
  <div class="nova-tz-panel-title"><span>📡 AWG / сеть</span><span class="nova-tz-badge">live snapshot</span></div>
  <pre class="nova-tz-pre" id="tz-details">Загрузка…</pre>
</div>
</section>
<script>
async function novaToolzaAction(action){
 const labels={'apply-profile':'применить профиль NOVA','repair-nat':'исправить NAT','restart-awg':'перезапустить AWG','repair-all':'выполнить полное исправление'};
 if(!confirm('Подтвердить: '+(labels[action]||action)+'?')) return;
 try{
  const r=await fetch('/api/nova/toolza-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  const d=await r.json(); alert(d.ok?'Операция выполнена: '+action:'Ошибка: '+(d.error||'см. результат')); novaToolzaLoad();
 }catch(e){alert('Ошибка Toolz: '+e)}
}
async function novaToolzaLoad(){
 try{
  const r=await fetch('/api/nova/toolza-center',{cache:'no-store'}); const d=await r.json();
  const cls=(ok)=>ok?'nova-tz-ok':'nova-tz-bad';
  document.getElementById('tz-awg').textContent=d.awg_state.up?'● ONLINE':'● OFFLINE'; document.getElementById('tz-awg').className=cls(d.awg_state.up);
  document.getElementById('tz-tools').textContent=d.awg.tools;
  document.getElementById('tz-port').textContent=d.listen_port||'—';
  document.getElementById('tz-profile').textContent=d.profile_ok?'✓ PASS':'⚠ CHECK'; document.getElementById('tz-profile').className=cls(d.profile_ok);
  document.getElementById('tz-ip').textContent=d.network.public_ipv4; document.getElementById('tz-route').textContent=d.network.default_route;
  document.getElementById('tz-fwd').textContent=d.network.forwarding?'ON':'OFF'; document.getElementById('tz-fwd').className=cls(d.network.forwarding);
  document.getElementById('tz-nat').textContent=d.network.nat?'FOUND':'MISSING'; document.getElementById('tz-nat').className=cls(d.network.nat);
  document.getElementById('tz-profile-grid').innerHTML=Object.entries(d.expected_profile).map(x=>'<div class="nova-tz-param"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');
  const bad=Object.entries(d.mismatches||{}).map(x=>x[0]+': expected '+x[1].expected+', actual '+x[1].actual);
  document.getElementById('tz-result').className='nova-tz-status '+(d.profile_ok?'nova-tz-ok':'nova-tz-bad');
  document.getElementById('tz-result').textContent=d.profile_ok?'✓ Canonical profile совпадает':'⚠ '+bad.join(' · ');
  document.getElementById('tz-probes').innerHTML=(d.probes||[]).map(p=>'<tr><td><strong>'+p.name+'</strong><small>'+p.host+'</small></td><td>'+((p.ipv4||[]).join(', ')||'—')+'</td><td class="'+cls(p.dns_ok)+'">'+(p.dns_ok?'OK':'FAIL')+'</td><td class="'+cls(p.tcp_ok)+'">'+(p.tcp_ok?'OPEN':'TIMEOUT/FAIL')+'</td></tr>').join('');
  document.getElementById('tz-details').textContent=[
   'AWG tools: '+d.awg.tools,'Kernel module: '+d.awg.loaded_module,'AWG0: '+(d.awg_state.up?'ONLINE':'OFFLINE'),
   'UDP ports: '+(d.udp_ports||[]).join(', '),'ListenPort: '+(d.listen_port||'—'),'Public IPv4: '+d.network.public_ipv4,
   'Default route: '+d.network.default_route,'Forwarding: '+d.network.forwarding,'NAT: '+d.network.nat,'DNS: '+(d.network.dns||[]).join(' | ')
  ].join('\\n');
 }catch(e){document.getElementById('tz-details').textContent='Ошибка проверки: '+e}
}
novaToolzaLoad(); setInterval(novaToolzaLoad,15000);
</script>'''

def apply(nova):
    app = nova.core.app
    @app.route("/awg-toolza")
    def awg_toolza():
        return HTML
    @app.route("/api/nova/toolza-action", methods=["POST"])
    def api_toolza_action():
        import json as _json, pathlib as _pathlib, urllib.request as _request
        body=_json.loads(request.get_data(as_text=True) or "{}")
        token=_pathlib.Path("/etc/awg-toolz/token").read_text().strip()
        req=_request.Request("http://127.0.0.1:9090/v1/action",data=_json.dumps(body).encode(),headers={"Content-Type":"application/json","X-NOVA-Toolz-Token":token,"X-NOVA-Confirm":"APPLY"},method="POST")
        try:
            with _request.urlopen(req,timeout=35) as f:
                return jsonify(_json.loads(f.read().decode()))
        except Exception as e:
            return jsonify({"ok":False,"error":str(e)}),500

    @app.route("/api/nova/toolza-center")
    def api_toolza():
        return jsonify(snapshot())
    return nova
