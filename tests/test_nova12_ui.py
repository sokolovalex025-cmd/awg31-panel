import importlib

app = importlib.import_module("app")
nova11 = importlib.import_module("nova11")
nova12_ui = importlib.import_module("nova12_ui")


def test_mobile_diagnostics_is_visible_and_active():
    nova12_ui.apply(nova11)
    html = nova11.core.nav("/mobile-diagnostics")
    assert "/mobile-diagnostics" in html
    assert "Мобильная диагностика" in html
    assert 'class="active"' in html


def test_ui_patch_is_idempotent():
    nova12_ui.apply(nova11)
    nova12_ui.apply(nova11)
    html = nova11.core.nav("/")
    assert html.count("/mobile-diagnostics") == 1
    assert nova11.core.VERSION == "12.0"
