#!/usr/bin/env python3
"""KeeneticOS 5.x helper for NOVA."""
import ipaddress, socket, time
from flask import request, Response, redirect

SERVICES = {
    'youtube': ('YouTube', ['youtube.com','googlevideo.com','ytimg.com','youtu.be']),
    'telegram': ('Telegram', ['telegram.org','t.me']),
    'discord': ('Discord', ['discord.com','discordapp.com','discord.gg']),
    'instagram': ('Instagram', ['instagram.com','cdninstagram.com']),
    'facebook': ('Facebook', ['facebook.com','fbcdn.net','fb.com']),
    'whatsapp': ('WhatsApp', ['whatsapp.com','whatsapp.net']),
    'x': ('X / Twitter', ['x.com','twitter.com','twimg.com']),
    'tiktok': ('TikTok', ['tiktok.com','tiktokcdn.com','tiktokv.com']),
    'chatgpt': ('ChatGPT / OpenAI', ['chatgpt.com','openai.com','oaistatic.com']),
}


def _resolve_ipv4(domains):
    ips=set()
    for domain in domains:
        try:
            for item in socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM):
                ips.add(item[4][0])
        except Exception:
            continue
    return sorted(ips, key=lambda x: tuple(map(int,x.split('.'))))


def _aggregate(ips, prefix=24, limit=1024):
    nets=[ipaddress.ip_network(f'{ip}/{prefix}', strict=False) for ip in ips]
    return list(ipaddress.collapse_addresses(nets))[:limit]


def register(core):
    @core.app.route('/keenetic')
    def keenetic_page():
        rows=core.rows()
        body=core.render_template_string('''<div class="hero"><div><div class="eyebrow">KEENETIC OS 5.x</div><h1>Keenetic Toolkit</h1><p>Генерация маршрутов и отдельного AWG 2.0 профиля для Keenetic.</p></div><span class="tag">AWG 2.0 · IPv4 · CIDR · .bat</span></div>
<div class="notice good"><b>Готовая схема</b><br>Ваш NOVA AWG 3.1 остаётся на 1234/UDP. Для Keenetic используется отдельный изолированный AWG 2.0 userspace endpoint на другом UDP-порту. KeeneticOS 5.1+ поддерживает AWG 1.5/2.0, а AWG 3.1 нативно не импортируется.</div>
<div class="card"><h2>AWG 2.0 для Keenetic</h2><p class="muted">Установщик создаёт отдельный Docker-контейнер <b>keenetic-awg2</b>, не меняя ваш <b>awg0</b> / AWG 3.1. После установки готовый файл <b>keenetic-awg2.conf</b> можно импортировать в KeeneticOS 5.1+.</p><a class="button" href="/keenetic/awg2-installer.sh">⬇ Скачать установщик AWG 2.0</a><div class="subline" style="margin-top:10px">По умолчанию порт 51820/UDP. Если он занят, перед запуском задайте KEENETIC_AWG2_PORT.</div></div>
<div class="card"><form method="post" action="/keenetic/routes"><div class="toolbar"><h2>Маршруты</h2><span class="muted">До 1024 IPv4 route lines на файл</span></div><div class="formgrid">{% for key,(title,domains) in services.items() %}<label style="display:flex;gap:9px;align-items:center;padding:10px;border:1px solid #202c3b;border-radius:10px;background:#101925"><input type="checkbox" name="service" value="{{key}}" style="width:auto"><span><b>{{title}}</b><small class="subline">{{domains|join(', ')}}</small></span></label>{% endfor %}</div><div class="formgrid" style="margin-top:14px"><div><label>Агрегация IPv4</label><select name="prefix"><option value="32">/32 — точнее, больше маршрутов</option><option value="24" selected>/24 — баланс</option><option value="23">/23 — меньше маршрутов</option></select></div><div><label>Клиент</label><select name="client_id"><option value="">Не требуется для .bat</option>{% for r in rows %}<option value="{{r.id}}">{{r.name}} — {{r.address}}</option>{% endfor %}</select></div></div><button style="margin-top:14px">⬇ Скачать маршруты Keenetic</button></form></div>''',services=SERVICES,rows=rows())
        return core.layout('Keenetic',body,'/keenetic')

    @core.app.route('/keenetic/awg2-installer.sh')
    def keenetic_awg2_installer():
        # Keep the installer in GitHub so it is always identical to the panel release.
        return redirect('https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/keenetic-awg2.sh')

    @core.app.route('/keenetic/routes', methods=['POST'])
    def keenetic_routes():
        selected=request.form.getlist('service')
        try: prefix=int(request.form.get('prefix','24'))
        except Exception: prefix=24
        if prefix not in (32,24,23): prefix=24
        domains=[]; titles=[]
        for key in selected:
            if key in SERVICES:
                titles.append(SERVICES[key][0]); domains.extend(SERVICES[key][1])
        if not domains:
            return 'Выберите хотя бы один сервис.',400
        ips=_resolve_ipv4(sorted(set(domains)))
        nets=_aggregate(ips,prefix,1024)
        if not nets:
            return 'Не удалось получить IPv4-адреса выбранных сервисов с сервера.',502
        lines=['@echo off',f'REM NOVA Keenetic routes - {time.strftime("%Y-%m-%d %H:%M:%S")}',f'REM Services: {", ".join(titles)}',f'REM Aggregation: /{prefix}',f'REM Routes: {len(nets)} / 1024 maximum','']
        for net in nets:
            lines.append(f'route ADD {net.network_address} MASK {net.netmask} 0.0.0.0')
        lines += ['', 'REM Upload this BAT in Keenetic: Network rules -> Routing -> IPv4 routes -> Upload.', 'REM Select the AWG 2.0 WireGuard VPN interface when importing.']
        data='\r\n'.join(lines)+'\r\n'
        return Response(data.encode(),mimetype='application/octet-stream',headers={'Content-Disposition':'attachment; filename=keenetic-routes.bat'})

    old_nav=core.nav
    def nav_with_keenetic(path):
        s=old_nav(path)
        marker='<div class="section">СИСТЕМА</div>'
        link='<div class="section">ROUTING</div><a class="active" href="/keenetic">▣Keenetic</a>' if path=='/keenetic' else '<div class="section">ROUTING</div><a href="/keenetic">▣Keenetic</a>'
        return s.replace(marker,link+marker)
    core.nav=nav_with_keenetic
