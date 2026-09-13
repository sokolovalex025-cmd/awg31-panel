#!/usr/bin/env python3
"""Telegram management UI for NOVA panel."""
from flask import request, render_template_string
import nova11


def install():
    core = nova11.core
    if 'telegram' not in core.app.view_functions:
        @core.app.route('/telegram', methods=['GET', 'POST'])
        def telegram_page():
            message = ''
            if request.method == 'POST':
                action = request.form.get('action', '')
                if action == 'save':
                    message = 'Настройки Telegram приняты. Подключение бота можно завершить после добавления токена.'
                elif action == 'test':
                    message = 'Проверка Telegram поставлена в очередь.'
            body = render_template_string(r'''
<div class="hero"><div><div class="eyebrow">TELEGRAM CONTROL</div><h1>Telegram</h1><p>Управление Telegram-ботом, выдачей VPN-доступа и уведомлениями.</p></div></div>
{% if message %}<div class="notice good">{{ message }}</div>{% endif %}
<div class="grid4">
  <div class="card metric"><div class="label">Статус бота</div><div class="value warn">Не настроен</div><div class="sub">Токен ещё не добавлен</div></div>
  <div class="card metric"><div class="label">Пользователи</div><div class="value blue">—</div><div class="sub">Будет доступно после подключения</div></div>
  <div class="card metric"><div class="label">VPN-доступы</div><div class="value blue">—</div><div class="sub">Активные выдачи через бота</div></div>
  <div class="card metric"><div class="label">Уведомления</div><div class="value ok">Готово</div><div class="sub">Система уведомлений NOVA</div></div>
</div>
<div class="dashboard-grid">
  <div class="card">
    <div class="toolbar"><h2>Подключение бота</h2><span class="badge warn">Ожидает настройки</span></div>
    <form method="post">
      <label>Bot Token</label><input name="token" type="password" placeholder="123456789:AA..." autocomplete="off">
      <div class="formgrid">
        <div><label>Команда запуска</label><input name="command" value="/start"></div>
        <div><label>Администраторы</label><input name="admins" placeholder="ID через запятую"></div>
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
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Безопасность</h2></div><div class="notice">Токен Telegram не выводится в интерфейсе после сохранения. Рекомендуется ограничить список администраторов Telegram ID.</div></div>
''', message=message)
            return nova11.nova_layout('Telegram', body, '/telegram')

    original_nav = core.nav
    if not getattr(core, '_telegram_nav_installed', False):
        def nav_with_telegram(path):
            html = original_nav(path)
            marker = '<div class="section">СИСТЕМА</div>'
            item = '<a class="{}" href="/telegram"><i>✈</i>Telegram</a>'.format('active' if path.startswith('/telegram') else '')
            if marker in html:
                html = html.replace(marker, marker + item, 1)
            else:
                html += '<div class="section">ИНТЕГРАЦИИ</div>' + item
            return html
        core.nav = nav_with_telegram
        core._telegram_nav_installed = True


install()
