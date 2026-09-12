#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
FILE=$BASE/telegram_bot.py
SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Не найден $FILE"; exit 1; }
mkdir -p "$BASE/backups"
TS=$(date +%Y%m%d-%H%M%S)
cp -a "$FILE" "$BASE/backups/telegram_bot-before-enhance-$TS.py"
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
start=s.find('def menu():')
end=s.find('def send(', start)
if start<0 or end<0: raise SystemExit('Не найден блок menu/send')
new='''def menu():
 return json.dumps({'inline_keyboard':[
  [{'text':'🔐 Получить VPN','callback_data':'get'}],
  [{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],
  [{'text':'📲 QR-код','callback_data':'qr'},{'text':'♻️ Продлить','callback_data':'renew'}],
  [{'text':'📊 Статус','callback_data':'status'},{'text':'🆘 Помощь','callback_data':'help'}]
 ]},ensure_ascii=False)

def admin_menu():
 return json.dumps({'inline_keyboard':[
  [{'text':'👥 Пользователи','callback_data':'users'},{'text':'📊 Статистика','callback_data':'stats'}],
  [{'text':'🖥 Сервер','callback_data':'server'},{'text':'🔄 Перезапуск AWG','callback_data':'awg_restart'}],
  [{'text':'⬅️ Главное меню','callback_data':'home'}]
 ]},ensure_ascii=False)

'''
s=s[:start]+new+s[end:]
start=s.find('def process(u):')
end=s.find('def loop():', start)
if start<0 or end<0: raise SystemExit('Не найден блок process/loop')
new='''def server_status():
 awg='unknown'
 for unit in ('amneziawg-quick@awg0.service','awg-quick@awg0.service'):
  r=run('systemctl','is-active',unit)
  if r.returncode==0:
   awg=r.stdout.strip(); break
 bot='🟢 работает' if status(SERVICE) else '🔴 остановлен'
 return f'🖥 <b>NOVA Server</b>\\n\\n🤖 Telegram: <b>{bot}</b>\\n🔐 AWG: <b>{awg}</b>\\n📁 Конфиг: <b>{"OK" if CONF.exists() else "не найден"}</b>'

def admin_users(chat):
 c=db();rows=c.execute('SELECT telegram_id,username,client_id,expires,active FROM telegram_subscriptions ORDER BY expires DESC LIMIT 20').fetchall();c.close()
 if not rows:return send(chat,'👥 Пользователей пока нет.','admin')
 lines=['👥 <b>Последние пользователи</b>']
 for r in rows:
  ok=bool(r['active']) and r['expires']>int(time.time())
  lines.append(f'\\n<code>{r["telegram_id"]}</code> · {r["username"] or "—"} · VPN #{r["client_id"]}\\n{"🟢" if ok else "🔴"} до {fmt(r["expires"])}')
 send(chat,'\\n'.join(lines),'admin')

def admin_stats(chat):
 c=db();total=c.execute('SELECT COUNT(*) FROM telegram_subscriptions').fetchone()[0];active=c.execute('SELECT COUNT(*) FROM telegram_subscriptions WHERE active=1 AND expires>?',(int(time.time()),)).fetchone()[0];c.close();send(chat,f'📊 <b>Статистика</b>\\n\\n👥 Всего: <b>{total}</b>\\n🟢 Активных: <b>{active}</b>\\n🔴 Истёкших: <b>{total-active}</b>','admin')

def process(u):
 if 'callback_query' in u:
  q=u['callback_query'];uid=q['from']['id'];chat=q['message']['chat']['id'];data=q.get('data','');tg('answerCallbackQuery',{'callback_query_id':q['id']})
  if not allowed(uid): send(chat,'⛔ Доступ запрещён.','none'); return
  if data=='get': deliver(chat,uid,q['from'].get('username',''))
  elif data=='my': show_my(chat,uid)
  elif data=='conf': send_conf(chat,uid)
  elif data=='qr': send_qr(chat,uid)
  elif data=='renew': renew(chat,uid,q['from'].get('username',''))
  elif data=='status': send(chat,server_status())
  elif data=='help': send(chat,'🆘 <b>Помощь</b>\\n\\n🔐 Получить VPN — создать профиль.\\n📱 Мой VPN — срок и IP.\\n📄 Конфиг — получить конфигурацию.\\n📲 QR-код — получить QR.\\n♻️ Продлить — добавить срок.\\n📊 Статус — состояние сервера.')
  elif data=='home': send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nВыберите действие:')
  elif data=='users' and admin(uid): admin_users(chat)
  elif data=='stats' and admin(uid): admin_stats(chat)
  elif data=='server' and admin(uid): send(chat,server_status(),'admin')
  elif data=='awg_restart' and admin(uid):
   r=run('systemctl','restart','amneziawg-quick@awg0.service')
   if r.returncode!=0: r=run('systemctl','restart','awg-quick@awg0.service')
   send(chat,'🔄 AWG перезапущен.' if r.returncode==0 else '❌ Не удалось перезапустить AWG.','admin')
  return
 if 'message' in u:
  m=u['message'];uid=m['from']['id'];chat=m['chat']['id'];cmd=(m.get('text') or '').split()[0].lower()
  if not allowed(uid): send(chat,'⛔ Доступ запрещён.','none'); return
  if cmd in ('/start','/help'): send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nУправление AmneziaWG 3.1.\\n\\nВыберите действие:')
  elif cmd in ('/vpn','/get'): deliver(chat,uid,m['from'].get('username',''))
  elif cmd in ('/myvpn','/my'): show_my(chat,uid)
  elif cmd in ('/config','/conf'): send_conf(chat,uid)
  elif cmd=='/qr': send_qr(chat,uid)
  elif cmd=='/renew': renew(chat,uid,m['from'].get('username',''))
  elif cmd=='/status': send(chat,server_status())
  elif cmd=='/admin' and admin(uid): send(chat,'🛠 <b>Панель администратора</b>\\n\\nВыберите действие:','admin')
  else: send(chat,'Используйте кнопки меню.')

'''
s=s[:start]+new+s[end:]
p.write_text(s)
PY
PY=$BASE/venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl daemon-reload
if [ -s /etc/awg31-panel/telegram.env ]; then systemctl enable --now "$SERVICE"; systemctl restart "$SERVICE"; fi
echo '=== Telegram bot enhanced ==='
echo "File: $FILE"
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
