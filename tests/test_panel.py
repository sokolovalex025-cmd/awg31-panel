import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")
app = importlib.import_module("app")


def test_core_helpers():
    assert app.cfg() is not None
    assert isinstance(app.online(), bool)


def test_login_page_smoke():
    client = app.app.test_client()
    response = client.get("/login")
    assert response.status_code == 200
    assert "Войти" in response.get_data(as_text=True)


def test_app9_import_smoke():
    mod = importlib.import_module("app9")
    assert mod.core.VERSION == "9.2"
    assert mod.core.app.url_map._rules_by_endpoint["health9"][0].rule == "/api/health9"
    assert mod.core.app.url_map._rules_by_endpoint["diagnostics92"][0].rule == "/diagnostics"


def test_diagnostics_smoke():
    mod = importlib.import_module("app9")
    client = mod.core.app.test_client()
    with client.session_transaction() as sess:
        sess["logged"] = 1
    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert "Диагностика" in response.get_data(as_text=True)
