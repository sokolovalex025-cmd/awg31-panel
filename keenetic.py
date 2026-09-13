#!/usr/bin/env python3
"""KeeneticOS 5.x helper for NOVA.

Generates Keenetic-compatible IPv4 route .bat files from curated service domains.
The route file is intentionally separate from the AWG client .conf because
KeeneticOS 5.x selective routing is configured as user-defined IPv4 routes.
"""
import io, ipaddress, socket, time
from flask import request, Response

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
    nets=[]
    for ip in ips:
        nets.append(ipaddress.ip_network(f'{ip}/{prefix}', strict=False))
    merged=ipaddress.collapse_addresses(nets)
    return list(merged)[:limit]

def register(core):
    @core.app.route('/keenetic')
    def keenetic_page():
        rows=core.rows()
        body=core.render_template_string('''<div class="hero"><div><div class="eyebrow">KEENETIC OS 5.x</div><h1>Keenetic Toolkit</h1><p>Генерация маршрутов для выборочного VPN без ручного ввода сотен IP.</p></div><span class="tag">IPv4 · CIDR · .bat</span></div>
<div class="notice good"><b>Как это работает</b><br>Выберите сервисы → NOVA разрешит домены в IPv4 → соберёт CIDR → скачаете <b>keenetic-routes.bat</b> → загрузите его в Keenetic в разделе IPv4-маршрутов и выберете ваш WireGuard-интерфейс.</div>
<div class="notice"><b>Важно для вашей схемы:</b> KeeneticOS 5.15 поддерживает AmneziaWG 1.5/2.0, но текущий сервер NOVA работает на AmneziaWG 3.1. Поэтому этот генератор маршрутов уже можно использовать с VPN-интерфейсом, но сам 3.1-конфиг в Keenetic импортировать нельзя. Для полноценного Keenetic-профиля добавим отдельный AWG 2.0 listener, не затрагивая ваш AWG 3.1.</div>
<div class="card"><form method="post" action="/keenetic/routes"><div class="toolbar"><h2>Сервисы</h2><span class="muted">Обычно достаточно 1–4 сервисов</span></div><div class="formgrid">{% for key,(title,domains) in services.items() %}<label style="display:flex;gap:9px;align-items:center;padding:10px;border:1px solid #202c3b;border-radius:10px;background:#101925"><input type="checkbox" name="service" value="{{key}}" style="width:auto" {% if key in selected %}checked{% endif %}><span><b>{{title}}</b><small class="subline">{{domains|join(', ')}}</small></span></label>{% endfor %}</div><div class="formgrid" style="margin-top:14px"><div><label>Агрегация IPv4</label><select name="prefix"><option value="32">/32 — точнее, больше маршрутов</option><option value="24" selected>/24 — баланс</option><option value="23">/23 — меньше маршрутов</option></select></div><div><label>Клиент</label><select name="client_id"><option value="">Не требуется для .bat</option>{% for r in rows %}<option value="{{r.id}}">{{r.name}} — {{r.address}}</option>{% endfor %}</select></div></div><button style="margin-top:14px">⬇ Скачать маршруты Keenetic</button></form></div>''',services=SERVICES,selected=[],rows=rows())
        return core.layout('Keenetic',body,'/keenetic')

    @core.app.route('/keenetic/routes', methods=['POST'])
    def keenetic_routes():
        selected=request.form.getlist('service')
        try: prefix=int(request.form.get('prefix','24'))
        except Exception: prefix=24
        if prefix not in (32,24,23): prefix=24
        domains=[]
        titles=[]
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
            mask=str(net.netmask)
            lines.append(f'route ADD {net.network_address} MASK {mask} 0.0.0.0')
        lines += ['', 'REM Upload this BAT in Keenetic: Network rules -> Routing -> IPv4 routes -> Upload.', 'REM Select the WireGuard VPN interface when importing.']
        data='\r\n'.join(lines)+'\r\n'
        return Response(data.encode(),mimetype='application/octet-stream',headers={'Content-Disposition':'attachment; filename=keenetic-routes.bat'})

    # Add a compact sidebar entry without changing the core navigation code.
    old_nav=core.nav
    def nav_with_keenetic(path):
        s=old_nav(path)
        marker='<div class="section">СИСТЕМА</div>'
        link='<div class="section">ROUTING</div><a class="active" href="/keenetic">▣Keenetic</a>' if path=='/keenetic' else '<div class="section">ROUTING</div><a href="/keenetic">▣Keenetic</a>'
        return s.replace(marker,link+marker)
    core.nav=nav_with_keenetic
