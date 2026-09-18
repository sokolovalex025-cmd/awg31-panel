import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nova_mobile_monitor as mod

def test_snapshot_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "DB", tmp_path / "panel.db")
    data = {"online_peers": 1, "peer_count": 2, "peers":[{"rx":100,"tx":200},{"rx":300,"tx":400}]}
    mod._snapshot(data)
    h = mod._history()
    assert len(h) == 1
    assert h[0]["online"] == 1
    assert h[0]["peers"] == 2
    assert h[0]["rx"] == 400
    assert h[0]["tx"] == 600

def test_module_does_not_expose_keys():
    text = Path(mod.__file__).read_text()
    assert "PrivateKey" not in text
    assert "PresharedKey" not in text
