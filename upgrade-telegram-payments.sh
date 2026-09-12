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
cp -a "$FILE" "$BASE/backups/telegram_bot-before-payments-$(date +%Y%m%d-%H%M%S).py"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
curl -fsSL --retry 3 "$REPO" -o "$TMP"
python3 - "$FILE" "$TMP" <<'PY'
from pathlib import Path
import sys
live=Path(sys.argv[1]); source=Path(sys.argv[2]); s=source.read_text()
anchor="SERVICE='awgpanel-telegram.service';DB=BASE/'panel.db';CONF=Path('/etc/amnezia/amneziawg/awg0.conf')"
if 'TARIFFS=' not in s:
 s=s.replace(anchor, anchor+"\nTARIFFS={'30':(350,30),'90':(900,90),'180':(1600,180),'365':(3000,365)}")
start=s.find('def menu():'); end=s.find('def send(',start)
if start<0 or end<0: raise SystemExit('menu markers not found')
menu='''def menu():\n return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],[{'text':'📲 QR-код','callback_data':'qr'},{'text':'🗑 Удалить конфиг','callback_data':'delete'}],[{'text':'💳 Оплатить VPN','callback_data':'pay'}],[{'text':'♻️ Продлить','callback_data':'renew'},{'text':'🆘 Помощь','callback_data':'help'}]]},ensure_ascii=False)\n\ndef pay_menu():\n return json.dumps({'inline_keyboard':[[{'text':'30 дней — 350 ₽','callback_data':'tariff_30'},{'text':'90 дней — 900 ₽','callback_data':'tariff_90'}],[{'text':'180 дней — 1 600 ₽','callback_data':'tariff_180'},{'text':'365 дней — 3 000 ₽','callback_data':'tariff_365'}],[{'text':'🇷🇺 СБП','callback_data':'pay_sbp'},{'text':'💵 USDT TRC20','callback_data':'pay_usdt'}],[{'text':'⬅️ Назад','callback_data':'home'}]]},ensure_ascii=False)\n\ndef confirm_delete_menu():\n return json.dumps({'inline_keyboard':[[{'text':'⚠️ Да, удалить','callback_data':'delete_yes'},{'text':'Отмена','callback_data':'home'}]]},ensure_ascii=False)\n'''
s=s[:start]+menu+s[end:]
marker='def deliver(chat,uid,username):'
if marker not in s: raise SystemExit('deliver marker not found')
helpers='''def send_conf(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'📄 Сначала получите VPN-профиль.',True)\n try: multipart('sendDocument',{'chat_id':chat,'caption':'📄 Конфигурация AmneziaWG 3.1'},{'document':('NOVA-'+str(s['client_id'])+'.conf',conf_bytes(s['client_id']),'text/plain')})\n except Exception: send(chat,'❌ Не удалось получить конфигурацию.',True)\n\ndef send_qr(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'📲 Сначала получите VPN-профиль.',True)\n try: multipart('sendPhoto',{'chat_id':chat,'caption':'📲 QR-код AmneziaWG 3.1'},{'photo':('NOVA-'+str(s['client_id'])+'.png',qr_bytes(s['client_id']),'image/png')})\n except Exception: send(chat,'❌ Не удалось получить QR-код.',True)\n\ndef delete_config(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'🗑 У вас нет VPN-конфига.',True)\n c=client_row(s['client_id'])\n if not c:return send(chat,'❌ Профиль не найден.',True)\n try:\n  if not set_peer_enabled(c['public_key'],False,s['peer_block']):return send(chat,'❌ Не удалось отключить конфиг.',True)\n  cx=db();cx.execute('UPDATE telegram_subscriptions SET active=0 WHERE telegram_id=?',(uid,));cx.commit();cx.close()\n  send(chat,'🗑 <b>Конфиг удалён.</b>\\nVPN-профиль отключён на сервере. Новый можно получить через «🔐 Получить VPN».',True)\n except Exception: send(chat,'❌ Ошибка удаления конфига.',True)\n\ndef payment_info(chat,method=''):\n e=env()\n if method=='usdt':\n  addr=e.get('USDT_ADDRESS','')\n  if not addr:return send(chat,'💵 <b>USDT TRC20</b>\\n\\nКошелёк ещё не настроен. Администратор может создать его скриптом create-usdt-trc20-wallet.sh.',True)\n  return send(chat,f'💵 <b>USDT TRC20</b>\\n\\nАдрес: <code>{addr}</code>\\n\\n⚠️ Только сеть TRON (TRC20). Автоматическое зачисление будет включено после настройки проверки транзакций.',True)\n if method=='sbp':\n  url=e.get('SBP_PAYMENT_URL','')\n  if not url:return send(chat,'🇷🇺 <b>СБП</b>\\n\\nСсылка оплаты ещё не настроена. Укажите SBP_PAYMENT_URL в /etc/awg31-panel/telegram.env.',True)\n  return tg('sendMessage',{'chat_id':chat,'text':'🇷🇺 <b>Оплата через СБП</b>\\n\\nНажмите кнопку ниже.', 'parse_mode':'HTML','reply_markup':json.dumps({'inline_keyboard':[[{'text':'💳 Перейти к оплате СБП','url':url}],[{'text':'⬅️ Назад','callback_data':'pay'}]]},ensure_ascii=False)})\n return tg('sendMessage',{'chat_id':chat,'text':'💳 <b>Выберите тариф</b>\\n\\n30 дней — 350 ₽\\n90 дней — 900 ₽\\n180 дней — 1 600 ₽\\n365 дней — 3 000 ₽', 'parse_mode':'HTML','reply_markup':pay_menu()})\n'''
s=s.replace(marker,helpers+marker,1)
a=s.find('def process(u):'); b=s.find('def loop():',a)
if a<0 or b<0: raise SystemExit('dispatcher markers not found')
proc='''def process(u):\n if 'callback_query' in u:\n  q=u['callback_query'];uid=q['from']['id'];chat=q['message']['chat']['id'];data=q.get('data','');username=q['from'].get('username','')\n  tg('answerCallbackQuery',{'callback_query_id':q['id']})\n  if not allowed(uid):return send(chat,'⛔ Доступ запрещён.',False)\n  if data=='get':deliver(chat,uid,username)\n  elif data=='my':show_my(chat,uid)\n  elif data=='conf':send_conf(chat,uid)\n  elif data=='qr':send_qr(chat,uid)\n  elif data=='delete':tg('sendMessage',{'chat_id':chat,'text':'⚠️ <b>Удалить конфиг?</b>\\nЭто отключит VPN-профиль на сервере.','parse_mode':'HTML','reply_markup':confirm_delete_menu()})\n  elif data=='delete_yes':delete_config(chat,uid)\n  elif data=='pay':payment_info(chat)\n  elif data.startswith('tariff_'):\n   days=data.split('_',1)[1];price,_=TARIFFS.get(days,(0,0));tg('sendMessage',{'chat_id':chat,'text':f'💳 <b>Тариф: {days} дней</b>\\nСтоимость: <b>{price} ₽</b>\\n\\nВыберите способ оплаты:', 'parse_mode':'HTML','reply_markup':json.dumps({'inline_keyboard':[[{'text':'🇷🇺 СБП','callback_data':'pay_sbp'},{'text':'💵 USDT TRC20','callback_data':'pay_usdt'}],[{'text':'⬅️ Тарифы','callback_data':'pay'}]]},ensure_ascii=False)})\n  elif data=='pay_sbp':payment_info(chat,'sbp')\n  elif data=='pay_usdt':payment_info(chat,'usdt')\n  elif data=='renew':renew(chat,uid,username)\n  elif data=='status':send(chat,'📊 Telegram Bot работает.',True)\n  elif data=='help':send(chat,'🆘 <b>NOVA VPN</b>\\n\\n🔐 Получить VPN — создать профиль.\\n📱 Мой VPN — срок и статус.\\n📄 Конфиг — получить .conf.\\n📲 QR-код — получить QR.\\n🗑 Удалить конфиг — отключить профиль.\\n💳 Оплатить VPN — тарифы и способы оплаты.\\n♻️ Продлить — продлить действующий профиль.',True)\n  elif data=='home':send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nВыберите действие:',True)\n  return\n if 'message' in u:\n  m=u['message'];uid=m['from']['id'];chat=m['chat']['id'];cmd=(m.get('text') or '').split()[0].lower();username=m['from'].get('username','')\n  if not allowed(uid):return send(chat,'⛔ Доступ запрещён.',False)\n  if cmd in ('/start','/help'):send(chat,'🚀 <b>NOVA Network Control Center</b>\\n\\nУправление AmneziaWG 3.1 прямо из Telegram.\\n\\nВыберите действие:',True)\n  elif cmd in ('/vpn','/get'):deliver(chat,uid,username)\n  elif cmd in ('/myvpn','/my'):show_my(chat,uid)\n  elif cmd in ('/config','/conf'):send_conf(chat,uid)\n  elif cmd=='/qr':send_qr(chat,uid)\n  elif cmd=='/delete':delete_config(chat,uid)\n  elif cmd=='/pay':payment_info(chat)\n  elif cmd=='/renew':renew(chat,uid,username)\n  elif cmd=='/status':send(chat,'📊 Telegram Bot работает.',True)\n  else:send(chat,'Используйте кнопки меню.',True)\n'''
s=s[:a]+proc+s[b:]
live.write_text(s)
PY
PY="$BASE/venv/bin/python"; [ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl daemon-reload
systemctl restart "$SERVICE"
echo '=== NOVA Telegram payments/delete installed ==='
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
