import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "nova_client_center.py").read_text(encoding="utf-8")


def test_client_center_compiles():
    ast.parse(SRC)


def test_client_center_has_creation_and_download_views():
    tree = ast.parse(SRC)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert {"_clients_page", "_create_client", "_delete_client", "_conf", "_qr", "apply"} <= names


def test_generated_profile_does_not_reintroduce_legacy_s2_s4_values():
    assert '"S2":"24"' not in SRC
    assert '"S4":"32"' not in SRC
    assert "S2 = 24" not in SRC
    assert "S4 = 32" not in SRC


def test_client_center_uses_canonical_awg_profile():
    assert 'import nova_awg31_fix' in SRC
    assert '"S1":"16"' in SRC
    assert '"S2":"16"' in SRC
    assert '"S3":"16"' in SRC
    assert '"S4":"16"' in SRC
    assert '"H1":"1"' in SRC
    assert '"H2":"2"' in SRC
    assert '"H3":"3"' in SRC
    assert '"H4":"4"' in SRC
