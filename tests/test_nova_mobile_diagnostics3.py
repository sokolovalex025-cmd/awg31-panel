import importlib
import os

os.environ.setdefault("AWGPANEL_SECRET", "test-secret")


def test_safe_config_removes_secrets():
    mod = importlib.import_module("nova_mobile_diagnostics3")
    safe = mod.safe_config({
        "ListenPort": "1234",
        "PrivateKey": "SUPER-SECRET",
        "PresharedKey": "PSK-SECRET",
        "HeaderProtectionKey": "HP-SECRET",
        "dns": "1.1.1.1",
    })
    assert safe == {"ListenPort": "1234", "dns": "1.1.1.1"}
    assert "SUPER-SECRET" not in repr(safe)
    assert "PSK-SECRET" not in repr(safe)


def test_default_route_parser():
    mod = importlib.import_module("nova_mobile_diagnostics3")
    monkey = lambda *args: (0, "default via 192.0.2.1 dev ens3 proto dhcp")
    original = mod.run
    try:
        mod.run = monkey
        assert mod.default_route() == ("192.0.2.1", "ens3")
    finally:
        mod.run = original


def test_diagnostics_reports_port_and_network(monkeypatch):
    mod = importlib.import_module("nova_mobile_diagnostics3")
    monkeypatch.setattr(mod, "run", lambda *args: (0, "default via 192.0.2.1 dev ens3"))
    monkeypatch.setattr(mod, "public_ip", lambda: "198.51.100.20")
    monkeypatch.setattr(mod, "udp_listener", lambda port: port == "1234")
    monkeypatch.setattr(mod, "forwarding", lambda: True)
    monkeypatch.setattr(mod, "nat_detected", lambda: True)
    monkeypatch.setattr(mod, "app", None, raising=False)
    monkeypatch.setitem(mod.__dict__, "read_cfg", lambda: {"ListenPort": "1234", "MTU": "1280"})
    data = mod.diagnose()
    assert data["ok"] is True
    assert data["port"] == "1234"
    assert data["public_ipv4"] == "198.51.100.20"
    assert data["interface"] == "ens3"
