from flask import request, Response, redirect
import ipaddress
import os
import re
import subprocess

SERVICES = {
    'youtube': ['YouTube'],
    'telegram': ['Telegram'],
    'discord': ['Discord'],
    'instagram': ['Instagram'],
    'facebook': ['Facebook'],
    'whatsapp': ['WhatsApp'],
    'x': ['X / Twitter'],
    'tiktok': ['TikTok'],
    'chatgpt': ['ChatGPT / OpenAI'],
}

ROUTES = {
    'youtube': ['142.250.0.0/15', '142.251.0.0/16', '172.217.0.0/16', '216.58.192.0/19'],
    'telegram': ['91.108.0.0/16', '149.154.160.0/20'],
    'discord': ['66.22.0.0/16', '162.158.0.0/15'],
    'instagram': ['31.13.24.0/21', '157.240.0.0/16'],
    'facebook': ['31.13.64.0/18', '157.240.0.0/16'],
    'whatsapp': ['31.13.64.0/18', '157.240.0.0/16'],
    'x': ['104.244.40.0/21', '192.133.76.0/22'],
    'tiktok': ['23.227.0.0/16', '161.117.0.0/16'],
    'chatgpt': ['104.18.0.0/15', '172.64.0.0/13'],
}


def _run(*args, timeout=3):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _text(*args):
    r = _run(*args)
    return (r.stdout or '').strip() if r else ''


def _logged(core):
    return bool(core.session.get('logged'))


def _parse_awg_show(text):
    result = {'latest_handshake': None, 'rx': 0, 'tx': 0, 'peers': 0}
    if not text:
        return result
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('peer:'):
            result['peers'] += 1
        elif s.startswith('latest handshake:'):
            m = re.search(r'(\d+)\s+seconds?\s+ago', s)
            if m:
                result['latest_handshake'] = int(m.group(1))
        elif s.startswith('transfer:'):
            m = re.search(r'([0-9.]+)\s*(KiB|MiB|GiB)\s+received,\s+([0-9.]+)\s*(KiB|MiB|GiB)\s+sent', s)
            if m:
                units = {'KiB': 1024, 'MiB': 1024 ** 2, 'GiB': 1024 ** 3}
                result['rx'] += int(float(m.group(1)) * units[m.group(2)])
                result['tx'] += int(float(m.group(3)) * units[m.group(4)])
    return result


def register(core):
    app = core.app
    config_path = '/opt/keenetic-awg2/clients/keenetic-awg2.conf'
    iface = 'awg-keenetic'

    @app.route('/keenetic')
    def keenetic_page():
        if not _logged(core):
            return redirect('/login')
        return Response('''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA — Keenetic</title>
<style>body{font-family:Inter,Arial;background:#0b1020;color:#e8edf7;margin:0;padding:32px}.box{max-width:980px;margin:auto;background:#11182b;border:1px solid #26314d;border-radius:18px;padding:28px}h1{margin-top:0}.muted{color:#94a3b8}.btn{display:inline-block;padding:12px 16px;border-radius:10px;background:#2563eb;color:white;text-decoration:none;margin:8px 8px 8px 0;border:0;cursor:pointer}.card{background:#0c1427;border:1px solid #26314d;border-radius:14px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:14px;background:#101a2f;border:1px solid #26314d;border-radius:12px}.metric b{display:block;font-size:20px;margin-top:5px}.ok{color:#4ade80}.warn{color:#fbbf24}code{background:#0a0f1d;padding:3px 6px;border-radius:6px}@media(max-width:760px){.grid{grid-template-columns:1fr}}</style></head><body><div class="box">
<h1>🛜 Keenetic AWG</h1><p class="muted">Отдельный AWG 2.0-compatible мост для KeeneticOS. Основной NOVA AWG 3.1 не изменяется.</p>
<div class="grid"><div class="metric">Интерфейс<b>awg-keenetic</b></div><div class="metric">UDP порт<b>51820</b></div><div class="metric">Подсеть<b>10.77.0.0/24</b></div></div>
<div class="card"><b>Архитектура</b><p>Клиент Keenetic подключается к <code>awg-keenetic</code>. Сервер NAT'ит трафик через WAN. <code>awg0:1234/UDP</code> и его конфигурация остаются отдельными.</p></div>
<div class="card"><h3>1. Установка / обновление моста</h3><p class="muted">Скрипт безопасно пересоздаёт только <code>awg-keenetic</code> и не трогает <code>awg0</code>.</p><a class="btn" href="/keenetic/awg2-installer.sh">Скачать установщик</a></div>
<div class="card"><h3>2. Конфиг для Keenetic</h3><p>Готовый клиентский профиль с AWG 2.0-compatible параметрами.</p><a class="btn" href="/keenetic/awg2-config">Скачать .conf</a><p class="muted">Файл содержит приватный ключ. Не публикуйте его.</p></div>
<div class="card"><h3>3. Диагностика data-plane</h3><p>Проверяет интерфейс, handshake, передачу, forwarding, NAT и маршрут через WAN.</p><a class="btn" href="/keenetic/diagnostics">Открыть диагностику</a><a class="btn" href="/api/keenetic/status">JSON статус</a></div>
<div class="card"><h3>4. Full tunnel на Keenetic</h3><p>В peer используйте <code>AllowedIPs = 0.0.0.0/0</code>, а на самом Keenetic назначьте нужные устройства/сеть на профиль политики, использующий AWG-интерфейс. Одного AllowedIPs недостаточно для выборочной policy routing.</p><p class="muted">Если весь LAN должен идти через VPN, назначьте LAN-профиль на VPN. Для выборочной маршрутизации используйте политики KeeneticOS.</p></div>
<div class="card"><h3>5. Выборочная маршрутизация</h3><p>Ниже можно получить справочный список IPv4 CIDR. Это не универсальный импорт: CDN и IP сервисов меняются, поэтому для стабильной выборочной маршрутизации лучше использовать политики KeeneticOS по доменам/IP.</p><form method="post" action="/keenetic/routes"><select name="service">''' + ''.join(f'<option value="{k}">{v[0]}</option>' for k,v in SERVICES.items()) + '''</select> <button class="btn" type="submit">Скачать CIDR</button></form></div>
</div></body></html>''', mimetype='text/html')

    @app.route('/keenetic/awg2-installer.sh')
    def keenetic_installer():
        if not _logged(core):
            return redirect('/login')
        return redirect('https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/keenetic-awg2.sh')

    @app.route('/keenetic/awg2-config')
    def keenetic_config():
        if not _logged(core):
            return redirect('/login')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = f.read()
        except FileNotFoundError:
            return Response('Keenetic AWG 2.0 bridge is not installed yet. Run keenetic-awg2.sh first.', status=404, mimetype='text/plain')
        except OSError as e:
            return Response(f'Cannot read Keenetic config: {e}', status=500, mimetype='text/plain')
        return Response(data, mimetype='application/octet-stream', headers={'Content-Disposition': 'attachment; filename="nova-keenetic-awg2.conf"', 'Cache-Control': 'no-store', 'Pragma': 'no-cache'})

    @app.route('/keenetic/routes', methods=['POST'])
    def keenetic_routes():
        if not _logged(core):
            return redirect('/login')
        service = request.form.get('service', 'youtube')
        if service not in SERVICES:
            return Response('Unknown service', status=400)
        lines = [f'# NOVA Keenetic reference routes: {service}', '# Static IPv4 CIDR list. CDN/domain changes may require updates.', '# This file is a reference list, not a universal KeeneticOS import format.']
        lines.extend(str(ipaddress.ip_network(cidr, strict=False)) for cidr in ROUTES[service])
        lines.append('')
        return Response('\n'.join(lines), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename="nova-{service}-routes.txt"', 'Cache-Control': 'no-store'})

    def _status():
        link = _run('ip', 'link', 'show', iface)
        addr = _text('ip', '-4', 'addr', 'show', 'dev', iface)
        show = _text('awg', 'show', iface)
        service = _text('systemctl', 'is-active', 'keenetic-awg2.service') or 'inactive'
        forwarding = _text('sysctl', '-n', 'net.ipv4.ip_forward') or '0'
        route = _text('ip', 'route', 'get', '1.1.1.1', 'from', '10.77.0.1')
        nat = _text('iptables', '-t', 'nat', '-L', 'POSTROUTING', '-n', '-v')
        forward = _text('iptables', '-L', 'FORWARD', '-n', '-v')
        parsed = _parse_awg_show(show)
        return {'interface': iface, 'exists': bool(link and link.returncode == 0), 'service': service, 'awg_ok': bool(show), 'address': addr, 'details': show, 'handshake_seconds_ago': parsed['latest_handshake'], 'peers': parsed['peers'], 'rx_bytes': parsed['rx'], 'tx_bytes': parsed['tx'], 'ip_forward': forwarding, 'route_from_tunnel': route, 'nat_rules': nat, 'forward_rules': forward, 'wan_route_ok': bool(route and 'dev ' in route and 'via ' in route)}

    @app.route('/keenetic/diagnostics')
    def keenetic_diagnostics():
        if not _logged(core):
            return redirect('/login')
        s = _status()
        hs = s['handshake_seconds_ago']
        hs_text = 'нет handshake' if hs is None else f'{hs} сек. назад'
        body = f'''<div class="hero"><div><div class="eyebrow">NOVA / KEENETIC</div><h1>Диагностика AWG bridge</h1><p>Проверка именно <code>{iface}</code>; основной <code>awg0</code> не участвует.</p></div><a class="btn" href="/keenetic/diagnostics">↻ Обновить</a></div><div class="grid4"><div class="card metric"><div class="label">Service</div><div class="value">{s['service']}</div></div><div class="card metric"><div class="label">Handshake</div><div class="value">{hs_text}</div></div><div class="card metric"><div class="label">RX / TX</div><div class="value">{s['rx_bytes']} / {s['tx_bytes']}</div></div><div class="card metric"><div class="label">Forwarding</div><div class="value">{s['ip_forward']}</div></div></div><div class="card" style="margin-top:14px"><h2>Результаты</h2><p><b>Интерфейс:</b> {'OK' if s['exists'] else 'НЕ НАЙДЕН'}</p><p><b>AWG:</b> {'OK' if s['awg_ok'] else 'НЕ ОТВЕЧАЕТ'}</p><p><b>Маршрут 10.77.0.1 → 1.1.1.1:</b> {'OK' if s['wan_route_ok'] else 'ПРОВЕРИТЬ'}</p><p><b>Peer:</b> {s['peers']}</p></div><div class="card" style="margin-top:14px"><h2>Как проверить трафик Keenetic</h2><p>Откройте сайт на устройстве за Keenetic и одновременно смотрите этот экран. Если handshake есть, но RX/TX не растёт — проблема обычно в policy routing на Keenetic.</p><pre style="white-space:pre-wrap;overflow:auto">{s['route_from_tunnel']}</pre></div>'''
        return core.layout('Keenetic — диагностика', body, '/keenetic/diagnostics')

    @app.route('/api/keenetic/status')
    def keenetic_status():
        if not _logged(core):
            return core.jsonify({'error': 'auth required'}), 401
        return core.jsonify(_status())
