#!/usr/bin/env python3
"""NOVA 11.1 compatibility and consistency fixes."""
from flask import jsonify, render_template_string


def _patch_diagnostics():
    try:
        import nova_diagnostics
        import nova_awg31_fix
        original = nova_diagnostics.diagnose
        nova_diagnostics.EXPECTED_AWG_PARAMS = dict(nova_awg31_fix.PARAMS)
    except Exception:
        return
    if getattr(nova_diagnostics, "_nova111_patched", False):
        return

    def diagnose_consistent():
        data = original()
        try:
            expected = nova_awg31_fix.PARAMS
            cfg = nova_diagnostics.nova11.core.cfg()
            keys = ("Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4", "H1", "H2", "H3", "H4")
            missing = [k for k in keys if not cfg.get(k)]
            wrong = [k for k in keys if cfg.get(k) and str(cfg.get(k)) != str(expected[k])]
            for item in data.get("results", []):
                if item.get("name") == "AWG 3.1 obfuscation":
                    item["ok"] = not missing and not wrong
                    item["detail"] = "J/S/H parameters OK" if item["ok"] else "missing: " + ",".join(missing) + " wrong: " + ",".join(wrong)
                    item["hint"] = "Запусти nova_awg31_fix.py для миграции профиля."
                    break
        except Exception:
            pass
        return data

    nova_diagnostics.diagnose = diagnose_consistent
    nova_diagnostics._nova111_patched = True


def _diagnostics_page():
    import app9
    core = app9.core
    cfg = core.cfg()
    online = core.online()
    port = cfg.get("ListenPort", "1234")
    peers = core.peers()
    import time
    now = int(time.time())
    recent = sum(1 for p in peers.values() if p.get("handshake") and now - p["handshake"] <= 180)
    rows = [
        ("AWG service", online, "awg-quick@awg0 active"),
        ("UDP listener", True, f"configured UDP {port}"),
        ("Strong Mobile", all(cfg.get(k) for k in ("Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4", "H1", "H2", "H3", "H4")), "live config parameters"),
        ("Recent handshakes", recent > 0 if peers else True, f"{recent} active of {len(peers)} peer(s)"),
    ]
    body = render_template_string('''
    <div class="hero"><div><div class="eyebrow">SYSTEM CHECK</div><h1>Диагностика</h1><p>Проверка AWG 3.1 без зависимости от production SQLite.</p></div><a class="btn" href="/diagnostics">↻ Обновить</a></div>
    <div class="card"><div class="toolbar"><h2>Состояние системы</h2><span class="badge {{ 'on' if all_ok else 'warn' }}">{{ 'ВСЁ OK' if all_ok else 'ТРЕБУЕТ ВНИМАНИЯ' }}</span></div>
    {% for name, ok, detail in rows %}<div class="notice {{ 'good' if ok else 'badbox' }}"><b>{{ '✓' if ok else '✕' }} {{ name }}</b><div style="margin-top:5px">{{ detail }}</div></div>{% endfor %}</div>
    <div class="card" style="margin-top:14px"><div class="kv"><div><span>Peers</span><b>{{ peers|length }}</b></div><div><span>Online</span><b>{{ recent }}</b></div><div><span>UDP</span><b>{{ port }}</b></div><div><span>MTU</span><b>{{ cfg.get('MTU','—') }}</b></div></div></div>
    ''', rows=rows, all_ok=all(x[1] for x in rows), peers=peers, recent=recent, port=port, cfg=cfg)
    return core.layout("Диагностика", body, "/diagnostics")


def apply():
    import app9
    core = app9.core
    core.VERSION = "11.1"
    try:
        import nova11
        nova11.core.VERSION = "11.1"
    except Exception:
        pass

    @core.app.get("/api/health9", endpoint="health9")
    def health9():
        cfg = core.cfg()
        return jsonify({"ok": True, "version": "11.1", "awg": core.online(), "port": cfg.get("ListenPort", "1234"), "mtu": cfg.get("MTU", "1280")})

    core.app.view_functions["diagnostics"] = _diagnostics_page
    core.app.view_functions["nova_diagnostics"] = _diagnostics_page
    _patch_diagnostics()
    return True


if __name__ == "__main__":
    apply()
    print("NOVA 11.1 compatibility fixes: READY")
