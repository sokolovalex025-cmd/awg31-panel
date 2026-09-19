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
.nova-tz{--bg:#f5f7fb;--surface:#fff;--surface2:#f8fafc;--text:#162033;--muted:#718096;--line:#e6ebf2;--accent:#14b8a6;--accent2:#3b82f6;--ok:#0f9f72;--bad:#e05268;--warn:#c58b18;max-width:1280px;margin:0 auto;padding:24px 20px 42px;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.nova-tz *{box-sizing:border-box}
.nova-tz.dark{--bg:#0b1220;--surface:#111a2b;--surface2:#172235;--text:#edf4ff;--muted:#91a0b6;--line:#25344b}
.nova-tz{background:transparent}
.nova-tz-shell{padding:4px}
.nova-tz-hero{position:relative;overflow:hidden;min-height:178px;padding:28px 30px;border:1px solid var(--line);border-radius:28px;background:linear-gradient(135deg,#ffffff 0%,#f1fbfa 52%,#eef5ff 100%);box-shadow:0 18px 55px rgba(26,45,75,.09)}
.nova-tz.dark .nova-tz-hero{background:linear-gradient(135deg,#101a2b,#13283a 55%,#14243b)}
.nova-tz-hero:before,.nova-tz-hero:after{content:"";position:absolute;border-radius:50%;pointer-events:none}
.nova-tz-hero:before{width:310px;height:310px;right:-105px;top:-190px;background:rgba(20,184,166,.14);filter:blur(4px)}
.nova-tz-hero:after{width:220px;height:220px;right:130px;bottom:-170px;background:rgba(59,130,246,.10);filter:blur(5px)}
.nova-tz-head{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:20px}
.nova-tz-brand{display:flex;align-items:center;gap:15px}
.nova-tz-logo{width:54px;height:54px;display:grid;place-items:center;border-radius:17px;background:linear-gradient(135deg,#14b8a6,#3b82f6);color:#fff;font-size:25px;box-shadow:0 10px 24px rgba(20,184,166,.22)}
.nova-tz-title{margin:0;font-size:29px;line-height:1.1;letter-spacing:-.7px;font-weight:800}
.nova-tz-sub{margin:7px 0 0;color:var(--muted);font-size:13px}
.nova-tz-head-actions{display:flex;gap:8px}
.nova-tz-btn{border:1px solid var(--line);border-radius:12px;padding:10px 13px;background:var(--surface);color:var(--text);cursor:pointer;font-weight:650;transition:.18s ease;box-shadow:0 4px 12px rgba(30,50,80,.05)}
.nova-tz-btn:hover{transform:translateY(-1px);box-shadow:0 8px 18px rgba(30,50,80,.09)}
.nova-tz-btn.icon{width:42px;padding:10px;display:grid;place-items:center}
.nova-tz-live{display:inline-flex;align-items:center;gap:6px;margin-top:17px;padding:7px 10px;border-radius:999px;background:rgba(15,159,114,.09);color:var(--ok);font-size:11px;font-weight:750}
.nova-tz-live i{width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 0 4px rgba(15,159,114,.10)}
.nova-tz-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-top:14px}
.nova-tz-kpi{position:relative;min-height:112px;padding:17px 18px;border:1px solid var(--line);border-radius:19px;background:var(--surface);box-shadow:0 10px 30px rgba(30,50,80,.055)}
.nova-tz-kpi-top{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.055em}
.nova-tz-kpi-icon{width:31px;height:31px;display:grid;place-items:center;border-radius:10px;background:#eef8f7;color:var(--accent)}
.nova-tz.dark .nova-tz-kpi-icon{background:#15343a}
.nova-tz-kpi b{display:block;margin-top:13px;font-size:21px;line-height:1.1;letter-spacing:-.3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nova-tz-kpi small{display:block;margin-top:6px;color:var(--muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nova-tz-ok{color:var(--ok)!important}.nova-tz-bad{color:var(--bad)!important}.nova-tz-warn{color:var(--warn)!important}.nova-tz-blue{color:var(--accent2)!important}
.nova-tz-layout{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.75fr);gap:14px;margin-top:14px}
.nova-tz-panel{padding:20px;border:1px solid var(--line);border-radius:21px;background:var(--surface);box-shadow:0 10px 30px rgba(30,50,80,.05)}
.nova-tz-panel+.nova-tz-panel{margin-top:14px}
.nova-tz-panel-title{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:16px;font-weight:800}
.nova-tz-panel-sub{margin-top:5px;color:var(--muted);font-size:12px;line-height:1.5}
.nova-tz-badge{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid var(--line);border-radius:999px;background:var(--surface2);color:var(--muted);font-size:10px;font-weight:750;white-space:nowrap}
.nova-tz-actions{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:16px}
.nova-tz-action{min-height:48px;border:1px solid var(--line);border-radius:13px;padding:11px 13px;background:var(--surface2);color:var(--text);cursor:pointer;text-align:left;font-weight:700;transition:.18s ease}
.nova-tz-action:hover{border-color:#c8d6e7;transform:translateY(-1px);box-shadow:0 7px 17px rgba(30,50,80,.07)}
.nova-tz-action.primary{background:linear-gradient(135deg,#ecfffb,#eef8ff);border-color:#cceee7}
.nova-tz.dark .nova-tz-action.primary{background:#15343a;border-color:#245b61}
.nova-tz-action.danger{background:#fff5f6;border-color:#f5d9dd;color:#a63b4d}
.nova-tz.dark .nova-tz-action.danger{background:#341b25;border-color:#5a2c39}
.nova-tz-note{display:block;margin-top:12px;color:var(--muted);font-size:11px}
.nova-tz-profile{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:15px}
.nova-tz-param{padding:11px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface2)}
.nova-tz-param span{display:block;color:var(--muted);font-size:10px;font-weight:700}
.nova-tz-param strong{display:block;margin-top:4px;font:700 14px ui-monospace,SFMono-Regular,Menlo,monospace}
.nova-tz-status{margin-top:12px;padding:11px 13px;border-radius:12px;font-size:12px;font-weight:700;background:#f0fdf8;border:1px solid #d6f3e8;color:var(--ok)}
.nova-tz.dark .nova-tz-status{background:#143129;border-color:#205443}
.nova-tz-table{width:100%;border-collapse:separate;border-spacing:0;margin-top:13px;overflow:hidden}
.nova-tz-table th{padding:9px 8px;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;text-align:left;border-bottom:1px solid var(--line)}
.nova-tz-table td{padding:11px 8px;border-bottom:1px solid var(--line);font-size:12px}
.nova-tz-table tr:last-child td{border-bottom:0}
.nova-tz-table small{display:block;margin-top:2px;color:var(--muted);font-size:10px}
.nova-tz-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;background:currentColor}
.nova-tz-pre{white-space:pre-wrap;margin:13px 0 0;padding:14px;border:1px solid var(--line);border-radius:13px;background:var(--surface2);color:var(--muted);font:11px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace}
@media(max-width:1050px){.nova-tz-kpis{grid-template-columns:repeat(2,1fr)}.nova-tz-layout{grid-template-columns:1fr}}
@media(max-width:620px){.nova-tz{padding:12px 10px 30px}.nova-tz-hero{padding:21px;border-radius:22px}.nova-tz-head{align-items:flex-start;flex-direction:column}.nova-tz-title{font-size:23px}.nova-tz-head-actions{width:100%}.nova-tz-head-actions .nova-tz-btn{flex:1}.nova-tz-kpis,.nova-tz-actions{grid-template-columns:1fr}.nova-tz-profile{grid-template-columns:repeat(2,1fr)}.nova-tz-table th:nth-child(2),.nova-tz-table td:nth-child(2){display:none}}
</style>
<section class="nova-tz" id="nova-toolz">
<div class="nova-tz-shell">
  <div class="nova-tz-hero">
    <div class="nova-tz-head">
      <div>
        <div class="nova-tz-brand">
          <div class="nova-tz-logo">N</div>
          <div>
            <h2 class="nova-tz-title">NOVA AWG Toolz <span class="nova-tz-badge">2.0</span></h2>
            <div class="nova-tz-sub">AWG 3.1 • Server Control Center • диагностика и подтверждённые операции</div>
          </div>
        </div>
        <div class="nova-tz-live"><i></i><span id="tz-live">Проверка состояния…</span></div>
      </div>
      <div class="nova-tz-head-actions">
        <button class="nova-tz-btn" onclick="novaToolzaLoad()">↻ Обновить</button>
        <button class="nova-tz-btn icon" onclick="novaToolzaTheme()" title="Сменить тему">☼</button>
      </div>
    </div>
  </div>

  <div class="nova-tz-kpis">
    <div class="nova-tz-kpi"><div class="nova-tz-kpi-top"><span>AWG interface</span><span class="nova-tz-kpi-icon">◉</span></div><b id="tz-awg">—</b><small>amneziawg / awg0</small></div>
    <div class="nova-tz-kpi"><div class="nova-tz-kpi-top"><span>AWG Tools</span><span class="nova-tz-kpi-icon">⌘</span></div><b id="tz-tools">—</b><small>userspace tools</small></div>
    <div class="nova-tz-kpi"><div class="nova-tz-kpi-top"><span>UDP listener</span><span class="nova-tz-kpi-icon">↯</span></div><b id="tz-port" class="nova-tz-blue">—</b><small>ListenPort</small></div>
    <div class="nova-tz-kpi"><div class="nova-tz-kpi-top"><span>NOVA profile</span><span class="nova-tz-kpi-icon">✓</span></div><b id="tz-profile">—</b><small>canonical AWG 3.1</small></div>
  </div>

  <div class="nova-tz-layout">
    <main>
      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>⚙️ Управление сервером</span><span class="nova-tz-badge">confirmation required</span></div>
        <div class="nova-tz-panel-sub">Изменения проходят через локальный Toolz daemon. Публичного доступа к daemon нет.</div>
        <div class="nova-tz-actions">
          <button class="nova-tz-action primary" onclick="novaToolzaAction('apply-profile')">✓ &nbsp; Применить профиль<br><small>Canonical NOVA Strong Mobile</small></button>
          <button class="nova-tz-action" onclick="novaToolzaAction('repair-nat')">🔧 &nbsp; Исправить NAT<br><small>Проверка и восстановление MASQUERADE</small></button>
          <button class="nova-tz-action" onclick="novaToolzaAction('restart-awg')">↻ &nbsp; Перезапустить AWG<br><small>Перезапуск awg-quick@awg0</small></button>
          <button class="nova-tz-action danger" onclick="novaToolzaAction('repair-all')">🛠️ &nbsp; Исправить всё<br><small>Профиль + NAT + AWG</small></button>
        </div>
        <small class="nova-tz-note">Каждая изменяющая операция требует отдельного подтверждения.</small>
      </div>

      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📱 NOVA Strong Mobile</span><span class="nova-tz-badge">AWG 3.1</span></div>
        <div class="nova-tz-panel-sub">Единый canonical-профиль для сервера и клиентских конфигураций.</div>
        <div class="nova-tz-profile" id="tz-profile-grid">Загрузка…</div>
        <div class="nova-tz-status" id="tz-result">Проверяем профиль…</div>
      </div>

      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>🌐 RU Access</span><span class="nova-tz-badge">live TCP/443</span></div>
        <div class="nova-tz-panel-sub">DNS и TCP-доступность контрольных ресурсов с VPS.</div>
        <table class="nova-tz-table"><thead><tr><th>Ресурс</th><th>IPv4</th><th>DNS</th><th>TCP/443</th></tr></thead><tbody id="tz-probes"><tr><td colspan="4">Проверяем…</td></tr></tbody></table>
      </div>
    </main>

    <aside>
      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📊 Сеть</span><span class="nova-tz-badge">live</span></div>
        <div class="nova-tz-kpi" style="margin-top:13px;box-shadow:none;background:var(--surface2)">
          <div class="nova-tz-kpi-top"><span>Public IPv4</span></div><b id="tz-ip" class="tz-muted">—</b><small id="tz-route">—</small>
        </div>
        <div class="nova-tz-kpi" style="margin-top:9px;min-height:92px;box-shadow:none;background:var(--surface2)">
          <div class="nova-tz-kpi-top"><span>Forwarding</span></div><b id="tz-fwd">—</b><small>IPv4 packet forwarding</small>
        </div>
        <div class="nova-tz-kpi" style="margin-top:9px;min-height:92px;box-shadow:none;background:var(--surface2)">
          <div class="nova-tz-kpi-top"><span>NAT</span></div><b id="tz-nat">—</b><small>MASQUERADE</small>
        </div>
      </div>
      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📡 Live snapshot</span><span class="nova-tz-badge">15 sec</span></div>
        <pre class="nova-tz-pre" id="tz-details">Загрузка…</pre>
      </div>
    </aside>
  </div>
</div>
</section>
<script>
function novaToolzaTheme(){
 const el=document.getElementById('nova-toolz'); el.classList.toggle('dark');
 localStorage.setItem('nova-toolz-theme',el.classList.contains('dark')?'dark':'light');
}
(function(){const el=document.getElementById('nova-toolz');if(localStorage.getItem('nova-toolz-theme')==='dark')el.classList.add('dark')})();
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
  document.getElementById('tz-live').textContent=d.awg_state.up?'Система онлайн • обновлено сейчас':'Требуется внимание';
  document.getElementById('tz-live').parentElement.className='nova-tz-live '+(d.awg_state.up?'':'nova-tz-bad');
  document.getElementById('tz-awg').textContent=d.awg_state.up?'ONLINE':'OFFLINE'; document.getElementById('tz-awg').className=cls(d.awg_state.up);
  document.getElementById('tz-tools').textContent=d.awg.tools;
  document.getElementById('tz-port').textContent=d.listen_port||'—';
  document.getElementById('tz-profile').textContent=d.profile_ok?'PASS':'CHECK'; document.getElementById('tz-profile').className=cls(d.profile_ok);
  document.getElementById('tz-ip').textContent=d.network.public_ipv4; document.getElementById('tz-route').textContent=d.network.default_route;
  document.getElementById('tz-fwd').textContent=d.network.forwarding?'ON':'OFF'; document.getElementById('tz-fwd').className=cls(d.network.forwarding);
  document.getElementById('tz-nat').textContent=d.network.nat?'FOUND':'MISSING'; document.getElementById('tz-nat').className=cls(d.network.nat);
  document.getElementById('tz-profile-grid').innerHTML=Object.entries(d.expected_profile).map(x=>'<div class="nova-tz-param"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');
  const bad=Object.entries(d.mismatches||{}).map(x=>x[0]+': expected '+x[1].expected+', actual '+x[1].actual);
  document.getElementById('tz-result').className='nova-tz-status '+(d.profile_ok?'nova-tz-ok':'nova-tz-bad');
  document.getElementById('tz-result').textContent=d.profile_ok?'✓ Canonical profile совпадает':'⚠ '+bad.join(' · ');
  document.getElementById('tz-probes').innerHTML=(d.probes||[]).map(p=>'<tr><td><strong>'+p.name+'</strong><small>'+p.host+'</small></td><td>'+((p.ipv4||[]).join(', ')||'—')+'</td><td class="'+cls(p.dns_ok)+'"><span class="nova-tz-dot"></span>'+(p.dns_ok?'OK':'FAIL')+'</td><td class="'+cls(p.tcp_ok)+'"><span class="nova-tz-dot"></span>'+(p.tcp_ok?'OPEN':'FAIL')+'</td></tr>').join('');
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
