#!/usr/bin/env python3
"""NOVA Telegram welcome/menu layer for telegram_bot_v2."""
import html
import json
import telegram_bot_v2 as bot

ORIGINAL_PROCESS = bot.process


def welcome_menu(uid):
    rows = [
        [{'text': '🔐 Получить VPN', 'callback_data': 'get'}],
        [{'text': '📱 Мой VPN', 'callback_data': 'my'}, {'text': '♻️ Продлить', 'callback_data': 'renew'}],
        [{'text': '📖 Как подключиться', 'callback_data': 'help'}],
    ]
    if bot.base.admin(uid):
        rows.append([{'text': '🛠 Админ-панель', 'callback_data': 'admin_open'}])
    return json.dumps({'inline_keyboard': rows}, ensure_ascii=False)


def send_welcome(chat, user):
    first = html.escape((user.get('first_name') or user.get('username') or 'друг').strip())
    text = (
        f'🚀 <b>Добро пожаловать в NOVA VPN, {first}!</b>\n\n'
        '🛡 <b>Быстрый и защищённый доступ</b> на базе AmneziaWG 3.1.\n\n'
        'Здесь можно получить VPN-конфигурацию, увидеть срок доступа и продлить его — прямо в Telegram.\n\n'
        '👇 <b>Выберите действие:</b>'
    )
    bot.base.tg('sendMessage', {
        'chat_id': chat,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': welcome_menu(user.get('id', 0)),
    })


def process(u):
    if 'callback_query' in u:
        q = u['callback_query']
        uid = q['from']['id']
        chat = q['message']['chat']['id']
        data = q.get('data', '')
        if data == 'admin_open':
            bot.base.tg('answerCallbackQuery', {'callback_query_id': q['id']})
            if bot.base.admin(uid):
                bot.send_admin(chat, bot.status_text())
            else:
                bot.base.send(chat, '⛔ Только администратор.', False)
            return
        if data == 'welcome':
            bot.base.tg('answerCallbackQuery', {'callback_query_id': q['id']})
            if bot.base.allowed(uid):
                send_welcome(chat, q['from'])
            else:
                bot.base.send(chat, '⛔ Доступ запрещён.', False)
            return
    if 'message' in u:
        m = u['message']
        uid = m['from']['id']
        cmd = (m.get('text') or '').split()[0].lower()
        if cmd in ('/start', '/menu'):
            if bot.base.allowed(uid):
                send_welcome(m['chat']['id'], m['from'])
            else:
                bot.base.send(m['chat']['id'], '⛔ Доступ запрещён.', False)
            return
    ORIGINAL_PROCESS(u)


bot.process = process

if __name__ == '__main__':
    bot.loop()
