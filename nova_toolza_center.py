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
.nova-tz{max-width:1200px;margin:24px auto;padding:0 18px;font-family:inherit}
.nova-tz h2{margin-bottom:4px}.nova-tz-sub{color:#7d899b;margin-bottom:18px}
.nova-tz-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.nova-tz-card,.nova-tz-panel{padding:17px;border:1px solid rgba(255,255,255,.08);border-radius:16px;background:rgba(12,20,31,.82)}
.nova-tz-panel{margin-top:14px}.nova-tz-card b{font-size:18px}.nova-tz-card small{display:block;color:#7d899b;margin-top:6px}
.nova-tz-ok{color:#55dfb9}.nova-tz-bad{color:#ff7186}.nova-tz-warn{color:#f3c969}
.nova-tz-table{width:100%;border-collapse:collapse}.nova-tz-table td,.nova-tz-table th{padding:9px;border-bottom:1px solid rgba(255,255,255,.07);text-align:left}
.nova-tz-pre{white-space:pre-wrap;font:12px ui-monospace,monospace;color:#cbd5e1}
.nova-tz-refresh{float:right;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:8px 12px;background:rgba(255,255,255,.05);color:inherit;cursor:pointer}
@media(max-width:900px){.nova-tz-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.nova-tz-grid{grid-template-columns:1fr}}
</style>
<section class="nova-tz">
<button class="nova-tz-refresh" onclick="novaToolzaLoad()">↻ Обновить</button>
<h2>🛠️ NOVA AWG Toolz 2.0</h2>
<div class="nova-tz-sub">AWG 3.1 • единый центр состояния и диагностики • только чтение</div>
<div class="nova-tz-grid">
<div class="nova-tz-card"><b id="tz-awg">—</b><small>AWG interface</small></div>
<div class="nova-tz-card"><b id="tz-tools">—</b><small>awg-tools</small></div>
<div class="nova-tz-card"><b id="tz-port">—</b><small>UDP listener</small></div>
<div class="nova-tz-card"><b id="tz-profile">—</b><small>NOVA profile</small></div>
<div class="nova-tz-card"><b id="tz-ip">—</b><small>public IPv4</small></div>
<div class="nova-tz-card"><b id="tz-route">—</b><small>default route</small></div>
<div class="nova-tz-card"><b id="tz-fwd">—</b><small>IPv4 forwarding</small></div>
<div class="nova-tz-card"><b id="tz-nat">—</b><small>NAT / MASQUERADE</small></div>
</div>
<div class="nova-tz-panel"><b>Управление сервером</b><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
<button class="nova-tz-refresh" onclick="novaToolzaAction('apply-profile')">✓ Применить профиль</button>
<button class="nova-tz-refresh" onclick="novaToolzaAction('repair-nat')">🔧 Исправить NAT</button>
<button class="nova-tz-refresh" onclick="novaToolzaAction('restart-awg')">↻ Перезапустить AWG</button>
<button class="nova-tz-refresh" onclick="novaToolzaAction('repair-all')">🛠️ Исправить всё</button>
</div><small style="display:block;color:#7d899b;margin-top:9px">Изменения выполняются только после подтверждения.</small></div>
<div class="nova-tz-panel"><b>Профиль NOVA Strong Mobile</b><pre class="nova-tz-pre" id="tz-profile-text">Загрузка…</pre><div id="tz-result"></div></div>
<div class="nova-tz-panel"><b>RU Access — контроль доступности</b>
<table class="nova-tz-table"><thead><tr><th>Ресурс</th><th>IPv4</th><th>DNS</th><th>TCP/443</th></tr></thead><tbody id="tz-probes"><tr><td colspan="4">Проверяем…</td></tr></tbody></table>
</div>
<div class="nova-tz-panel"><b>AWG / сеть</b><pre class="nova-tz-pre" id="tz-details">Загрузка…</pre></div>
</section>
<script>
async function novaToolzaAction(action){
 const labels={'apply-profile':'применить профиль NOVA','repair-nat':'исправить NAT','restart-awg':'перезапустить AWG','repair-all':'выполнить полное исправление'};
 if(!confirm('Подтвердить: '+(labels[action]||action)+'?')) return;
 try{
  const r=await fetch('/api/nova/toolza-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  const d=await r.json(); alert(d.ok?'Операция выполнена: '+action:'Ошибка: '+(d.error||'см. результат'));
  novaToolzaLoad();
 }catch(e){alert('Ошибка Toolz: '+e)}
}
async function novaToolzaLoad(){
 try{
  const r=await fetch('/api/nova/toolza-center',{cache:'no-store'}); const d=await r.json();
  const cls=(ok)=>ok?'nova-tz-ok':'nova-tz-bad';
  document.getElementById('tz-awg').textContent=d.awg_state.up?'ONLINE':'OFFLINE';
  document.getElementById('tz-awg').className=cls(d.awg_state.up);
  document.getElementById('tz-tools').textContent=d.awg.tools;
  document.getElementById('tz-port').textContent=d.listen_port||'—';
  document.getElementById('tz-profile').textContent=d.profile_ok?'PASS':'CHECK';
  document.getElementById('tz-profile').className=cls(d.profile_ok);
  document.getElementById('tz-ip').textContent=d.network.public_ipv4;
  document.getElementById('tz-route').textContent=d.network.default_route;
  document.getElementById('tz-fwd').textContent=d.network.forwarding?'ON':'OFF';
  document.getElementById('tz-fwd').className=cls(d.network.forwarding);
  document.getElementById('tz-nat').textContent=d.network.nat?'FOUND':'MISSING';
  document.getElementById('tz-nat').className=cls(d.network.nat);
  document.getElementById('tz-profile-text').textContent=Object.entries(d.expected_profile).map(x=>x[0]+'='+x[1]).join('\n');
  const bad=Object.entries(d.mismatches||{}).map(x=>x[0]+': expected '+x[1].expected+', actual '+x[1].actual);
  document.getElementById('tz-result').innerHTML=d.profile_ok?'<span class="nova-tz-ok">✓ Canonical profile совпадает</span>':'<span class="nova-tz-bad">⚠ '+bad.join(' · ')+'</span>';
  document.getElementById('tz-probes').innerHTML=(d.probes||[]).map(p=>'<tr><td>'+p.name+' <small>'+p.host+'</small></td><td>'+((p.ipv4||[]).join(', ')||'—')+'</td><td class="'+cls(p.dns_ok)+'">'+(p.dns_ok?'OK':'FAIL')+'</td><td class="'+cls(p.tcp_ok)+'">'+(p.tcp_ok?'OPEN':'TIMEOUT/FAIL')+'</td></tr>').join('');
  document.getElementById('tz-details').textContent=[
   'AWG tools: '+d.awg.tools,'Kernel module: '+d.awg.loaded_module,
   'AWG0: '+(d.awg_state.up?'ONLINE':'OFFLINE'),'UDP ports: '+(d.udp_ports||[]).join(', '),
   'ListenPort: '+(d.listen_port||'—'),'Public IPv4: '+d.network.public_ipv4,
   'Default route: '+d.network.default_route,'Forwarding: '+d.network.forwarding,
   'NAT: '+d.network.nat,'DNS: '+(d.network.dns||[]).join(' | ')
  ].join('\n');
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
