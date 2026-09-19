"""NOVA AWG Toolz 2.0 — unified, read-only AWG/network operations dashboard.

The dashboard is intentionally non-destructive: it reads AWG, routing, firewall/NAT,
DNS and a small set of connectivity probes. It never writes awg0.conf, firewall
rules, routes or service state.
"""
from __future__ import annotations
import re
import socket
import subprocess
import shutil
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

def _external_toolza():
    path = "/usr/local/bin/awg2"
    installed = bool(shutil.which("awg2"))
    version = ""
    if installed:
        try:
            p = subprocess.run([path, "--help"], capture_output=True, text=True, timeout=4)
            if p.returncode == 0:
                version = next((x.strip() for x in p.stdout.splitlines() if x.startswith("awg2 ")), "")
        except Exception:
            pass
    return {
        "installed": installed,
        "path": path if installed else None,
        "version": version,
        "expected_version": "v0.8.25",
        "pinned_commit": "ecccafa3094181a6962ff71e54527e4771657698",
        "repository": "https://github.com/pumbaX/awg-multi-script",
    }

def _live_snapshot():
    """Return safe live telemetry without exposing AWG secrets."""
    try:
        import nova12_diagnostics
        d = nova12_diagnostics.diagnose()
    except Exception as exc:
        return {
            "online_peers": 0, "peer_count": 0, "rx": 0, "tx": 0,
            "last_handshake": 0, "mobile_ready": False,
            "awg_service": False, "panel_service": False,
            "uptime": "unknown", "error": str(exc),
        }

    peers = d.get("peers") or []
    online = [p for p in peers if p.get("online")]
    rx = sum(int(p.get("rx") or 0) for p in peers)
    tx = sum(int(p.get("tx") or 0) for p in peers)
    last_handshake = max((int(p.get("handshake") or 0) for p in peers), default=0)

    def active(unit):
        try:
            return subprocess.run(
                ["systemctl", "is-active", "--quiet", unit],
                timeout=2,
            ).returncode == 0
        except Exception:
            return False

    uptime = _run("uptime", "-p") or "unknown"
    mobile_ready = bool(
        d.get("profile_ok")
        and d.get("port")
        and d.get("online_peers", 0) >= 0
    )

    return {
        "online_peers": len(online),
        "peer_count": len(peers),
        "rx": rx,
        "tx": tx,
        "last_handshake": last_handshake,
        "mobile_ready": mobile_ready,
        "awg_service": active("awg-quick@awg0.service"),
        "panel_service": active("awgpanel.service"),
        "toolz_service": active("awg-toolz.service"),
        "uptime": uptime,
        "error": "",
    }


def snapshot():
    cfg = _config()
    mismatches = {k: {"expected": v, "actual": cfg.get(k)}
                  for k, v in PARAMS.items() if cfg.get(k) != v}
    return {
        "mode": "read-only",
        "external_toolza_control": "blocked",
        "external_toolza_note": "NOVA only inspects /usr/local/bin/awg2; web requests never execute external Toolza.",
        "external_toolza": _external_toolza(),
        "daemon": _daemon(),
        "live": _live_snapshot(),
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
.nova-tz{--bg:#f6f8fc;--surface:#fff;--surface2:#f8fafc;--text:#142033;--muted:#708097;--line:#e5eaf1;--accent:#10b981;--blue:#3b82f6;--bad:#e05268;--warn:#c58b18;max-width:1320px;margin:0 auto;padding:22px 20px 42px;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.nova-tz *{box-sizing:border-box}.nova-tz.dark{--bg:#0b1220;--surface:#111a2b;--surface2:#172235;--text:#edf4ff;--muted:#91a0b6;--line:#26364d}
.nova-tz-shell{background:var(--bg);border-radius:28px;padding:4px}.nova-tz-hero{position:relative;overflow:hidden;padding:25px 27px;border:1px solid var(--line);border-radius:25px;background:linear-gradient(135deg,#fff 0%,#effbf8 54%,#eef5ff 100%);box-shadow:0 16px 48px rgba(30,50,80,.08)}
.nova-tz.dark .nova-tz-hero{background:linear-gradient(135deg,#101a2b,#13283a 55%,#14243b)}.nova-tz-hero:before{content:"";position:absolute;width:300px;height:300px;right:-110px;top:-190px;border-radius:50%;background:rgba(16,185,129,.13);filter:blur(5px)}
.nova-tz-head{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:18px}.nova-tz-brand{display:flex;align-items:center;gap:14px}.nova-tz-logo{width:52px;height:52px;display:grid;place-items:center;border-radius:16px;background:linear-gradient(135deg,#10b981,#3b82f6);color:#fff;font-size:24px;font-weight:850;box-shadow:0 10px 25px rgba(16,185,129,.2)}
.nova-tz-title{margin:0;font-size:28px;line-height:1.1;letter-spacing:-.7px;font-weight:850}.nova-tz-sub{margin-top:7px;color:var(--muted);font-size:13px}.nova-tz-actions-top{display:flex;gap:8px}
.nova-tz-btn{border:1px solid var(--line);border-radius:12px;padding:10px 13px;background:var(--surface);color:var(--text);cursor:pointer;font-weight:700;box-shadow:0 4px 12px rgba(30,50,80,.04);transition:.18s}.nova-tz-btn:hover{transform:translateY(-1px);box-shadow:0 8px 18px rgba(30,50,80,.09)}
.nova-tz-livebar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:18px;padding-top:15px;border-top:1px solid rgba(120,145,175,.18);font-size:12px}.nova-tz-live{display:inline-flex;align-items:center;gap:7px;color:var(--accent);font-weight:750}.nova-tz-live i{width:8px;height:8px;border-radius:50%;background:currentColor;box-shadow:0 0 0 4px rgba(16,185,129,.11)}
.nova-tz-sync{color:var(--muted)}.nova-tz-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:13px}.nova-tz-kpi{min-height:108px;padding:16px 17px;border:1px solid var(--line);border-radius:18px;background:var(--surface);box-shadow:0 9px 27px rgba(30,50,80,.05)}
.nova-tz-kpi-top{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.nova-tz-kpi-icon{width:30px;height:30px;display:grid;place-items:center;border-radius:9px;background:#eef8f6;color:var(--accent)}.nova-tz.dark .nova-tz-kpi-icon{background:#15343a}
.nova-tz-kpi b{display:block;margin-top:12px;font-size:20px;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nova-tz-kpi small{display:block;margin-top:6px;color:var(--muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nova-tz-ok{color:var(--accent)!important}.nova-tz-bad{color:var(--bad)!important}.nova-tz-warn{color:var(--warn)!important}.nova-tz-blue{color:var(--blue)!important}
.nova-tz-layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,.72fr);gap:13px;margin-top:13px}.nova-tz-panel{padding:19px;border:1px solid var(--line);border-radius:19px;background:var(--surface);box-shadow:0 9px 27px rgba(30,50,80,.045)}.nova-tz-panel+.nova-tz-panel{margin-top:13px}
.nova-tz-panel-title{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:15px;font-weight:850}.nova-tz-panel-sub{margin-top:5px;color:var(--muted);font-size:11px;line-height:1.5}.nova-tz-badge{display:inline-flex;align-items:center;padding:5px 9px;border:1px solid var(--line);border-radius:999px;background:var(--surface2);color:var(--muted);font-size:10px;font-weight:800;white-space:nowrap}
.nova-tz-action-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:15px}.nova-tz-action{min-height:52px;border:1px solid var(--line);border-radius:13px;padding:10px 12px;background:var(--surface2);color:var(--text);cursor:pointer;text-align:left;font-weight:750;transition:.18s}.nova-tz-action:hover{transform:translateY(-1px);box-shadow:0 7px 17px rgba(30,50,80,.07)}.nova-tz-action small{display:block;margin-top:4px;color:var(--muted);font-weight:500;font-size:10px}.nova-tz-action.primary{background:linear-gradient(135deg,#ecfffa,#eef8ff);border-color:#ccefe5}.nova-tz.dark .nova-tz-action.primary{background:#15343a;border-color:#245b61}.nova-tz-action.danger{background:#fff5f6;border-color:#f2d6dc;color:#a43b4d}.nova-tz.dark .nova-tz-action.danger{background:#341b25;border-color:#5a2c39}
.nova-tz-note{display:block;margin-top:10px;color:var(--muted);font-size:10px}.nova-tz-profile{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.nova-tz-param{padding:10px 11px;border:1px solid var(--line);border-radius:11px;background:var(--surface2)}.nova-tz-param span{display:block;color:var(--muted);font-size:9px;font-weight:800}.nova-tz-param strong{display:block;margin-top:4px;font:750 13px ui-monospace,SFMono-Regular,Menlo,monospace}
.nova-tz-status{display:flex;align-items:center;gap:8px;margin-top:11px;padding:11px 12px;border-radius:11px;background:#effcf7;border:1px solid #d3f3e7;color:var(--accent);font-size:11px;font-weight:750}.nova-tz.dark .nova-tz-status{background:#143129;border-color:#205443}
.nova-tz-mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.nova-tz-mini{padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--surface2)}.nova-tz-mini label{display:block;color:var(--muted);font-size:9px;font-weight:800;text-transform:uppercase}.nova-tz-mini b{display:block;margin-top:6px;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nova-tz-mini small{display:block;margin-top:3px;color:var(--muted);font-size:9px}
.nova-tz-table{width:100%;border-collapse:separate;border-spacing:0;margin-top:11px}.nova-tz-table th{padding:8px;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.06em;text-align:left;border-bottom:1px solid var(--line)}.nova-tz-table td{padding:10px 8px;border-bottom:1px solid var(--line);font-size:11px}.nova-tz-table tr:last-child td{border-bottom:0}.nova-tz-table small{display:block;margin-top:2px;color:var(--muted);font-size:9px}.nova-tz-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:5px;background:currentColor}
.nova-tz-pre{white-space:pre-wrap;margin:11px 0 0;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--surface2);color:var(--muted);font:10px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace}
.nova-tz-collapse{margin-top:12px}.nova-tz-collapse summary{cursor:pointer;color:var(--muted);font-size:11px;font-weight:750}.nova-tz-copy{border:0;background:none;color:var(--blue);cursor:pointer;font-size:10px;margin-left:5px}
@media(max-width:1040px){.nova-tz-kpis{grid-template-columns:repeat(2,1fr)}.nova-tz-layout{grid-template-columns:1fr}}
@media(max-width:620px){.nova-tz{padding:12px 9px 30px}.nova-tz-hero{padding:20px}.nova-tz-head{align-items:flex-start;flex-direction:column}.nova-tz-title{font-size:23px}.nova-tz-actions-top{width:100%}.nova-tz-actions-top .nova-tz-btn{flex:1}.nova-tz-kpis,.nova-tz-action-grid{grid-template-columns:1fr}.nova-tz-profile{grid-template-columns:repeat(2,1fr)}.nova-tz-livebar{align-items:flex-start;flex-direction:column}.nova-tz-table th:nth-child(2),.nova-tz-table td:nth-child(2){display:none}}
</style>
<section class="nova-tz" id="nova-toolz">
<div class="nova-tz-shell">
  <div class="nova-tz-hero">
    <div class="nova-tz-head">
      <div class="nova-tz-brand"><div class="nova-tz-logo">N</div><div><h2 class="nova-tz-title">NOVA AWG Toolz <span class="nova-tz-badge">2.0</span></h2><div class="nova-tz-sub">AWG 3.1 • Server Control Center • диагностика и подтверждённые операции</div></div></div>
      <div class="nova-tz-actions-top"><button class="nova-tz-btn" onclick="novaToolzaLoad()">↻ Обновить</button><button class="nova-tz-btn" onclick="novaToolzaTheme()" title="Сменить тему">☼ / ☾</button></div>
    </div>
    <div class="nova-tz-livebar"><div class="nova-tz-live"><i></i><span id="tz-live">Проверка состояния…</span></div><div class="nova-tz-sync">Автообновление: 15 сек • <span id="tz-clock">—</span></div></div>
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
        <div class="nova-tz-panel-sub">Изменяющие операции выполняются только NOVA Toolz daemon на 127.0.0.1:9090. Внешний /usr/local/bin/awg2 из веб-панели не запускается.</div>
        <div class="nova-tz-action-grid">
          <button class="nova-tz-action primary" onclick="novaToolzaAction('apply-profile')">✓ &nbsp; Применить профиль<small>Canonical NOVA Strong Mobile</small></button>
          <button class="nova-tz-action" onclick="novaToolzaAction('repair-nat')">🔧 &nbsp; Исправить NAT<small>Проверка MASQUERADE</small></button>
          <button class="nova-tz-action" onclick="novaToolzaAction('restart-awg')">↻ &nbsp; Перезапустить AWG<small>awg-quick@awg0</small></button>
          <button class="nova-tz-action danger" onclick="novaToolzaAction('repair-all')">🛠️ &nbsp; Исправить всё<small>Профиль + NAT + AWG</small></button>
        </div>
        <small class="nova-tz-note">Перед каждой операцией появится подтверждение.</small>
      </div>

      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>🧩 AWG Toolza</span><span class="nova-tz-badge">external CLI</span></div>
        <div class="nova-tz-panel-sub">Совместимость с внешним AWG Toolza. NOVA показывает только наличие и версию /usr/local/bin/awg2. Запуск внешнего Toolza из веб-интерфейса запрещён; awg0 остаётся под контролем NOVA.</div>
        <div class="nova-tz-mini-grid">
          <div class="nova-tz-mini"><label>Статус</label><b id="tz-external">Проверяем…</b><small id="tz-external-version">—</small></div>
          <div class="nova-tz-mini"><label>Версия</label><b>v0.8.25</b><small>pinned upstream</small></div>
        </div>
        <div class="nova-tz-status" id="tz-external-note">Проверяем наличие /usr/local/bin/awg2…</div>
        <div style="margin-top:11px"><a class="nova-tz-btn" href="https://github.com/pumbaX/awg-multi-script" target="_blank" rel="noopener">Открыть AWG Toolza ↗</a></div>
      </div>

      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📱 NOVA Strong Mobile</span><span class="nova-tz-badge">AWG 3.1</span></div>
        <div class="nova-tz-panel-sub">Одинаковый canonical-профиль для сервера и генератора клиентских конфигураций.</div>
        <div class="nova-tz-profile" id="tz-profile-grid">Загрузка…</div>
        <div class="nova-tz-status" id="tz-result">Проверяем профиль…</div>
      </div>

      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>🌐 RU Access</span><span class="nova-tz-badge">live TCP/443</span></div>
        <div class="nova-tz-panel-sub">Контроль DNS и TCP-доступности ресурсов непосредственно с VPS.</div>
        <table class="nova-tz-table"><thead><tr><th>Ресурс</th><th>IPv4</th><th>DNS</th><th>TCP/443</th></tr></thead><tbody id="tz-probes"><tr><td colspan="4">Проверяем…</td></tr></tbody></table>
      </div>
    </main>

    <aside>
      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📊 Сеть</span><span class="nova-tz-badge">live</span></div>
        <div class="nova-tz-mini-grid">
          <div class="nova-tz-mini"><label>Public IPv4</label><b id="tz-ip">—</b><small><button class="nova-tz-copy" onclick="novaCopy('tz-ip')">копировать</button></small></div>
          <div class="nova-tz-mini"><label>ListenPort</label><b id="tz-port-mini">—</b><small>UDP</small></div>
          <div class="nova-tz-mini"><label>Forwarding</label><b id="tz-fwd">—</b><small>IPv4 packet forwarding</small></div>
          <div class="nova-tz-mini"><label>NAT</label><b id="tz-nat">—</b><small>MASQUERADE</small></div>
          <div class="nova-tz-mini" style="grid-column:1/-1"><label>Default route</label><b id="tz-route">—</b></div>
        </div>
      </div>
      <div class="nova-tz-panel">
        <div class="nova-tz-panel-title"><span>📡 Live snapshot</span><span class="nova-tz-badge">15 sec</span></div>
        <div class="nova-tz-mini-grid">
          <div class="nova-tz-mini"><label>Клиенты</label><b id="tz-clients">—</b><small id="tz-clients-sub">—</small></div>
          <div class="nova-tz-mini"><label>Последний handshake</label><b id="tz-handshake">—</b><small>максимальный среди peer</small></div>
          <div class="nova-tz-mini"><label>RX / TX</label><b id="tz-traffic">—</b><small>суммарный трафик peer</small></div>
          <div class="nova-tz-mini"><label>Mobile Ready</label><b id="tz-mobile-ready">—</b><small>профиль + сеть</small></div>
          <div class="nova-tz-mini"><label>AWG service</label><b id="tz-awg-service">—</b><small>awg-quick@awg0</small></div>
          <div class="nova-tz-mini"><label>Panel / Toolz</label><b id="tz-services">—</b><small>systemd</small></div>
          <div class="nova-tz-mini" style="grid-column:1/-1"><label>Uptime</label><b id="tz-uptime">—</b></div>
        </div>
        <details class="nova-tz-collapse"><summary>Показать технические данные</summary><pre class="nova-tz-pre" id="tz-details">Загрузка…</pre></details>
      </div>
    </aside>
  </div>
</div>
</section>
<script>
function novaToolzaTheme(){const el=document.getElementById('nova-toolz');el.classList.toggle('dark');localStorage.setItem('nova-toolz-theme',el.classList.contains('dark')?'dark':'light')}
(function(){const el=document.getElementById('nova-toolz');if(localStorage.getItem('nova-toolz-theme')==='dark')el.classList.add('dark')})();
function novaCopy(id){const t=document.getElementById(id).textContent;if(navigator.clipboard)navigator.clipboard.writeText(t).then(()=>{});}
function novaClock(){const e=document.getElementById('tz-clock');if(e)e.textContent=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});}
async function novaToolzaAction(action){
 const labels={'apply-profile':'применить профиль NOVA','repair-nat':'исправить NAT','restart-awg':'перезапустить AWG','repair-all':'выполнить полное исправление'};
 if(!confirm('Подтвердить: '+(labels[action]||action)+'?'))return;
 try{const r=await fetch('/api/nova/toolza-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});const d=await r.json();alert(d.ok?'Операция выполнена: '+action:'Ошибка: '+(d.error||'см. результат'));novaToolzaLoad()}catch(e){alert('Ошибка Toolz: '+e)}
}
async function novaToolzaLoad(){
 try{
  const r=await fetch('/api/nova/toolza-center',{cache:'no-store'}),d=await r.json(),cls=ok=>ok?'nova-tz-ok':'nova-tz-bad';
  document.getElementById('tz-live').textContent=d.awg_state.up?'Система онлайн':'Требуется внимание';
  document.getElementById('tz-awg').textContent=d.awg_state.up?'ONLINE':'OFFLINE';document.getElementById('tz-awg').className=cls(d.awg_state.up);
  document.getElementById('tz-tools').textContent=d.awg.tools;document.getElementById('tz-port').textContent=d.listen_port||'—';document.getElementById('tz-port-mini').textContent=d.listen_port||'—';
  document.getElementById('tz-profile').textContent=d.profile_ok?'PASS':'CHECK';document.getElementById('tz-profile').className=cls(d.profile_ok);
  document.getElementById('tz-ip').textContent=d.network.public_ipv4;document.getElementById('tz-route').textContent=d.network.default_route;
  document.getElementById('tz-fwd').textContent=d.network.forwarding?'ON':'OFF';document.getElementById('tz-fwd').className=cls(d.network.forwarding);
  document.getElementById('tz-nat').textContent=d.network.nat?'FOUND':'MISSING';document.getElementById('tz-nat').className=cls(d.network.nat);
  const live=d.live||{};
  const fmtBytes=n=>{n=Number(n||0);const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++;}return n.toFixed(n>=10?0:1)+' '+u[i]};
  const ago=ts=>{ts=Number(ts||0);if(!ts)return '—';const s=Math.max(0,Math.floor(Date.now()/1000-ts));return s<60?s+' сек. назад':s<3600?Math.floor(s/60)+' мин. назад':Math.floor(s/3600)+' ч. назад'};
  document.getElementById('tz-clients').textContent=(live.online_peers||0)+' / '+(live.peer_count||0);
  document.getElementById('tz-clients').className=(live.online_peers||0)>0?'nova-tz-ok':'';
  document.getElementById('tz-clients-sub').textContent=(live.online_peers||0)>0?'ONLINE':'активных сейчас нет';
  document.getElementById('tz-handshake').textContent=ago(live.last_handshake);
  document.getElementById('tz-traffic').textContent=fmtBytes(live.rx)+' / '+fmtBytes(live.tx);
  document.getElementById('tz-mobile-ready').textContent=live.mobile_ready?'READY':'CHECK';
  document.getElementById('tz-mobile-ready').className=live.mobile_ready?'nova-tz-ok':'nova-tz-warn';
  document.getElementById('tz-awg-service').textContent=live.awg_service?'ACTIVE':'DOWN';
  document.getElementById('tz-awg-service').className=live.awg_service?'nova-tz-ok':'nova-tz-bad';
  document.getElementById('tz-services').textContent=(live.panel_service?'PANEL ✓':'PANEL ✕')+' / '+(live.toolz_service?'TOOLZ ✓':'TOOLZ ✕');
  document.getElementById('tz-services').className=(live.panel_service&&live.toolz_service)?'nova-tz-ok':'nova-tz-bad';
  document.getElementById('tz-uptime').textContent=live.uptime||'unknown';
  document.getElementById('tz-profile-grid').innerHTML=Object.entries(d.expected_profile).map(x=>'<div class="nova-tz-param"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join('');
  const ext=d.external_toolza||{};
  document.getElementById('tz-external').textContent=ext.installed?'INSTALLED':'NOT INSTALLED';
  document.getElementById('tz-external').className=cls(ext.installed);
  document.getElementById('tz-external-version').textContent=ext.version||'Команда awg2 не найдена';
  document.getElementById('tz-external-note').textContent=ext.installed?'✓ AWG Toolza обнаружен. Только чтение: запуск из веб-панели заблокирован.':'ℹ️ Установить можно через /opt/awg31-panel/install-awg-toolza.sh';
  const bad=Object.entries(d.mismatches||{}).map(x=>x[0]+': expected '+x[1].expected+', actual '+x[1].actual);
  document.getElementById('tz-result').className='nova-tz-status '+(d.profile_ok?'nova-tz-ok':'nova-tz-bad');document.getElementById('tz-result').innerHTML=d.profile_ok?'✓ Canonical profile совпадает':'⚠ '+bad.join(' · ');
  document.getElementById('tz-probes').innerHTML=(d.probes||[]).map(p=>'<tr><td><strong>'+p.name+'</strong><small>'+p.host+'</small></td><td>'+((p.ipv4||[]).join(', ')||'—')+'</td><td class="'+cls(p.dns_ok)+'"><span class="nova-tz-dot"></span>'+(p.dns_ok?'OK':'FAIL')+'</td><td class="'+cls(p.tcp_ok)+'"><span class="nova-tz-dot"></span>'+(p.tcp_ok?'OPEN':'FAIL')+'</td></tr>').join('');
  document.getElementById('tz-details').textContent=['AWG tools: '+d.awg.tools,'Kernel module: '+d.awg.loaded_module,'AWG0: '+(d.awg_state.up?'ONLINE':'OFFLINE'),'UDP ports: '+(d.udp_ports||[]).join(', '),'ListenPort: '+(d.listen_port||'—'),'Public IPv4: '+d.network.public_ipv4,'Default route: '+d.network.default_route,'Forwarding: '+d.network.forwarding,'NAT: '+d.network.nat,'DNS: '+(d.network.dns||[]).join(' | '),'Clients: '+(live.online_peers||0)+'/'+(live.peer_count||0),'RX/TX: '+fmtBytes(live.rx)+' / '+fmtBytes(live.tx),'Last handshake: '+ago(live.last_handshake),'Mobile Ready: '+live.mobile_ready,'Services: AWG='+(live.awg_service?'active':'down')+', Panel='+(live.panel_service?'active':'down')+', Toolz='+(live.toolz_service?'active':'down'),'Uptime: '+(live.uptime||'unknown')].join('\\n');
  novaClock();
 }catch(e){document.getElementById('tz-details').textContent='Ошибка проверки: '+e}
}
novaToolzaLoad();setInterval(novaToolzaLoad,15000);setInterval(novaClock,1000);novaClock();
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
