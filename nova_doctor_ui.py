#!/usr/bin/env python3
"""Expose NOVA Doctor in the main NOVA navigation."""

def apply(nova11):
    core = nova11.core
    old_nav = core.nav

    def nav(path):
        groups = [
            ('ОБЗОР', [('⌂','Дашборд','/'), ('◉','Активные клиенты','/active')]),
            ('УПРАВЛЕНИЕ', [('♣','Клиенты','/clients'), ('◇','Конфигурация','/config'), ('◈','Strong Mobile','/obfuscation'), ('🛜','Настроить Keenetic','/keenetic')]),
            ('СИСТЕМА', [('⌘','Сеть и Firewall','/network'), ('◌','Live Traffic','/traffic'), ('✓','Диагностика','/diagnostics'), ('🩺','NOVA Doctor','/doctor'), ('📡','Монитор подключений','/live-monitor'), ('🛠️','AWG Toolza','/awg-toolza'), ('▣','Резервные копии','/backups'), ('☷','Логи','/logs')]),
            ('ПАНЕЛЬ', [('⚙','Настройки','/settings'), ('📱','Мобильная диагностика','/mobile-diagnostics'), ('ⓘ','О NOVA','/about')]),
        ]
        out = []
        for title, items in groups:
            out.append(f'<div class="section">{title}</div>')
            for icon, name, url in items:
                active = 'active' if (path == url or (url == '/keenetic' and path.startswith('/keenetic'))) else ''
                extra = ' keenetic-nav' if url == '/keenetic' else ''
                out.append(f'<a class="{active}{extra}" href="{url}"><i>{icon}</i>{name}</a>')
        return ''.join(out)

    core.nav = nav
    # Existing app routes call the presentation helpers through app.py globals.
    # Point those globals at the updated navigation as well.
    for rule in list(core.app.url_map.iter_rules()):
        view = core.app.view_functions.get(rule.endpoint)
        if view is not None and getattr(view, '__module__', None) == 'app':
            view.__globals__['nav'] = nav
    return True
