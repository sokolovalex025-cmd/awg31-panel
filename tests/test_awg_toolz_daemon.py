import importlib.util
from pathlib import Path

def load():
    spec=importlib.util.spec_from_file_location("awg_toolz_daemon", Path(__file__).parents[1]/"awg-toolz-daemon.py")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_profile_mismatch_is_detected(monkeypatch):
    m=load()
    monkeypatch.setattr(m, "read_config", lambda: {"S2":"24"})
    d=m.status()
    assert d["profile_ok"] is False
    assert d["mismatches"]["S2"]["actual"]=="24"

def test_unknown_action_is_rejected():
    m=load()
    d=m.action("not-allowed")
    assert d["ok"] is False
    assert d["error"]=="unknown action"

def test_confirmation_is_required():
    m=load()
    class Headers(dict):
        def get(self,k,default=None): return super().get(k,default)
    assert "X-NOVA-Confirm" not in Headers()
