#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
PATCH=/tmp/nova-telegram-ui.py
URL=https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/telegram-ui-fix2/telegram_ui_patch.py
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
[ -f "$BASE/app.py" ] || { echo "[FAIL] $BASE/app.py not found"; exit 1; }

# Add the Telegram menu item directly first. This is intentionally independent
# from the route patch so the menu cannot be skipped because of a stale check.
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/awg31-panel/app.py')
s=p.read_text()
needle="('ⓘ','О NOVA','/about')"
menu="('✈','Telegram Bot','/telegram')," + needle
if "'/telegram'" not in s:
    if needle not in s:
        raise SystemExit('[FAIL] Could not find the NOVA navigation anchor')
    s=s.replace(needle,menu,1)
    p.write_text(s)
    print('[OK] Telegram menu item added')
else:
    print('[OK] Telegram menu item already present')
PY

curl -fsSL --retry 3 "$URL" -o "$PATCH"
python3 -m py_compile "$PATCH"
python3 "$PATCH"
python3 -m py_compile "$BASE/app.py"

# Verify both the menu and route exist before restarting the panel.
python3 - <<'PY'
from pathlib import Path
s=Path('/opt/awg31-panel/app.py').read_text()
if "'/telegram'" not in s or 'def nova_telegram_page' not in s:
    raise SystemExit('[FAIL] Telegram UI verification failed')
print('[OK] Telegram menu + /telegram route verified')
PY

systemctl restart awgpanel.service
sleep 2
echo 'NOVA Telegram UI installed.'
echo 'Open the panel and select: Telegram Bot'
systemctl is-active awgpanel.service
