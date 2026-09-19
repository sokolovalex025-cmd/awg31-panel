import importlib


def _load_runtime():
    app_mod = importlib.import_module("app")
    nova11 = importlib.import_module("nova11")
    for mod_name in (
        "nova12_diagnostics",
        "nova_mobile_diagnostics3",
        "nova_mobile_monitor",
        "nova_toolza_center",
        "nova_toolza_external",
        "nova12_clients",
        "nova_client_center",
        "nova12_ui",
        "nova_doctor_ui",\n        "nova13_status",
    ):
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "apply"):
            mod.apply(nova11)
    return app_mod


def test_final_navigation_contains_all_operational_entries():
    app_mod = _load_runtime()
    html = app_mod.nav("/awg-toolza")
    for href in (
        "/", "/active", "/clients", "/config", "/obfuscation", "/keenetic",
        "/network", "/traffic", "/diagnostics", "/nova13-status", "/doctor", "/live-monitor",
        "/awg-toolza", "/backups", "/logs", "/settings", "/mobile-diagnostics",
        "/about",
    ):
        assert f'href="{href}"' in html, href


def test_core_and_nova_routes_exist_with_expected_methods():
    app_mod = _load_runtime()
    rules = {rule.rule: set(rule.methods or ()) for rule in app_mod.app.url_map.iter_rules()}
    expected_get = {
        "/", "/active", "/clients", "/config", "/config/download", "/obfuscation",
        "/network", "/traffic", "/diagnostics", "/backups", "/backups/create",
        "/logs", "/settings", "/about", "/mobile-diagnostics", "/mobile-diagnostics-v3",
        "/live-monitor", "/api/nova/live-monitor", "/awg-toolza", "/api/nova/toolza-center",
        "/doctor", "/api/doctor", "/api/nova/toolza-external", "/nova13-status", "/api/nova13/status",
    }
    for route in expected_get:
        assert route in rules, route
        assert "GET" in rules[route], route

    expected_post = {
        "/clients/create", "/api/nova/toolza-action",
    }
    for route in expected_post:
        assert route in rules, route
        assert "POST" in rules[route], route

    assert any(r.rule == "/clients/<int:cid>/conf" and "GET" in r.methods for r in app_mod.app.url_map.iter_rules())
    assert any(r.rule == "/clients/<int:cid>/qr" and "GET" in r.methods for r in app_mod.app.url_map.iter_rules())
    assert any(r.rule == "/clients/<int:cid>/delete" and "POST" in r.methods for r in app_mod.app.url_map.iter_rules())
    assert any(r.rule == "/clients/<int:cid>/toggle" and "POST" in r.methods for r in app_mod.app.url_map.iter_rules())


def test_toolza_client_shortcuts_and_actions_are_wired():
    src = open("nova_toolza_center.py", encoding="utf-8").read()
    assert 'href="/clients"' in src
    assert 'href="/clients#new-client"' in src
    for action in ("apply-profile", "repair-nat", "restart-awg", "repair-all"):
        assert f"novaToolzaAction('{action}')" in src
        assert action in src
    assert "fetch('/api/nova/toolza-action'" in src
    assert "fetch('/api/nova/toolza-center'" in src
