import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")


def test_diagnostics_normalizes_core_mobile_state(monkeypatch):
    mod = importlib.import_module("nova12_diagnostics")
    monkeypatch.setattr(mod, "run", lambda *args: (0, "awg0 UP"))
    monkeypatch.setattr(mod, "read_cfg", lambda: {"ListenPort": "1234", "MTU": "1280", "Jc": "4", "Jmin": "40", "Jmax": "120", "S1": "16", "S2": "16", "S3": "16", "S4": "16", "H1": "1", "H2": "2", "H3": "3", "H4": "4", "RandomTrailers": "on"})
    monkeypatch.setattr(mod, "recent_peers", lambda: [{"endpoint": "198.51.100.10:50000", "handshake": 1, "rx": 1024, "tx": 2048, "online": True}])
    data = mod.diagnose()
    assert data["port"] == "1234"
    assert data["mtu"] == "1280"
    assert data["profile_ok"] is True
    assert data["online_peers"] == 1


def test_profile_mismatch_is_reported(monkeypatch):
    mod = importlib.import_module("nova12_diagnostics")
    monkeypatch.setattr(mod, "read_cfg", lambda: {"ListenPort": "1234", "MTU": "1280", "Jc": "4", "Jmin": "40", "Jmax": "120", "S1": "16", "S2": "24", "S3": "16", "S4": "32", "H1": "1", "H2": "2", "H3": "3", "H4": "4", "RandomTrailers": "on"})
    result = mod.profile_check(mod.read_cfg())
    assert result["ok"] is False
    assert "S2" in result["wrong"]
    assert "S4" in result["wrong"]


def test_diagnostics_never_exposes_private_key(monkeypatch):
    mod = importlib.import_module("nova12_diagnostics")
    monkeypatch.setattr(mod, "read_cfg", lambda: {"ListenPort": "1234", "PrivateKey": "SUPER-SECRET"})
    safe = mod.safe_config(mod.read_cfg())
    assert "PrivateKey" not in safe
    assert "SUPER-SECRET" not in repr(safe)
