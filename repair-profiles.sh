#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
[ -f "$APP" ] || { echo "Missing $APP"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$APP" "$BASE/backups/app-before-profile-repair-$(date +%Y%m%d-%H%M%S).py"

if ! grep -q 'AWG PROFILE MANAGER V1' "$APP"; then
  echo 'Profile manager is not installed; running upgrade-profiles.sh.'
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  chmod +x "$SCRIPT_DIR/upgrade-profiles.sh"
  "$SCRIPT_DIR/upgrade-profiles.sh"
fi

python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
s=s.replace("{{cur.get('H3','-'))}}", "{{cur.get('H3','-')}}")
s=s.replace("VERSION='8.1';BG_VERSION='82'", "VERSION='8.2';BG_VERSION='82'")
s=s.replace("VERSION='8.0';BG_VERSION='82'", "VERSION='8.2';BG_VERSION='82'")
old="('♣','Клиенты','/clients'),('▤','Конфигурация','/config')"
new="('♣','Клиенты','/clients'),('◈','Профили подключения','/profiles'),('▤','Конфигурация','/config')"
s=s.replace(old,new)
p.write_text(s)
PY
/opt/awg31-panel/venv/bin/python -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
echo '=== PROFILE REPAIR COMPLETE ==='
echo 'Panel: http://SERVER_IP:8080/profiles'
