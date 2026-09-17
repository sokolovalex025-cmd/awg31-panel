import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")
app = importlib.import_module("app")
clients12 = importlib.import_module("nova12_clients")
clients12.apply(app)


def test_client_config_inherits_single_awg_profile(monkeypatch):
    monkeypatch.setattr(app, "cfg", lambda: {
        "ListenPort": "1234", "MTU": "1280",
        "Jc": "4", "Jmin": "40", "Jmax": "120",
        "S1": "16", "S2": "16", "S3": "16", "S4": "16",
        "H1": "1", "H2": "2", "H3": "3", "H4": "4",
    })
    monkeypatch.setattr(app, "setting", lambda key, default="": "vpn.example.test" if key == "endpoint" else default)
    monkeypatch.setattr(app, "server_public", lambda: "SERVER-PUBLIC")
    config = app.client_config({
        "private_key": "CLIENT-PRIVATE",
        "address": "10.66.66.2/32",
        "psk": "CLIENT-PSK",
    })
    assert "S1 = 16" in config
    assert "S2 = 16" in config
    assert "S3 = 16" in config
    assert "S4 = 16" in config
    assert "S2 = 24" not in config
    assert "S4 = 32" not in config
    assert "Endpoint = vpn.example.test:1234" in config


def test_client_config_does_not_fallback_to_old_obfuscation_values(monkeypatch):
    monkeypatch.setattr(app, "cfg", lambda: {"ListenPort": "1234", "MTU": "1280"})
    monkeypatch.setattr(app, "setting", lambda key, default="": "vpn.example.test" if key == "endpoint" else default)
    monkeypatch.setattr(app, "server_public", lambda: "SERVER-PUBLIC")
    config = app.client_config({
        "private_key": "CLIENT-PRIVATE",
        "address": "10.66.66.2/32",
        "psk": "CLIENT-PSK",
    })
    assert all(f"{key} = {value}" in config for key, value in {
        "Jc": "4", "Jmin": "40", "Jmax": "120",
        "S1": "16", "S2": "16", "S3": "16", "S4": "16",
        "H1": "1", "H2": "2", "H3": "3", "H4": "4",
    }.items())
