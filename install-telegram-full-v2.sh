#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
BASE=/opt/awg31-panel
FILE="$BASE/telegram_bot.py"
ENV=/etc/awg31-panel/telegram.env
SERVICE=awgpanel-telegram.service
REPO='https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/telegram_bot.py'
[ -f "$FILE" ] || { echo "Missing $FILE"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$FILE" "$BASE/backups/telegram_bot-before-full-v2-$(date +%Y%m%d-%H%M%S).py"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
curl -fsSL --retry 3 "$REPO" -o "$TMP"
python3 - "$FILE" "$TMP" <<'PY'
from pathlib import Path
import sys
live=Path(sys.argv[1]); source=Path(sys.argv[2])
s=source.read_text()
# The repository bot is the known-good self-service core. Upgrade its menu and dispatcher
# without relying on the formatting of the locally installed copy.
old_menu="def menu():return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'ℹ️ Помощь','callback_data':'help'}]]},ensure_ascii=False)"
new_menu="""def menu():\n return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],[{'text':'📲 QR-код','callback_data':'qr'},{'text':'♻️ Продлить','callback_data':'renew'}],[{'text':'📊 Статус','callback_data':'status'},{'text':'🆘 Помощь','callback_data':'help'}]]},ensure_ascii=False)\n\ndef admin_menu():\n return json.dumps({'inline_keyboard':[[{'text':'👥 Пользователи','callback_data':'users'},{'text':'📊 Статистика','callback_data':'stats'}],[{'text':'🖥 Сервер','callback_data':'server'},{'text':'🔄 Перезапуск AWG','callback_data':'awg_restart'}],[{'text':'⬅️ Главное меню','callback_data':'home'}]]},ensure_ascii=False)\n\ndef send_markup(chat,text,markup):tg('sendMessage',{'chat_id':chat,'text':text,'parse_mode':'HTML','reply_markup':markup})"""
if old_menu not in s: raise SystemExit('source menu marker not found')
s=s.replace(old_menu,new_menu,1)
marker='def deliver(chat,uid,username):'
if marker not in s: raise SystemExit('source deliver marker not found')
helpers="""def send_conf(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'📄 Сначала получите VPN-профиль.',True)\n try: multipart('sendDocument',{'chat_id':chat,'caption':'📄 Конфигурация AmneziaWG 3.1'},{'document':('NOVA-'+str(s['client_id'])+'.conf',conf_bytes(s['client_id']),'text/plain')})\n except Exception: send(chat,'❌ Не удалось получить конфигурацию.',True)\n\ndef send_qr(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'📲 Сначала получите VPN-профиль.',True)\n try: multipart('sendPhoto',{'chat_id':chat,'caption':'📲 QR-код AmneziaWG 3.1'},{'photo':('NOVA-'+str(s['client_id'])+'.png',qr_bytes(s['client_id']),'image/png')})\n except Exception: send(chat,'❌ Не удалось получить QR-код.',True)\n\ndef server_status():\n awg='🔴 не определён'\n for unit in ('amneziawg-quick@awg0.service','awg-quick@awg0.service'):\n  r=run('systemctl','is-active',unit)\n  if r.returncode==0:awg='🟢 '+r.stdout.strip();break\n return f'🖥 <b>NOVA Server</b>\\n\\n🤖 Telegram: <b>{"🟢 работает" if status(SERVICE) else "🔴 остановлен"}</b>\\n🔐 AWG: <b>{awg}</b>\\n📁 awg0.conf: <b>{"OK" if CONF.exists() else "не найден"}</b>'\n\ndef admin_users(chat):\n c=db();rows=c.execute('SELECT telegram_id,username,client_id,expires,active FROM telegram_subscriptions ORDER BY expires DESC LIMIT 30').fetchall();c.close()\n if not rows:return send_markup(chat,'👥 Пользователей пока нет.',admin_menu())\n lines=['👥 <b>Пользователи NOVA</b>']\n for r in rows:\n  ok=bool(r['active']) and r['expires']>int(time.time())\n  lines.append(f'<code>{r["telegram_id"]}</code> · @{r["username"] or "—"} · VPN #{r["client_id"]} · {"🟢" if ok else "🔴"} до {fmt(r["expires"])}')\n send_markup(chat,'\\n'.join(lines),admin_menu())\n\ndef admin_stats(chat):\n c=db();total=c.execute('SELECT COUNT(*) FROM telegram_subscriptions').fetchone()[0];active=c.execute('SELECT COUNT(*) FROM telegram_subscriptions WHERE active=1 AND expires>?',(int(time.time()),)).fetchone()[0];c.close();send_markup(chat,f'📊 <b>Статистика NOVA</b>\\n\\n👥 Всего: <b>{total}</b>\\n🟢 Активных: <b>{active}</b>\\n🔴 Истёкших: <b>{total-active}</b>',admin_menu())\n\ndef restart_awg(chat):\n for unit in ('amneziawg-quick@awg0.service','awg-quick@awg0.service'):\n  r=run('systemctl','restart',unit)\n  if r.returncode==0:return send_markup(chat,'✅ AWG перезапущен.',admin_menu())\n send_markup(chat,'❌ Не удалось перезапустить AWG.',admin_menu())\n\n"""
s=s.replace(marker,helpers+marker,1)
a=s.find('def process(u):'); b=s.find('def loop():',a)
if a<0 or b<0: raise SystemExit('source dispatcher markers not found')
proc="""def process(u):\n if 'callback_query' in u:\n  q=u['callback_query'];uid=q['from']['id'];chat=q['message']['chat']['id'];data=q.get('data','');username=q['from'].get('username','')\n  tg('answerCallbackQuery',{'callback_query_id':q['id']})\n  if not allowed(uid):return send(chat,'⛔ Доступ запрещён.',False)\n  if data=='get':deliver(chat,uid,username)\n  elif data=='my':show_my(chat,uid)\n  elif data=='conf':send_conf(chat,uid)\n  elif data=='qr':send_qr(chat,uid)\n  elif data=='renew':renew(chat,uid,username)\n  elif data=='status':send(chat,server_status(),True)\n  elif data=='help':send(chat,'🆘 <b>NOVA VPN</b>\\n\\n🔐 Получить VPN — создать профиль.\\n📱 Мой VPN — срок, IP и статус.\\n📄 Конфиг — получить .conf.\\n📲 QR-код — получить QR.\\n♻️ Продлить — добавить срок.\\n📊 Статус — состояние сервера.\\n\\nДля подключения используйте AmneziaVPN и импортируйте .conf или QR.',True)\n  elif data=='admin' and admin(uid):send_markup(chat,'🛠 <b>Панель администратора</b>\\n\\nВыберите действие:',admin_menu())\n  elif data=='users' and admin(uid):admin_users(chat)\n  elif data=='stats' and admin(uid):admin_stats(chat)\n  elif data=='server' and admin(uid):send_markup(chat,server_status(),admin_menu())\n  elif data=='awg_restart' and admin(uid):restart_awg(chat)\n  elif data=='home':send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nВыберите действие:',True)\n  return\n if 'message' in u:\n  m=u['message'];uid=m['from']['id'];chat=m['chat']['id'];cmd=(m.get('text') or '').split()[0].lower();username=m['from'].get('username','')\n  if not allowed(uid):return send(chat,'⛔ Доступ запрещён.',False)\n  if cmd in ('/start','/help'):send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nУправление AmneziaWG 3.1 прямо из Telegram.\\n\\nВыберите действие:',True)\n  elif cmd in ('/vpn','/get'):deliver(chat,uid,username)\n  elif cmd in ('/myvpn','/my'):show_my(chat,uid)\n  elif cmd in ('/config','/conf'):send_conf(chat,uid)\n  elif cmd=='/qr':send_qr(chat,uid)\n  elif cmd=='/renew':renew(chat,uid,username)\n  elif cmd=='/status':send(chat,server_status(),True)\n  elif cmd=='/admin' and admin(uid):send_markup(chat,'🛠 <b>Панель администратора</b>\\n\\nВыберите действие:',admin_menu())\n  else:send(chat,'Используйте кнопки меню.',True)\n"""
s=s[:a]+proc+s[b:]
live.write_text(s)
PY
PY="$BASE/venv/bin/python"; [ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"
# Preserve existing Telegram configuration and database; only the bot source is replaced.
systemctl daemon-reload
systemctl restart "$SERVICE"
echo '=== NOVA Telegram FULL V2 installed ==='
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
