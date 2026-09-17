#!/usr/bin/env python3
"""NOVA 12.0: structured mobile/AWG diagnostics.

Read-only diagnostics layer. It never edits awg0.conf, restarts services, or
changes firewall state. The existing AWG 3.1 profile remains the source of
truth via nova_awg31_fix.PARAMS.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from flask import jsonify, render_template_string

EXPECTED_KEYS = (
    "Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4",
    "H1", "H2", "H3", "H4", "RandomTrailers",
)
SECRET_KEYS = {
    "PrivateKey", "PresharedKey", "HeaderProtectionKey",
    "private_key", "psk", "privateKey", "secret",
}


def run(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args, text=True, capture_output=True, timeout=8,
            check=False,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def read_cfg() -> dict[str, str]:
    try:
        import app
        return dict(app.cfg())
    except Exception:
        return {}


def safe_config(config: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in config.items() if k not in SECRET_KEYS}


def profile_check(config: dict[str, str]) -> dict[str, Any]:
    try:
        import nova_awg31_fix
        expected = nova_awg31_fix.PARAMS
    except Exception:
        expected = {
            "Jc": "4", "Jmin": "40", "Jmax": "120",
            "S1": "16", "S2": "16", "S3": "16", "S4": "16",
            "H1": "1", "H2": "2", "H3": "3", "H4": "4",
            "RandomTrailers": "on",
        }
    missing = [k for k in EXPECTED_KEYS if not config.get(k)]
    wrong = [k for k in EXPECTED_KEYS if config.get(k) and str(config[k]) != str(expected[k])]
    return {"ok": not missing and not wrong, "missing": missing, "wrong": wrong}


def recent_peers() -> list[dict[str, Any]]:
    rc, out = run("awg", "show", "awg0", "dump")
    if rc != 0:
        return []
    rows: list[dict[str, Any]] = []
    now = int(time.time())
    lines = out.splitlines()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        try:
            hs = int(parts[4] or 0)
            rx = int(parts[5] or 0)
            tx = int(parts[6] or 0)
        except ValueError:
            hs, rx, tx = 0, 0, 0
        rows.append({
            "endpoint": parts[2] or "—",
            "handshake": hs,
            "rx": rx,
            "tx": tx,
            "online": bool(hs and now - hs <= 180),
        })
    return rows


def _check(name: str, ok: bool, detail: str, hint: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail or "OK", "hint": hint}


def diagnose() -> dict[str, Any]:
    config = read_cfg()
    profile = profile_check(config)
    port = config.get("ListenPort", "1234")
    mtu = config.get("MTU", "1280")

    rc, out = run("systemctl", "is-active", "--quiet", "awg-quick@awg0")
    service_ok = rc == 0

    rc, iface = run("ip", "link", "show", "awg0")
    iface_ok = rc == 0 and "UP" in iface

    rc, forwarding = run("sysctl", "-n", "net.ipv4.ip_forward")
    forwarding_ok = rc == 0 and forwarding.strip() == "1"

    rc, sockets = run("ss", "-lun")
    udp_ok = rc == 0 and any(
        line.strip().endswith(f":{port}") or f"0.0.0.0:{port}" in line or f"[::]:{port}" in line
        for line in sockets.splitlines()
    )

    rc, dns = run("getent", "hosts", "example.com")
    dns_ok = rc == 0

    peers = recent_peers()
    online = sum(1 for peer in peers if peer["online"])

    checks = [
        _check("AWG service", service_ok, "awg-quick@awg0 active" if service_ok else "awg-quick@awg0 inactive", "Проверь статус AWG."),
        _check("AWG interface", iface_ok, "awg0 UP" if iface_ok else iface or "awg0 not available", "Проверь интерфейс awg0."),
        _check("UDP listener", udp_ok, f"UDP {port} is listening" if udp_ok else f"UDP {port} is not listening", "Проверь ListenPort и firewall."),
        _check("IPv4 forwarding", forwarding_ok, "net.ipv4.ip_forward = 1" if forwarding_ok else forwarding, "Включи IPv4 forwarding."),
        _check("AWG 3.1 profile", profile["ok"], "J/S/H parameters match NOVA profile" if profile["ok"] else "wrong: " + ", ".join(profile["wrong"]) + "; missing: " + ", ".join(profile["missing"]), "Запусти проверку профиля NOVA AWG 3.1."),
        _check("Server DNS", dns_ok, dns or "DNS resolution failed", "Проверь DNS на VPS."),
        _check("Recent handshake", online > 0 if peers else True, f"{online} online of {len(peers)} peer(s)", "Подключи клиента и проверь Endpoint/порт."),
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "port": str(port),
        "mtu": str(mtu),
        "profile_ok": profile["ok"],
        "profile": profile,
        "peers": peers,
        "online_peers": online,
        "peer_count": len(peers),
        "config": safe_config(config),
        "checks": checks,
        "timestamp": int(time.time()),
    }


PAGE = '''
<div class="hero">
  <div><div class="eyebrow">NOVA 12 · MOBILE HEALTH</div>
  <h1>Мобильная диагностика</h1>
  <p>Проверка AWG, UDP, handshake, forwarding, DNS и профиля Strong Mobile.</p></div>
  <a class="btn" href="/mobile-diagnostics">↻ Проверить снова</a>
</div>
<div class="card">
  <div class="toolbar"><h2>Состояние</h2>
  <span class="badge {{ 'on' if data.ok else 'warn' }}">{{ 'ВСЁ OK' if data.ok else 'ТРЕБУЕТ ВНИМАНИЯ' }}</span></div>
  <div class="grid4">
    <div class="card metric"><div class="label">AWG</div><div class="value {{ 'ok' if data.checks[0].ok else 'bad' }}">{{ 'ONLINE' if data.checks[0].ok else 'OFFLINE' }}</div></div>
    <div class="card metric"><div class="label">UDP</div><div class="value">{{ data.port }}</div><div class="sub">MTU {{ data.mtu }}</div></div>
    <div class="card metric"><div class="label">Peers online</div><div class="value ok">{{ data.online_peers }}</div><div class="sub">из {{ data.peer_count }}</div></div>
    <div class="card metric"><div class="label">Strong Mobile</div><div class="value {{ 'ok' if data.profile_ok else 'bad' }}">{{ 'OK' if data.profile_ok else 'CHECK' }}</div></div>
  </div>
  {% for x in data.checks %}
  <div class="notice {{ 'good' if x.ok else 'badbox' }}"><b>{{ '✓' if x.ok else '✕' }} {{ x.name }}</b><div style="margin-top:5px">{{ x.detail }}</div>{% if not x.ok %}<div class="muted" style="margin-top:5px">{{ x.hint }}</div>{% endif %}</div>
  {% endfor %}
</div>
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Подключения</h2><span class="muted">handshake ≤ 180 сек. = ONLINE</span></div>
<div class="table-wrap"><table><tr><th>Endpoint</th><th>Статус</th><th>Handshake</th><th>RX</th><th>TX</th></tr>
{% for p in data.peers %}<tr><td>{{ p.endpoint }}</td><td><span class="badge {{ 'on' if p.online else 'off' }}">{{ 'ONLINE' if p.online else 'OFFLINE' }}</span></td><td>{{ p.handshake }}</td><td>{{ p.rx }}</td><td>{{ p.tx }}</td></tr>{% else %}<tr><td colspan="5" class="muted">Peers не найдены.</td></tr>{% endfor %}
</table></div></div>
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Что проверить на мобильном клиенте</h2></div>
<div class="notice">1. Endpoint должен использовать текущий UDP-порт <b>{{ data.port }}</b>.</div>
<div class="notice">2. При попытке подключения здесь должен появиться свежий <b>handshake</b>.</div>
<div class="notice">3. Если handshake отсутствует, проверь мобильную сеть, Endpoint, UDP-порт и firewall. Приватные ключи в диагностику не передавай.</div>
</div>
'''


def apply(nova11: Any) -> bool:
    app = nova11.core.app

    def page():
        return nova11.core.layout(
            "Мобильная диагностика",
            render_template_string(PAGE, data=diagnose()),
            "/mobile-diagnostics",
        )

    def api():
        return jsonify(diagnose())

    # Replace existing handlers instead of adding duplicate Flask rules.
    app.view_functions["mobile_diagnostics"] = page
    app.view_functions["mobile_diagnostics_api"] = api
    return True
