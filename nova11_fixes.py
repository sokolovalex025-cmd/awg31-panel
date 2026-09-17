#!/usr/bin/env python3
"""NOVA 11.1 compatibility and consistency fixes.

Loaded after the legacy NOVA modules so CI and the production bootstrap use the
same runtime behavior without duplicating the large UI modules.
"""
from flask import jsonify


def _patch_diagnostics():
    try:
        import nova_diagnostics
        original = nova_diagnostics.diagnose
    except Exception:
        return

    if getattr(nova_diagnostics, "_nova111_patched", False):
        return

    def diagnose_consistent():
        data = original()
        try:
            import nova_awg31_fix
            expected = nova_awg31_fix.PARAMS
            cfg = nova_diagnostics.nova11.core.cfg()
            required = {k: expected[k] for k in (
                "Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4",
                "H1", "H2", "H3", "H4"
            )}
            missing = [k for k in required if not cfg.get(k)]
            wrong = [k for k, v in required.items()
                     if cfg.get(k) and str(cfg.get(k)) != str(v)]
            for item in data.get("results", []):
                if item.get("name") == "AWG 3.1 obfuscation":
                    item["ok"] = not missing and not wrong
                    item["detail"] = (
                        "J/S/H parameters OK"
                        if item["ok"]
                        else "missing: " + ",".join(missing) +
                             " wrong: " + ",".join(wrong)
                    )
                    item["hint"] = "Запусти nova_awg31_fix.py для миграции профиля."
                    break
        except Exception:
            pass
        return data

    nova_diagnostics.diagnose = diagnose_consistent
    nova_diagnostics._nova111_patched = True


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
        return jsonify({
            "ok": True,
            "version": "11.1",
            "awg": core.online(),
            "port": cfg.get("ListenPort", "1234"),
            "mtu": cfg.get("MTU", "1280"),
        })

    # app9 already contains a database-independent enhanced diagnostics page.
    enhanced = getattr(app9, "_enhanced_diagnostics", None)
    if enhanced is not None:
        core.app.view_functions["diagnostics"] = enhanced
        core.app.view_functions["nova_diagnostics"] = enhanced

    _patch_diagnostics()
    return True


if __name__ == "__main__":
    apply()
    print("NOVA 11.1 compatibility fixes: READY")
