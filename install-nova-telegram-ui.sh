#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
PATCH=/tmp/nova-telegram-ui.py
URL=https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/telegram-ui-fix2/telegram_ui_patch.py
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
curl -fsSL --retry 3 "$URL" -o "$PATCH"
python3 -m py_compile "$PATCH"
python3 "$PATCH"
python3 -m py_compile "$BASE/app.py"
systemctl restart awgpanel.service
sleep 2
echo 'NOVA Telegram UI installed.'
echo 'Open the panel and select: Telegram Bot'
systemctl is-active awgpanel.service
