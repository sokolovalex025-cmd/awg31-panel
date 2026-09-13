#!/usr/bin/env bash
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
BASE=/opt/awg31-panel
FILE="$BASE/telegram_bot.py"
SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Missing $FILE"; exit 1; }

cp -a "$FILE" "$BASE/telegram_bot.py.before-keenetic-$(date +%Y%m%d-%H%M%S)"

python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old="def menu():return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)"
new="""def menu():
 return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'🛜 Настроить Keenetic','url':'/keenetic'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)"""
if '🛜 Настроить Keenetic' in s:
 print('Keenetic Telegram button already present.')
else:
 if old not in s: raise SystemExit('Telegram menu marker not found; no changes made')
 s=s.replace(old,new,1)
 p.write_text(s)
PY
python3 -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl restart "$SERVICE" 2>/dev/null || true
printf '\nTelegram: Keenetic button installed.\n'
printf 'Button: 🛜 Настроить Keenetic\n'
printf 'Target: /keenetic\n'
printf 'Service: %s\n' "$(systemctl is-active "$SERVICE" 2>/dev/null || true)"
