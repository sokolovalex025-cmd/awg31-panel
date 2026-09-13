#!/usr/bin/env bash
set -euo pipefail
BASE=/opt/awg31-panel; APP="$BASE/app.py"; BACKUP="$APP.bak-balancer-$(date +%Y%m%d-%H%M%S)"; TOKEN_FILE=/etc/awg31-panel/balancer.env
[ -f "$APP" ] || { echo "app.py not found: $APP"; exit 1; }; cp -a "$APP" "$BACKUP"; install -d -m 700 /etc/awg31-panel
if [ ! -f "$TOKEN_FILE" ]; then python3 - <<'PY' > "$TOKEN_FILE"
import secrets
print('BALANCER_TOKEN='+secrets.token_urlsafe(32))
PY
chmod 600 "$TOKEN_FILE"; fi
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/awg31-panel/app.py');s=p.read_text()
if 'import balancer as _nova_balancer' not in s:
 marker="if __name__=='__main__':app.run(host='0.0.0.0',port=8080)"
 if marker not in s: raise SystemExit('Cannot find app.run marker')
 s=s.replace(marker,"import balancer as _nova_balancer\n"+marker,1)
if "('⚖','Балансировка','/balancer')" not in s:
 needle="('☷','Логи','/logs')])"
 if needle not in s: raise SystemExit('Cannot find navigation marker')
 s=s.replace(needle,"('☷','Логи','/logs'),('⚖','Балансировка','/balancer')])",1)
p.write_text(s)
PY
# The balancer module is imported by app.py and exposes the UI. Existing client allocation remains local until nodes are configured.
systemctl daemon-reload 2>/dev/null || true
systemctl restart awg31-panel 2>/dev/null || systemctl restart awg31-panel.service 2>/dev/null || true
echo "NOVA AWG balancer installed. Backup: $BACKUP"
echo "Open: /balancer"
