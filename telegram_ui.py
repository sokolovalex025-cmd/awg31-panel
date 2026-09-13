#!/usr/bin/env python3
"""Telegram management UI for NOVA panel with persistent settings."""
import json
import sqlite3
import urllib.request
from flask import request, render_template_string
import nova11

DB = '/opt/awg31-panel/panel.db'

def db_init():
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)')
    con.commit()
    con.close()

def setting_get(key, default=''):
    db_init()
    con = sqlite3.connect(DB)
    row = con.execute('SELECT v FROM settings WHERE k=?', (key,)).fetchone()
    con.close()
    return row[0] if row else default

def setting_set(key, value):
    db_init()
    con = sqlite3.connect(DB)
    con.execute('INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (key, value))
    con.commit()
    con.close()

def telegram_getme(token):
    req = urllib.request.Request('https://api.telegram.org/bot' + token + '/getMe', headers={'User-Agent':'NOVA-AWG-Panel/1.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode('utf-8'))
    if not data.get('ok'):
        raise RuntimeError('Telegram API отклонил токен')
    return data.get('result', {})

def install():
    core = nova11.core
    db_init()
    if 'telegram' not in core.app.view_functions:
        @core.app.route('/telegram', methods=['GET', 'POST'])
        def telegram_page():
            message = ''
            good = False
            token = setting_get('telegram_token')
            command = setting_get('telegram_command', '/start') or '/start'
            admins = setting_get('telegram_admins')
            bot_name = setting_get('telegram_bot_name')
            if request.method == 'POST':
                action = request.form.get('action', '')
                if action == 'save':
                    new_token = request.form.get('token', '').strip()
                    if new_token and not new_token.startswith('••••'):
                        token = new_token
                        setting_set('telegram_token', token)
                    command = request.form.get('command', '/start').strip() or '/start'
                    admins = request.form.get('admins', '').strip()
                    setting_set('telegram_command', command)
                    setting_set('telegram_admins', admins)
                    message = 'Настройки Telegram сохранены.'
                    good = True
                elif action == 'test':
                    if not token:
                        message = 'Сначала сохраните Bot Token.'
                    else:
                        try:
                            info = telegram_getme(token)
                            bot_name = info.get('username') or info.get('first_name') or 'Telegram bot'
                            setting_set('telegram_bot_name', bot_name)
                            message = 'Соединение успешно: @' + info.get('username', bot_name)
                            good = True
                        except Exception as exc:
                            message = 'Ошибка подключения Telegram: ' + str(exc)
            masked = ('••••••••' + token[-4:]) if token and len(token) > 4 else ('••••••••' if token else '')
            body = render_template_string(r'''
<div class="hero"><div><div class="eyebrow">TELEGRAM CONTROL</div><h1>Telegram</h1><p>Управление Telegram-ботом, выдачей VPN-доступа и уведомлениями.</p></div></div>
{% if message %}<div class="notice {{ 'good' if good else 'badbox' }}">{{ message }}</div>{% endif %}
<div class="grid4">
  <div class="card metric"><div class="label">Статус бота</div><div class="value {{ 'ok' if token else 'warn' }}">{{ 'Настроен' if token else 'Не настроен' }}</div><div class="sub">{{ ('@' + bot_name) if bot_name else ('Токен сохранён' if token else 'Токен ещё не добавлен') }}</div></div>
  <div class="card metric"><div class="label">Пользователи</div><div class="value blue">—</div><div class="sub">Управление через бота</div></div>
  <div class="card metric"><div class="label">VPN-доступы</div><div class="value blue">—</div><div class="sub">Выдача AWG через бота</div></div>
  <div class="card metric"><div class="label">Уведомления</div><div class="value ok">Готово</div><div class="sub">Система уведомлений NOVA</div></div>
</div>
<div class="dashboard-grid">
  <div class="card">
    <div class="toolbar"><h2>Подключение бота</h2><span class="badge {{ 'on' if token else 'warn' }}">{{ 'Настроен' if token else 'Ожидает настройки' }}</span></div>
    <form method="post">
      <label>Bot Token</label>
      <input name="token" type="password" value="{{ masked }}" placeholder="123456789:AA..." autocomplete="off">
      <div class="formgrid">
        <div><label>Команда запуска</label><input name="command" value="{{ command }}"></div>
        <div><label>Администраторы</label><input name="admins" value="{{ admins }}" placeholder="ID через запятую"></div>
      </div>
      <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap"><button name="action" value="save">Сохранить</button><button class="btn secondary" name="action" value="test">Проверить соединение</button></div>
    </form>
  </div>
  <div class="card">
    <div class="toolbar"><h2>Возможности</h2></div>
    <div class="actions">
      <div class="action"><b>👤 Выдача VPN</b><span>Создание и продление доступа клиентам.</span></div>
      <div class="action"><b>📲 Конфигурация</b><span>Отправка конфигурации AWG пользователю.</span></div>
      <div class="action"><b>⏱ Продление</b><span>Управление сроком действия доступа.</span></div>
      <div class="action"><b>🔔 Уведомления</b><span>События, ошибки и окончания доступа.</span></div>
    </div>
  </div>
</div>
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Безопасность</h2></div><div class="notice">Токен хранится в SQLite и отображается только в маскированном виде.</div></div>
''', message=message, good=good, token=token, masked=masked, command=command, admins=admins, bot_name=bot_name)
            return nova11.nova_layout('Telegram', body, '/telegram')

    original_nav = core.nav
    if not getattr(core, '_telegram_nav_installed', False):
        def nav_with_telegram(path):
            html = original_nav(path)
            marker = '<div class="section">СИСТЕМА</div>'
            item = '<a class="telegram-nav %s" href="/telegram"><i>✈</i>Telegram</a>' % ('active' if path.startswith('/telegram') else '')
            if item not in html:
                html = html.replace(marker, item + marker, 1) if marker in html else html + '<div class="section">ИНТЕГРАЦИИ</div>' + item
            return html
        core.nav = nav_with_telegram
        core._telegram_nav_installed = True

install()
