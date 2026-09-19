import nova_toolza_center as m

def test_snapshot_is_read_only_and_has_canonical_profile(monkeypatch):
    monkeypatch.setattr(m, "_version", lambda: {"tools":"amneziawg-tools v3.1.20260812","loaded_module":"3.1.20260812"})
    monkeypatch.setattr(m, "_listen_port", lambda: [1234])
    monkeypatch.setattr(m, "_config", lambda: {**m.PARAMS, "ListenPort":"1234"})
    monkeypatch.setattr(m, "_awg_state", lambda: {"up": True, "interface":"awg0", "has_private_key":False, "raw":None})
    monkeypatch.setattr(m, "_public_ipv4", lambda: "95.85.241.45")
    monkeypatch.setattr(m, "_route", lambda: "default via 10.0.0.1 dev ens3")
    monkeypatch.setattr(m, "_forwarding", lambda: True)
    monkeypatch.setattr(m, "_nat", lambda: True)
    monkeypatch.setattr(m, "_dns", lambda: ["8.8.8.8 1.1.1.1"])
    monkeypatch.setattr(m, "_probe", lambda *x: {"name":x[0],"host":x[1],"port":x[2],"ipv4":["1.2.3.4"],"dns_ok":True,"tcp_ok":True})
    d=m.snapshot()
    assert d["profile_ok"] is True
    assert d["listen_port"]=="1234"
    assert d["mode"]=="read-only"
    assert d["expected_profile"]["S1"]=="16"
    assert d["expected_profile"]["S2"]=="16"
    assert d["expected_profile"]["S3"]=="16"
    assert d["expected_profile"]["S4"]=="16"
    assert d["network"]["forwarding"] is True
    assert d["network"]["nat"] is True
    assert d["awg_state"]["has_private_key"] is False

def test_mismatch_is_reported(monkeypatch):
    monkeypatch.setattr(m, "_version", lambda: {"tools":"x","loaded_module":"y"})
    monkeypatch.setattr(m, "_listen_port", lambda: [])
    monkeypatch.setattr(m, "_config", lambda: {"S2":"24"})
    monkeypatch.setattr(m, "_awg_state", lambda: {"up": False, "interface":"missing", "has_private_key":False, "raw":None})
    monkeypatch.setattr(m, "_public_ipv4", lambda: "unknown")
    monkeypatch.setattr(m, "_route", lambda: "unknown")
    monkeypatch.setattr(m, "_forwarding", lambda: False)
    monkeypatch.setattr(m, "_nat", lambda: False)
    monkeypatch.setattr(m, "_dns", lambda: [])
    monkeypatch.setattr(m, "_probe", lambda *x: {"name":x[0],"host":x[1],"port":x[2],"ipv4":[],"dns_ok":False,"tcp_ok":False})
    d=m.snapshot()
    assert d["profile_ok"] is False
    assert d["mismatches"]["S2"]["actual"]=="24"

def test_probe_reports_dns_and_tcp_separately(monkeypatch):
    monkeypatch.setattr(m.socket, "getaddrinfo", lambda *a, **k: [(2,1,6,"",("203.0.113.10",443))])
    monkeypatch.setattr(m, "_tcp", lambda *a, **k: False)
    d=m._probe("Test", "example.invalid", 443)
    assert d["dns_ok"] is True
    assert d["tcp_ok"] is False
    assert d["ipv4"] == ["203.0.113.10"]


def test_daemon_request_failure_is_safe(monkeypatch):
    monkeypatch.setattr(m, "_daemon", lambda: {"ok": False, "error": "not running"})
    d = m.snapshot()
    assert d["daemon"]["ok"] is False
