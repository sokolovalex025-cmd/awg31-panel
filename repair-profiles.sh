#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$APP" ] || { echo "Missing $APP"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$APP" "$BASE/backups/app-before-profile-repair-$(date +%Y%m%d-%H%M%S).py"

compile_ok() { /opt/awg31-panel/venv/bin/python -m py_compile "$APP" >/tmp/awgpanel-pycompile.out 2>&1; }

# If a previous profile upgrade left a broken app.py, restore the last known-good
# pre-profile version and let the corrected upgrade script install profiles again.
if ! compile_ok; then
  echo 'Current app.py has a Python syntax error. Restoring the latest pre-profile backup...'
  backup=$(ls -1t "$BASE"/backups/app-before-profiles-*.py 2>/dev/null | head -n1 || true)
  if [ -z "$backup" ]; then
    echo 'No pre-profile backup found.'
    cat /tmp/awgpanel-pycompile.out
    exit 1
  fi
  cp -a "$backup" "$APP"
  echo "Restored: $backup"
fi

chmod +x "$SCRIPT_DIR/upgrade-profiles.sh"
"$SCRIPT_DIR/upgrade-profiles.sh" || true

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

if ! compile_ok; then
  echo '=== PYTHON SYNTAX ERROR ==='
  cat /tmp/awgpanel-pycompile.out
  exit 1
fi
systemctl restart awgpanel
sleep 2
if ! systemctl is-active --quiet awgpanel; then
  systemctl --no-pager --full status awgpanel || true
  exit 1
fi

echo '=== PROFILE REPAIR COMPLETE ==='
echo 'Panel: http://SERVER_IP:8080/profiles'
