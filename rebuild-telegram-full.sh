#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
BASE=/opt/awg31-panel; FILE=$BASE/telegram_bot.py; SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Missing $FILE"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$FILE" "$BASE/backups/telegram_bot-before-full-$(date +%Y%m%d-%H%M%S).py"
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
# Main and admin keyboards.
a=s.index('def menu():'); b=s.index('def send(',a)
new='''def menu():
 return json.dumps({'inline_keyboard':[
  [{'text':'🔐 Получить VPN','callback_data':'get'}],
  [{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],
  [{'text':'📲 QR-код','callback_data':'qr'},{'text':'♻️ Продлить','callback_data':'renew'}],
  [{'text':'📊 Статус','callback_data':'status'},{'text':'🆘 Помощь','callback_data':'help'}],
  [{'text':'🛠 Админ-панель','callback_data':'admin'}]
 ]},ensure_ascii=False)

def admin_menu():
 return json.dumps({'inline_keyboard':[
  [{'text':'👥 Пользователи','callback_data':'users'},{'text':'📊 Статистика','callback_data':'stats'}],
  [{'text':'🖥 Сервер','callback_data':'server'},{'text':'🔄 Перезапуск AWG','callback_data':'awg_restart'}],
  [{'text':'⬅️ Главное меню','callback_data':'home'}]
 ]},ensure_ascii=False)

def send_markup(chat,text,markup):
 tg('sendMessage',{'chat_id':chat,'text':text,'parse_mode':'HTML','reply_markup':markup})

'''
s=s[:a]+new+s[b:]
# User/admin helpers.
a=s.index('def deliver(')
helpers='''def send_conf(chat,uid):
 s=subscription(uid)
 if not s: return send(chat,'📄 Сначала получите VPN-профиль.',True)
 try:
  multipart('sendDocument',{'chat_id':chat,'caption':'📄 Конфигурация AmneziaWG 3.1'},{'document':('NOVA-'+str(s['client_id'])+'.conf',conf_bytes(s['client_id']),'text/plain')})
 except Exception: send(chat,'❌ Не удалось получить конфигурацию.',True)

def send_qr(chat,uid):
 s=subscription(uid)
 if not s: return send(chat,'📲 Сначала получите VPN-профиль.',True)
 try:
  multipart('sendPhoto',{'chat_id':chat,'caption':'📲 QR-код AmneziaWG 3.1'},{'photo':('NOVA-'+str(s['client_id'])+'.png',qr_bytes(s['client_id']),'image/png')})
 except Exception: send(chat,'❌ Не удалось получить QR-код.',True)

def server_status():
 awg='🔴 не определён'
 for unit in ('amneziawg-quick@awg0.service','awg-quick@awg0.service'):
  r=run('systemctl','is-active',unit)
  if r.returncode==0: awg='🟢 '+r.stdout.strip(); break
 return f'🖥 <b>NOVA Server</b>\\n\\n🤖 Telegram: <b>{"🟢 работает" if status(SERVICE) else "🔴 остановлен"}</b>\\n🔐 AWG: <b>{awg}</b>\\n📁 awg0.conf: <b>{"OK" if CONF.exists() else "не найден"}</b>'

def admin_users(chat):
 c=db(); rows=c.execute('SELECT telegram_id,username,client_id,expires,active FROM telegram_subscriptions ORDER BY expires DESC LIMIT 30').fetchall(); c.close()
 if not rows: return send_markup(chat,'👥 Пользователей пока нет.',admin_menu())
 lines=['👥 <b>Пользователи NOVA</b>']
 for r in rows:
  ok=bool(r['active']) and r['expires']>int(time.time())
  lines.append(f'<code>{r["telegram_id"]}</code> · @{r["username"] or "—"} · VPN #{r["client_id"]} · {"🟢" if ok else "🔴"} до {fmt(r["expires"])}')
 send_markup(chat,'\\n'.join(lines),admin_menu())

def admin_stats(chat):
 c=db(); total=c.execute('SELECT COUNT(*) FROM telegram_subscriptions').fetchone()[0]; active=c.execute('SELECT COUNT(*) FROM telegram_subscriptions WHERE active=1 AND expires>?',(int(time.time()),)).fetchone()[0]; c.close()
 send_markup(chat,f'📊 <b>Статистика NOVA</b>\\n\\n👥 Всего: <b>{total}</b>\\n🟢 Активных: <b>{active}</b>\\n🔴 Истёкших: <b>{total-active}</b>',admin_menu())

def restart_awg(chat):
 for unit in ('amneziawg-quick@awg0.service','awg-quick@awg0.service'):
  r=run('systemctl','restart',unit)
  if r.returncode==0: return send_markup(chat,'✅ AWG перезапущен.',admin_menu())
 send_markup(chat,'❌ Не удалось перезапустить AWG.',admin_menu())

'''
s=s[:a]+helpers+s[a:]
# Dispatcher.
a=s.index('def process(u):'); b=s.index('def loop():',a)
proc='''def process(u):
 if 'callback_query' in u:
  q=u['callback_query']; uid=q['from']['id']; chat=q['message']['chat']['id']; data=q.get('data',''); username=q['from'].get('username','')
  tg('answerCallbackQuery',{'callback_query_id':q['id']})
  if not allowed(uid): return send(chat,'⛔ Доступ запрещён.',False)
  if data=='get': deliver(chat,uid,username)
  elif data=='my': show_my(chat,uid)
  elif data=='conf': send_conf(chat,uid)
  elif data=='qr': send_qr(chat,uid)
  elif data=='renew': renew(chat,uid,username)
  elif data=='status': send(chat,server_status(),True)
  elif data=='help': send(chat,'🆘 <b>NOVA VPN</b>\\n\\n🔐 Получить VPN — создать профиль.\\n📱 Мой VPN — срок, IP и статус.\\n📄 Конфиг — получить .conf.\\n📲 QR-код — получить QR.\\n♻️ Продлить — добавить срок.\\n📊 Статус — состояние сервера.\\n\\nДля подключения используйте AmneziaVPN и импортируйте .conf или QR.',True)
  elif data=='admin' and admin(uid): send_markup(chat,'🛠 <b>Панель администратора</b>\\n\\nВыберите действие:',admin_menu())
  elif data=='users' and admin(uid): admin_users(chat)
  elif data=='stats' and admin(uid): admin_stats(chat)
  elif data=='server' and admin(uid): send_markup(chat,server_status(),admin_menu())
  elif data=='awg_restart' and admin(uid): restart_awg(chat)
  elif data=='home': send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nВыберите действие:',True)
  return
 if 'message' in u:
  m=u['message']; uid=m['from']['id']; chat=m['chat']['id']; cmd=(m.get('text') or '').split()[0].lower(); username=m['from'].get('username','')
  if not allowed(uid): return send(chat,'⛔ Доступ запрещён.',False)
  if cmd in ('/start','/help'): send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nУправление AmneziaWG 3.1 прямо из Telegram.\\n\\nВыберите действие:',True)
  elif cmd in ('/vpn','/get'): deliver(chat,uid,username)
  elif cmd in ('/myvpn','/my'): show_my(chat,uid)
  elif cmd in ('/config','/conf'): send_conf(chat,uid)
  elif cmd=='/qr': send_qr(chat,uid)
  elif cmd=='/renew': renew(chat,uid,username)
  elif cmd=='/status': send(chat,server_status(),True)
  elif cmd=='/admin' and admin(uid): send_markup(chat,'🛠 <b>Панель администратора</b>\\n\\nВыберите действие:',admin_menu())
  else: send(chat,'Используйте кнопки меню.',True)

'''
s=s[:a]+proc+s[b:]
p.write_text(s)
PY
PY=$BASE/venv/bin/python; [ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl daemon-reload
systemctl restart "$SERVICE"
echo '=== NOVA Telegram FULL BOT rebuilt ==='
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
