#!/usr/bin/env python3
"""Telegram delete flow for NOVA VPN subscriptions.

Loaded by telegram_runner before telegram_bot.loop(). It keeps the existing bot
implementation intact and adds a confirmation-based destructive action.
"""
import json
import time
import telegram_bot as bot

ORIGINAL_MENU = bot.menu
ORIGINAL_PROCESS = bot.process


def menu_with_delete():
    return json.dumps({
        'inline_keyboard': [
            [{'text': '🔐 Получить VPN', 'callback_data': 'get'}],
            [
                {'text': '📱 Мой VPN', 'callback_data': 'my'},
                {'text': '📄 Конфиг', 'callback_data': 'conf'},
            ],
            [
                {'text': '📲 QR-код', 'callback_data': 'qr'},
                {'text': '♻️ Продлить', 'callback_data': 'renew'},
            ],
            [{'text': '🗑 Удалить', 'callback_data': 'delete'}],
            [{'text': 'ℹ️ Помощь', 'callback_data': 'help'}],
        ]
    }, ensure_ascii=False)


def delete_subscription(uid):
    sub = bot.subscription(uid)
    if not sub:
        return False, 'VPN-профиль не найден.'
    client = bot.client_row(sub['client_id'])
    if not client:
        con = bot.db()
        con.execute('DELETE FROM telegram_subscriptions WHERE telegram_id=?', (uid,))
        con.commit()
        con.close()
        return True, 'Старый профиль удалён.'

    # Use the same authenticated panel endpoint as the existing web UI. This
    # creates the normal AWG backup and applies the deletion to awg0 safely.
    response = bot.panel_request(f"/clients/{client['id']}/delete", 'POST')
    if response.status_code >= 400:
        return False, 'Не удалось удалить peer из AmneziaWG.'

    con = bot.db()
    con.execute('DELETE FROM telegram_subscriptions WHERE telegram_id=?', (uid,))
    con.commit()
    con.close()
    return True, f"Профиль <b>{client['name']}</b> удалён."


def process_with_delete(update):
    if 'callback_query' not in update:
        return ORIGINAL_PROCESS(update)

    q = update['callback_query']
    uid = q['from']['id']
    chat = q['message']['chat']['id']
    data = q.get('data', '')
    bot.tg('answerCallbackQuery', {'callback_query_id': q['id']})

    if data not in ('delete', 'delete_confirm', 'delete_cancel'):
        # Extra convenience buttons added to the modern menu.
        if data == 'conf':
            sub = bot.subscription(uid)
            if not sub:
                bot.send(chat, '📄 У вас пока нет VPN-профиля.', True)
                return
            try:
                bot.multipart('sendDocument', {'chat_id': chat, 'caption': '📄 Конфигурация AmneziaWG'}, {'document': ('NOVA-'+str(sub['client_id'])+'.conf', bot.conf_bytes(sub['client_id']), 'text/plain')})
            except Exception:
                bot.send(chat, '❌ Не удалось получить конфигурацию.', True)
            return
        if data == 'qr':
            sub = bot.subscription(uid)
            if not sub:
                bot.send(chat, '📲 У вас пока нет VPN-профиля.', True)
                return
            try:
                bot.multipart('sendPhoto', {'chat_id': chat, 'caption': '📲 QR-код для подключения'}, {'photo': ('NOVA-'+str(sub['client_id'])+'.png', bot.qr_bytes(sub['client_id']), 'image/png')})
            except Exception:
                bot.send(chat, '❌ Не удалось получить QR-код.', True)
            return
        return ORIGINAL_PROCESS(update)

    if not bot.allowed(uid):
        bot.send(chat, '⛔ Доступ запрещён.', False)
        return

    if data == 'delete':
        sub = bot.subscription(uid)
        if not sub:
            bot.send(chat, '🗑 <b>Удаление</b>\n\nУ вас нет активного VPN-профиля.', True)
            return
        client = bot.client_row(sub['client_id'])
        name = client['name'] if client else 'NOVA VPN'
        address = client['address'] if client else '-'
        bot.tg('sendMessage', {
            'chat_id': chat,
            'text': (
                '⚠️ <b>Удаление VPN</b>\n\n'
                f'Профиль: <b>{name}</b>\n'
                f'IP: <code>{address}</code>\n'
                f'Срок: <b>{bot.fmt(sub["expires"])}</b>\n\n'
                'Это отключит peer и удалит VPN-профиль.\n'
                '<b>Продолжить?</b>'
            ),
            'parse_mode': 'HTML',
            'reply_markup': json.dumps({'inline_keyboard': [[
                {'text': '❌ Отмена', 'callback_data': 'delete_cancel'},
                {'text': '🗑 ДА, УДАЛИТЬ', 'callback_data': 'delete_confirm'},
            ]]}, ensure_ascii=False)
        })
        return

    if data == 'delete_cancel':
        bot.send(chat, '↩️ Удаление отменено.', True)
        return

    ok, message = delete_subscription(uid)
    if ok:
        bot.send(chat, '🗑 <b>VPN удалён</b>\n\n' + message + '\n\nМожно получить новый профиль в любой момент.', True)
    else:
        bot.send(chat, '❌ <b>Удаление не выполнено</b>\n\n' + message, True)


bot.menu = menu_with_delete
bot.process = process_with_delete
