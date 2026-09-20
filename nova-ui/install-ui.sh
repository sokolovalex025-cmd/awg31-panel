#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/nova-ui
BASE="https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/nova-ui"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$APP/templates" "$APP/static"
B="$APP/backup-ui-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$B"
[ -f "$APP/templates/index.html" ] && cp -a "$APP/templates/index.html" "$B/"
[ -f "$APP/static/style.css" ] && cp -a "$APP/static/style.css" "$B/"
curl -fsSL "$BASE/index.html" -o "$TMP/index.html"
curl -fsSL "$BASE/style.css" -o "$TMP/style.css"
install -m 644 "$TMP/index.html" "$APP/templates/index.html"
install -m 644 "$TMP/style.css" "$APP/static/style.css"
echo "NOVA UI updated. Backup: $B"
systemctl list-units --type=service --all | grep -Ei 'nova|uvicorn' || true
