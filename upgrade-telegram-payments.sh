#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
BASE=/opt/awg31-panel
FILE="$BASE/telegram_bot.py"
ENV=/etc/awg31-panel/telegram.env
SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Missing $FILE"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$FILE" "$BASE/backups/telegram_bot-before-payments-$(date +%Y%m%d-%H%M%S).py"
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
# Add tariff/payment configuration without storing secrets in GitHub.
anchor="SERVICE='awgpanel-telegram.service';DB=BASE/'panel.db';CONF=Path('/etc/amnezia/amneziawg/awg0.conf')"
if anchor in s and 'TARIFFS =' not in s:
 s=s.replace(anchor, anchor+"\nTARIFFS={'30':(350,30),'90':(900,90),'180':(1600,180),'365':(3000,365)}")
# Replace the menu with a complete customer menu. Existing admin command remains available.
start=s.find('def menu():')
end=s.find('def send(',start)
if start>=0 and end>=0:
 menu='''def menu():\n return json.dumps({'inline_keyboard':[[{'text':'🔐 Получить VPN','callback_data':'get'}],[{'text':'📱 Мой VPN','callback_data':'my'},{'text':'📄 Конфиг','callback_data':'conf'}],[{'text':'📲 QR-код','callback_data':'qr'},{'text':'🗑 Удалить конфиг','callback_data':'delete'}],[{'text':'💳 Оплатить VPN','callback_data':'pay'}],[{'text':'♻️ Продлить','callback_data':'renew'},{'text':'🆘 Помощь','callback_data':'help'}]]},ensure_ascii=False)\n\ndef pay_menu():\n return json.dumps({'inline_keyboard':[[{'text':'30 дней — 350 ₽','callback_data':'tariff_30'},{'text':'90 дней — 900 ₽','callback_data':'tariff_90'}],[{'text':'180 дней — 1 600 ₽','callback_data':'tariff_180'},{'text':'365 дней — 3 000 ₽','callback_data':'tariff_365'}],[{'text':'🇷🇺 СБП','callback_data':'pay_sbp'},{'text':'💵 USDT TRC20','callback_data':'pay_usdt'}],[{'text':'⬅️ Назад','callback_data':'home'}]]},ensure_ascii=False)\n\ndef confirm_delete_menu():\n return json.dumps({'inline_keyboard':[[{'text':'⚠️ Да, удалить','callback_data':'delete_yes'},{'text':'Отмена','callback_data':'home'}]]},ensure_ascii=False)\n'''
 s=s[:start]+menu+s[end:]
# Insert helpers before deliver.
marker='def deliver(chat,uid,username):'
if marker in s and 'def delete_config(' not in s:
 helpers='''def delete_config(chat,uid):\n s=subscription(uid)\n if not s:return send(chat,'🗑 У вас нет VPN-конфига.',True)\n c=client_row(s['client_id'])\n if not c:return send(chat,'❌ Профиль не найден.',True)\n try:\n  ok=set_peer_enabled(c['public_key'],False,s['peer_block'])\n  if not ok: return send(chat,'❌ Не удалось отключить конфиг.',True)\n  dbx=db();dbx.execute('UPDATE telegram_subscriptions SET active=0 WHERE telegram_id=?',(uid,));dbx.commit();dbx.close()\n  send(chat,'🗑 <b>Конфиг удалён.</b>\\nVPN-профиль отключён на сервере. При необходимости можно оформить новый.',True)\n except Exception: send(chat,'❌ Ошибка удаления конфига.',True)\n\ndef payment_info(chat,method=''):\n e=env()\n if method=='usdt':\n  addr=e.get('USDT_ADDRESS','')\n  if not addr:return send(chat,'💵 <b>USDT TRC20</b>\\n\\nКошелёк ещё не настроен администратором.\\nЗапустите create-usdt-trc20-wallet.sh на VPS и укажите адрес в telegram.env.',True)\n  return send(chat,f'💵 <b>Оплата USDT TRC20</b>\\n\\nАдрес: <code>{addr}</code>\\n\\n⚠️ Отправляйте только USDT в сети TRON (TRC20). После перевода сохраните TXID и передайте его администратору для подтверждения.',True)\n if method=='sbp':\n  url=e.get('SBP_PAYMENT_URL','')\n  if not url:return send(chat,'🇷🇺 <b>СБП</b>\\n\\nСсылка оплаты ещё не настроена. Администратору нужно указать SBP_PAYMENT_URL в /etc/awg31-panel/telegram.env.',True)\n  return tg('sendMessage',{'chat_id':chat,'text':'🇷🇺 <b>Оплата через СБП</b>\\n\\nНажмите кнопку ниже для оплаты.', 'parse_mode':'HTML','reply_markup':json.dumps({'inline_keyboard':[[{'text':'💳 Перейти к оплате СБП','url':url}],[{'text':'⬅️ Назад','callback_data':'pay'}]]},ensure_ascii=False)})\n return send(chat,'💳 <b>Выберите тариф</b>\\n\\n30 дней — 350 ₽\\n90 дней — 900 ₽\\n180 дней — 1 600 ₽\\n365 дней — 3 000 ₽',True)\n'''
 s=s.replace(marker,helpers+marker)
# Extend callback dispatcher without depending on formatting of old handler.
needle="if data=='get':deliver(chat,uid,q['from'].get('username',''))"
if needle in s and "elif data=='delete'" not in s:
 repl=needle+"\n  elif data=='my':show_my(chat,uid)\n  elif data=='conf':send_conf(chat,uid) if 'send_conf' in globals() else send(chat,'📄 Получите VPN-профиль сначала.',True)\n  elif data=='delete':send(chat,'⚠️ <b>Удалить конфиг?</b>\\nЭто отключит VPN-профиль на сервере.',False) if False else tg('sendMessage',{'chat_id':chat,'text':'⚠️ <b>Удалить конфиг?</b>\\nЭто отключит VPN-профиль на сервере.','parse_mode':'HTML','reply_markup':confirm_delete_menu()})\n  elif data=='delete_yes':delete_config(chat,uid)\n  elif data=='pay':payment_info(chat)\n  elif data=='pay_sbp':payment_info(chat,'sbp')\n  elif data=='pay_usdt':payment_info(chat,'usdt')\n  elif data.startswith('tariff_'):\n   days=data.split('_',1)[1];price,_=TARIFFS.get(days,(0,0));send(chat,f'💳 <b>Тариф: {days} дней</b>\\nСтоимость: <b>{price} ₽</b>\\n\\nВыберите способ оплаты:',True)"
 s=s.replace(needle,repl,1)
p.write_text(s)
PY
PY="$BASE/venv/bin/python"; [ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"
systemctl restart "$SERVICE"
echo 'Telegram payment/delete update installed.'
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
