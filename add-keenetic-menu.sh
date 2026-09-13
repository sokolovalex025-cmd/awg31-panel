#!/usr/bin/env bash
set -euo pipefail
APP="/opt/awg31-panel/app.py"
MARK="('🛜','Keenetic','/keenetic')"
if [[ ! -f "$APP" ]]; then echo "app.py not found: $APP"; exit 1; fi
if grep -Fq "$MARK" "$APP"; then echo "Keenetic menu already present"; exit 0; fi
cp -a "$APP" "$APP.bak.$(date +%Y%m%d-%H%M%S)"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
needle="('СИСТЕМА',["
if needle not in s:
    needle="('ПАНЕЛЬ',["
if needle not in s:
    raise SystemExit('navigation anchor not found; app.py was not changed')
insert="('ИНТЕГРАЦИИ',[('🛜','Keenetic','/keenetic')]),"
pos=s.find(needle)
s=s[:pos]+insert+s[pos:]
p.write_text(s)
PY
python3 -m py_compile "$APP"
systemctl restart awgpanel.service
sleep 1
systemctl is-active --quiet awgpanel.service && echo "NOVA: Keenetic menu installed" || { echo "NOVA: service failed; restore backup if needed"; exit 1; }
