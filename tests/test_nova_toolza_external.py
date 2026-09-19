import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_external_toolza_bridge_compiles():
    ast.parse((ROOT / "nova_toolza_external.py").read_text(encoding="utf-8"))


def test_external_toolza_is_pinned_and_non_destructive():
    src = (ROOT / "nova_toolza_external.py").read_text(encoding="utf-8")
    assert "ecccafa3094181a6962ff71e54527e4771657698" in src
    assert 'subprocess.run' in src
    assert '["--help"]' in src


def test_installer_is_bash_syntax_checked():
    src = (ROOT / "install-awg-toolza.sh").read_text(encoding="utf-8")
    assert 'bash -n "$tmp"' in src
    assert "NOVA awg0.conf was not modified." in src
    assert "ecccafa3094181a6962ff71e54527e4771657698" in src

# Focused CI smoke coverage for the external Toolza bridge.

# smoke rerun

# final smoke assertion fix


def test_web_bridge_is_explicitly_read_only():
    src = (ROOT / "nova_toolza_external.py").read_text(encoding="utf-8")
    assert 'WEB_EXECUTION_ENABLED = False' in src
    assert 'web_execution_enabled' in src
    assert 'never execute' in src.lower()


def test_toolza_center_does_not_launch_external_awg2():
    src = (ROOT / "nova_toolza_center.py").read_text(encoding="utf-8")
    assert '["awg2"' not in src
    assert 'external_toolza_control' in src
    assert '127.0.0.1:9090' in src
