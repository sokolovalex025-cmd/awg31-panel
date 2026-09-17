import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")


def test_awg_profile_is_single_source_of_truth():
    fixer = importlib.import_module("nova_awg31_fix")
    diagnostics = importlib.import_module("nova_diagnostics")
    assert diagnostics.EXPECTED_AWG_PARAMS == fixer.PARAMS
    assert diagnostics.EXPECTED_AWG_PARAMS["S1"] == "16"
    assert diagnostics.EXPECTED_AWG_PARAMS["S2"] == "16"
    assert diagnostics.EXPECTED_AWG_PARAMS["S3"] == "16"
    assert diagnostics.EXPECTED_AWG_PARAMS["S4"] == "16"


def test_diagnostics_can_render_without_production_sqlite():
    app = importlib.import_module("app")
    app9 = importlib.import_module("app9")
    client = app9.core.app.test_client()
    with client.session_transaction() as sess:
        sess["logged"] = 1
    response = client.get("/diagnostics")
    assert response.status_code == 200
    assert "Диагностика" in response.get_data(as_text=True)


def test_health9_endpoint_exists_and_is_public_smoke():
    app9 = importlib.import_module("app9")
    rules = app9.core.app.url_map._rules_by_endpoint
    assert "health9" in rules
    assert rules["health9"][0].rule == "/api/health9"
