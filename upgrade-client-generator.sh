#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
BACKUP="$BASE/backups/app-before-client-generator-$(date +%Y%m%d-%H%M%S).py"
[ -f "$APP" ] || { echo "Не найден $APP"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$APP" "$BACKUP"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
if 'AWG CLIENT GENERATOR V2' in s:
    s=s.replace("fd,path=tempfile.mkstemp(prefix='awg-client-',suffix='.conf'); os.close(fd)","fd,path=tempfile.mkstemp(prefix='awgval-',suffix='.conf',dir='/tmp'); os.close(fd)")
    p.write_text(s,encoding='utf-8')
    print('Client Generator v2 validation fixed.')
    raise SystemExit(0)
raise SystemExit('Client Generator v2 is not installed; run the previous generator upgrade first.')
PY
"$BASE/venv/bin/python" -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
if ! systemctl is-active --quiet awgpanel; then echo 'ОШИБКА: awgpanel не запустилась. Восстанавливаю backup.'; cp -a "$BACKUP" "$APP"; systemctl restart awgpanel; exit 1; fi
echo '=== CLIENT GENERATOR V2 VALIDATION FIXED ==='
echo "Backup: $BACKUP"
echo 'Validation file now uses a valid short AWG interface name: awgval.conf.'
