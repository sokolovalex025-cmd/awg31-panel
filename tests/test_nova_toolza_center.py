import nova_toolza_center as m

def test_snapshot_is_read_only_and_has_canonical_profile(monkeypatch):
    monkeypatch.setattr(m, "_version", lambda: {"tools":"amneziawg-tools v3.1.20260812","loaded_module":"3.1.20260812"})
    monkeypatch.setattr(m, "_listen_port", lambda: [1234])
    monkeypatch.setattr(m, "_config", lambda: {**m.PARAMS, "ListenPort":"1234"})
    d=m.snapshot()
    assert d["profile_ok"] is True
    assert d["listen_port"]=="1234"
    assert d["mode"]=="read-only"
    assert d["expected_profile"]["S1"]=="16"
    assert d["expected_profile"]["S2"]=="16"
    assert d["expected_profile"]["S3"]=="16"
    assert d["expected_profile"]["S4"]=="16"

def test_mismatch_is_reported(monkeypatch):
    monkeypatch.setattr(m, "_version", lambda: {"tools":"x","loaded_module":"y"})
    monkeypatch.setattr(m, "_listen_port", lambda: [])
    monkeypatch.setattr(m, "_config", lambda: {"S2":"24"})
    d=m.snapshot()
    assert d["profile_ok"] is False
    assert d["mismatches"]["S2"]["actual"]=="24"
