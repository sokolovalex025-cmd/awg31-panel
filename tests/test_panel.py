import importlib
import os
import sys
import types

# app.py expects production paths but can be imported without a running service.
os.environ.setdefault("AWGPANEL_SECRET", "test-secret")
app = importlib.import_module("app")


def test_core_helpers():
    assert app.cfg() is not None
    assert isinstance(app.rows(), list)
    assert isinstance(app.online(), bool)


def test_login_page_smoke():
    client = app.app.test_client()
    response = client.get("/login")
    assert response.status_code == 200
    assert "Войти" in response.get_data(as_text=True)


def test_app9_import_smoke():
    # app9 reuses the stable core and replaces the dashboard/about view functions.
    mod = importlib.import_module("app9")
    assert mod.core.VERSION == "9.0"
    assert "/api/health9" in mod.core.app.url_map._rules_by_endpoint["health9"][0].rule
