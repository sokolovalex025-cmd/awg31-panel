#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
BASE="/opt/awg31-panel"
[ -d "$REPO_DIR/.git" ] || { echo "Repository not found: $REPO_DIR"; exit 2; }

git -C "$REPO_DIR" fetch origin main
git -C "$REPO_DIR" reset --hard origin/main
mkdir -p "$BASE"
for f in nova_shield.py panel_bootstrap.py nova14_theme.py antiblock.py domain_manager.py; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
chmod 755 "$BASE/panel_bootstrap.py" "$BASE/antiblock.py"
PY="$REPO_DIR/venv/bin/python"
[ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$BASE/nova_shield.py" "$BASE/panel_bootstrap.py" "$BASE/antiblock.py" "$BASE/domain_manager.py" "$BASE/nova14_theme.py"
systemctl daemon-reload
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null
systemctl reload nginx || true
printf '\nNOVA MAX update complete.\n'
printf 'Shield: /shield and /api/shield/status\n'
printf 'Primary awg0: not modified by Shield\n'
printf 'Panel: active\n'
