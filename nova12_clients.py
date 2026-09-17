#!/usr/bin/env python3
"""NOVA 12.0 client-profile consistency layer."""


def apply(app):
    """Make generated client profiles inherit the canonical AWG 3.1 profile."""
    if getattr(app, "_nova12_clients_patched", False):
        return app

    original = app.client_config
    keys = (
        "Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4",
        "H1", "H2", "H3", "H4", "ContentPaddingAddition",
        "RekeyAfterTime", "RekeyTimeout", "RejectAfterTime",
        "KeepaliveTimeout", "MaxHandshakeAttempts",
        "RandomTrailers", "DisableCookies",
    )
    try:
        import nova_awg31_fix
        expected = dict(nova_awg31_fix.PARAMS)
    except Exception:
        expected = {
            "Jc": "4", "Jmin": "40", "Jmax": "120",
            "S1": "16", "S2": "16", "S3": "16", "S4": "16",
            "H1": "1", "H2": "2", "H3": "3", "H4": "4",
        }

    def client_config_consistent(row):
        text = original(row)
        lines = text.splitlines()
        seen = set()
        out = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in keys and key in expected:
                if key in seen:
                    continue
                out.append(f"{key} = {expected[key]}")
                seen.add(key)
            else:
                out.append(line)
        insert_at = 0
        for i, line in enumerate(out):
            if line.startswith("MTU = "):
                insert_at = i + 1
        missing = [k for k in keys if k in expected and k not in seen]
        out[insert_at:insert_at] = [f"{k} = {expected[k]}" for k in missing]
        return "\n".join(out) + "\n"

    app.client_config = client_config_consistent
    app._nova12_clients_patched = True
    return app
