#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
BASE=/opt/awg31-panel
FILE="$BASE/telegram_bot.py"
ENV=/etc/awg31-panel/telegram.env
SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Missing $FILE"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$FILE" "$BASE/backups/telegram_bot-before-delete-$(date +%Y%m%d-%H%M%S).py"
python3 - "$FILE" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
menu_old="def menu():return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)"
menu_new="def menu():return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],[{'text':'📲 QR-код','callback_data':'qr'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'🗑 Удалить конфиг','callback_data':'delete'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)"
if menu_old in s:
    s=s.replace(menu_old,menu_new,1)
elif "callback_data':'delete'" not in s:
    raise SystemExit('menu marker not found; aborting without changes')
helper="""def delete_vpn(chat,uid):
 s=subscription(uid)
 if not s:return send(chat,'🗑 У вас нет VPN-профиля.',True)
 c=client_row(s['client_id'])
 if c:
  try:set_peer_enabled(c['public_key'],False,s['peer_block'])
  except Exception:pass
 dbh=db()
 dbh.execute('UPDATE telegram_subscriptions SET active=0 WHERE telegram_id=?',(uid,))
 dbh.commit();dbh.close()
 send(chat,'🗑 <b>VPN-конфиг удалён</b>\\n\\nДоступ к старому профилю отключён. При необходимости можно получить новый профиль через «🔐 Получить VPN».',True)

"""
if 'def delete_vpn(chat,uid):' not in s:
    pos=s.find('def deliver(chat,uid,username):')
    if pos<0: raise SystemExit('deliver marker not found; aborting without changes')
    s=s[:pos]+helper+s[pos:]
needle="  elif data=='renew':renew(chat,uid,q['from'].get('username',''))"
if needle in s and "elif data=='delete':delete_vpn(chat,uid)" not in s:
    s=s.replace(needle,needle+"\n  elif data=='delete':delete_vpn(chat,uid)",1)
cmdneedle="  elif cmd=='/renew':renew(chat,uid,m['from'].get('username',''))"
if cmdneedle in s and "elif cmd in ('/delete','/delvpn'):delete_vpn(chat,uid)" not in s:
    s=s.replace(cmdneedle,cmdneedle+"\n  elif cmd in ('/delete','/delvpn'):delete_vpn(chat,uid)",1)
p.write_text(s)
PY
"$BASE/venv/bin/python" -m py_compile "$FILE" 2>/dev/null || python3 -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl restart "$SERVICE"
echo "Telegram bot: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
echo 'Delete VPN button installed.'
