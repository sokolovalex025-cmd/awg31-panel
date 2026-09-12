#!/usr/bin/env python3
"""NOVA Telegram tariffs and crypto-payment helpers.

Payments are transfer-to-wallet based. Verification can be added later through a
provider/API; no private keys are ever stored by this module.
"""
import html
import os
import urllib.parse
from pathlib import Path

ENV = Path('/etc/awg31-panel/telegram.env')

TARIFFS = {
    '30':  {'days': 30,  'rub': 350,  'title': '🟢 1 месяц'},
    '90':  {'days': 90,  'rub': 900,  'title': '🔵 3 месяца'},
    '180': {'days': 180, 'rub': 1600, 'title': '🟣 6 месяцев'},
    '365': {'days': 365, 'rub': 3000, 'title': '🟠 1 год'},
}

def env():
    out = {}
    try:
        for line in ENV.read_text(errors='replace').splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                out[k] = v.strip().strip('"')
    except Exception:
        pass
    return out

def wallet():
    e = env()
    return e.get('CRYPTO_WALLET_ADDRESS', '').strip()

def network():
    return env().get('CRYPTO_NETWORK', 'USDT TRC20').strip() or 'USDT TRC20'

def pay_menu():
    rows = []
    for key in ('30', '90', '180', '365'):
        t = TARIFFS[key]
        rows.append([{'text': f'{t["title"]} — {t["rub"]} ₽', 'callback_data': 'pay_' + key}])
    rows.append([{'text': '⬅️ Назад', 'callback_data': 'home'}])
    import json
    return json.dumps({'inline_keyboard': rows}, ensure_ascii=False)

def payment_text(key):
    t = TARIFFS.get(str(key))
    if not t:
        return '❌ Тариф не найден.'
    w = wallet()
    net = html.escape(network())
    if not w:
        return (f'💳 <b>{html.escape(t["title"])} — {t["rub"]} ₽</b>\n\n'
                f'Сеть: <b>{net}</b>\n\n'
                '⚠️ Кошелёк администратора ещё не настроен.\n'
                'Добавьте <code>CRYPTO_WALLET_ADDRESS</code> в telegram.env.')
    enc = html.escape(w)
    return (f'💳 <b>{html.escape(t["title"])} — {t["rub"]} ₽</b>\n\n'
            f'Срок: <b>{t["days"]} дней</b>\n'
            f'Сеть: <b>{net}</b>\n\n'
            'Отправьте оплату на кошелёк:\n'
            f'<code>{enc}</code>\n\n'
            'После перевода сохраните TXID и отправьте его администратору для подтверждения.\n'
            '⚠️ Отправляйте только поддерживаемый актив и сеть.')
