#!/usr/bin/env python3
"""NOVA 12: read-only Mobile Diagnostics 3.0.

Adds network-path visibility without changing AWG, firewall, or routing state.
Private keys and other secrets are never returned.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from flask import jsonify, render_template_string

SECRET_WORDS = ("private", "preshared", "headerprotection", "secret", "token", "password")


def run(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=6, check=False)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def safe_config(config: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in config.items() if not any(w in k.lower() for w in SECRET_WORDS)}


def public_ip() -> str:
    rc, out = run("curl", "-4", "-fsS", "--max-time", "4", "https://api.ipify.org")
    return out if rc == 0 and out else "—"


def default_route() -> tuple[str, str]:
    rc, out = run("ip", "-4", "route", "show", "default")
    if rc != 0 or not out:
        return "—", "—"
    parts = out.split()
    gateway = parts[2] if len(parts) > 2 and parts[1] == "via" else "—"
    iface = parts[parts.index("dev") + 1] if "dev" in parts else "—"
    return gateway, iface


def udp_listener(port: str) -> bool:
    rc, out = run("ss", "-lun")
    if rc != 0:
        return False
    return any(f":{port}" in line for line in out.splitlines())


def forwarding() -> bool:
    rc, out = run("sysctl", "-n", "net.ipv4.ip_forward")
    return rc == 0 and out.strip() == "1"


def nat_detected() -> bool:
    rc, out = run("iptables", "-t", "nat", "-S")
    if rc == 0 and "MASQUERADE" in out.upper():
        return True
    rc, out = run("nft", "list", "ruleset")
    return rc == 0 and "masquerade" in out.lower()


def diagnose() -> dict[str, Any]:
    try:
        import app
        cfg = dict(app.cfg())
    except Exception:
        cfg = {}
    port = str(cfg.get("ListenPort", "1234"))
    gateway, iface = default_route()
    checks = [
        {"name": "Public IPv4", "ok": public_ip() != "—", "detail": public_ip()},
        {"name": "Default route", "ok": iface != "—", "detail": f"{gateway} via {iface}"},
        {"name": "UDP listener", "ok": udp_listener(port), "detail": f"UDP {port}" if udp_listener(port) else f"UDP {port} not listening"},
        {"name": "IPv4 forwarding", "ok": forwarding(), "detail": "enabled" if forwarding() else "disabled"},
        {"name": "NAT", "ok": nat_detected(), "detail": "MASQUERADE detected" if nat_detected() else "MASQUERADE not detected"},
    ]
    return {
        "ok": all(x["ok"] for x in checks),
        "port": port,
        "public_ipv4": checks[0]["detail"],
        "gateway": gateway,
        "interface": iface,
        "config": safe_config(cfg),
        "checks": checks,
        "timestamp": int(time.time()),
    }


PAGE = '''
<div class="hero"><div><div class="eyebrow">NOVA 12 · MOBILE DIAGNOSTICS 3.0</div>
<h1>Путь мобильного подключения</h1><p>Read-only проверка публичного IP, маршрута, UDP, forwarding и NAT.</p></div>
<a class="btn" href="/mobile-diagnostics-v3">↻ Проверить снова</a></div>
<div class="card"><div class="grid4">
<div class="card metric"><div class="label">Public IPv4</div><div class="value blue">{{ data.public_ipv4 }}</div></div>
<div class="card metric"><div class="label">UDP</div><div class="value {{ 'ok' if data.checks[2].ok else 'bad' }}">{{ data.port }}</div></div>
<div class="card metric"><div class="label">Interface</div><div class="value">{{ data.interface }}</div></div>
<div class="card metric"><div class="label">NAT</div><div class="value {{ 'ok' if data.checks[4].ok else 'bad' }}">{{ 'OK' if data.checks[4].ok else 'CHECK' }}</div></div>
</div>{% for x in data.checks %}<div class="notice {{ 'good' if x.ok else 'badbox' }}"><b>{{ '✓' if x.ok else '✕' }} {{ x.name }}</b><div style="margin-top:5px">{{ x.detail }}</div></div>{% endfor %}
<div class="notice">Если здесь всё зелёное, но мобильный клиент не получает handshake, следующий диагностический шаг — проверка реального UDP-трафика на интерфейсе VPS и Endpoint клиента. Приватные ключи не передавай.</div>
</div>
'''


def apply(nova11: Any) -> bool:
    app = nova11.core.app

    def page():
        return nova11.core.layout("Mobile Diagnostics 3.0", render_template_string(PAGE, data=diagnose()), "/mobile-diagnostics-v3")

    def api():
        return jsonify(diagnose())

    app.add_url_rule("/mobile-diagnostics-v3", "mobile_diagnostics_v3", page)
    app.add_url_rule("/api/nova/diagnostics/mobile3", "mobile_diagnostics_v3_api", api)
    return True
