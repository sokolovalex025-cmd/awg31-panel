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

marker="def menu():"
if '🛜 Настроить Keenetic' not in s:
    start=s.find(marker)
    if start<0: raise SystemExit('Telegram menu function not found; no changes made')
    end=s.find('\ndef send(',start)
    if end<0: raise SystemExit('Telegram menu end marker not found; no changes made')
    new_menu="""def menu():\n return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'🛜 Настроить Keenetic','callback_data':'keenetic'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)\n"""
    s=s[:start]+new_menu+s[end+1:]

if "elif data=='keenetic':" not in s:
    help_marker="  elif data=='help':"
    pos=s.find(help_marker)
    if pos<0: raise SystemExit('Telegram help handler not found; no changes made')
    s=s[:pos]+"  elif data=='keenetic':\n   panel=os.getenv('NOVA_PANEL_URL','').rstrip('/')\n   text='🛜 <b>Настройка Keenetic</b>\\n\\n1. Откройте NOVA → Keenetic.\\n2. На Keenetic создайте/импортируйте WireGuard-подключение.\\n3. Для полного туннеля используйте Allowed IPs: <code>0.0.0.0/0</code>.\\n4. В Keenetic включите использование подключения для доступа в Интернет и назначьте нужные устройства в политике подключения.'\n   if panel:text+='\\n\\n🌐 <a href=\"'+panel+'/keenetic\">Открыть Keenetic в NOVA</a>'\n   send(chat,text,True)\n"+s[pos:]

p.write_text(s)
PY
python3 -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl restart "$SERVICE" 2>/dev/null || true
printf '\nTelegram: Keenetic button installed.\nButton: 🛜 Настроить Keenetic\nService: %s\n' "$(systemctl is-active "$SERVICE" 2>/dev/null || true)"