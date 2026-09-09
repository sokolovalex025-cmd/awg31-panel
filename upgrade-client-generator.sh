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
import re
import sys

p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')

if 'AWG CLIENT GENERATOR V2' not in s:
    raise SystemExit('Client Generator v2 is not installed; run the previous generator upgrade first.')

# awg-quick validates the basename as an interface name.  The old
# tempfile prefix produced names such as awg-client-XXXXXX.conf,
# which exceed the Linux interface-name limit.  Replace any variant
# of the generator's temporary config creation with a fixed valid name.
pattern = r"tempfile\.mkstemp\([^\n]*?suffix=['\"]\.conf['\"][^\n]*?\)"
replacement = "tempfile.mkstemp(prefix='awgval-',suffix='.conf',dir='/tmp')"
s2, n = re.subn(pattern, replacement, s, count=1)

if n == 0:
    # Also handle the exact legacy one-line form if spacing/ordering differs.
    old = "fd,path=tempfile.mkstemp(prefix='awg-client-',suffix='.conf'); os.close(fd)"
    new = "fd,path=tempfile.mkstemp(prefix='awgval-',suffix='.conf',dir='/tmp'); os.close(fd)"
    if old in s:
        s2 = s.replace(old, new, 1)
        n = 1

if n == 0:
    raise SystemExit('Не найден вызов tempfile.mkstemp() генератора клиента; app.py не изменён.')

# Keep os.close(fd) if the replacement consumed only the mkstemp call.
s2 = s2.replace(
    "fd,path=tempfile.mkstemp(prefix='awgval-',suffix='.conf',dir='/tmp')\n",
    "fd,path=tempfile.mkstemp(prefix='awgval-',suffix='.conf',dir='/tmp'); os.close(fd)\n",
    1,
)
p.write_text(s2,encoding='utf-8')
print('Client Generator v2 validation fixed.')
PY
"$BASE/venv/bin/python" -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
if ! systemctl is-active --quiet awgpanel; then
  echo 'ОШИБКА: awgpanel не запустилась. Восстанавливаю backup.'
  cp -a "$BACKUP" "$APP"
  systemctl restart awgpanel
  exit 1
fi

echo '=== CLIENT GENERATOR V2 VALIDATION FIXED ==='
echo "Backup: $BACKUP"
echo 'Validation file uses a valid short AWG interface name: awgval-XXXXXX.conf.'
echo 'Check with: grep -n "tempfile.mkstemp" /opt/awg31-panel/app.py'
