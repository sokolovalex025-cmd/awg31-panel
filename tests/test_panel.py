import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")
app = importlib.import_module("app")
app9 = importlib.import_module("app9")
fixes = importlib.import_module("nova11_fixes")
fixes.apply()


def test_core_helpers():
    assert app.cfg() is not None
    assert isinstance(app.online(), bool)


def test_login_page_smoke():
    client = app.app.test_client()
    response = client.get("/login")
    assert response.status_code == 200
    assert "Войти" in response.get_data(as_text=True)


def test_app9_import_smoke():
    mod = app9
    assert mod.core.VERSION == "11.1"
    assert mod.core.app.url_map._rules_by_endpoint["health9"][0].rule == "/api/health9"
    assert mod.core.app.url_map._rules_by_endpoint["diagnostics"][0].rule == "/diagnostics"


def test_health9_smoke():
    client = app9.core.app.test_client()
    with client.session_transaction() as sess:
        sess["logged"] = 1
    response = client.get("/api/health9")
    assert response.status_code == 200
    assert response.get_json()["version"] == "11.1"


def test_awg_profile_is_single_source_of_truth():
    guard = importlib.import_module("nova_awg31_fix")
    assert guard.PARAMS["S1"] == guard.PARAMS["S2"] == guard.PARAMS["S3"] == guard.PARAMS["S4"] == "16"
    assert guard.PARAMS["H1"] == "1"
    assert guard.PARAMS["H2"] == "2"
    assert guard.PARAMS["H3"] == "3"
    assert guard.PARAMS["H4"] == "4"
    assert guard.PARAMS["RandomTrailers"] == "on"


def test_diagnostics_smoke():
    client = app9.core.app.test_client()
    with client.session_transaction() as sess:
        sess["logged"] = 1
    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert "Диагностика" in response.get_data(as_text=True)
