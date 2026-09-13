from flask import request, Response, redirect
import ipaddress
import os
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


def register(core):
    app = core.app
    config_path = '/opt/keenetic-awg2/clients/keenetic-awg2.conf'

    @app.route('/keenetic')
    def keenetic_page():
        if not core.session.get('logged'):
            return redirect('/login')
        return Response('''<!doctype html><html><head><meta charset="utf-8"><title>NOVA — Keenetic</title>
<style>body{font-family:Inter,Arial;background:#0b1020;color:#e8edf7;margin:0;padding:32px}.box{max-width:900px;margin:auto;background:#11182b;border:1px solid #26314d;border-radius:18px;padding:28px}h1{margin-top:0}.muted{color:#94a3b8}.btn{display:inline-block;padding:12px 16px;border-radius:10px;background:#2563eb;color:white;text-decoration:none;margin:8px 8px 8px 0;border:0;cursor:pointer}.card{background:#0c1427;border:1px solid #26314d;border-radius:14px;padding:18px;margin:16px 0}code{background:#0a0f1d;padding:3px 6px;border-radius:6px}.ok{color:#4ade80}.warn{color:#fbbf24}</style></head><body><div class="box">
<h1>🛜 Keenetic AWG</h1><p class="muted">KeeneticOS 5.1+ через отдельный AWG 2.0-compatible интерфейс.</p>
<div class="card"><b>Важно</b><p>Основной NOVA AWG 3.1 <code>awg0:1234/UDP</code> не изменяется. Для Keenetic используется отдельный интерфейс <code>awg-keenetic:51820/UDP</code>.</p></div>
<div class="card"><h3>1. Установка на VPS</h3><p>Скрипт создаёт отдельный туннель, ключи и готовый клиентский профиль.</p><a class="btn" href="/keenetic/awg2-installer.sh">Скачать установщик AWG 2.0</a></div>
<div class="card"><h3>2. Конфиг для Keenetic</h3><p>После установки скачайте готовый профиль и импортируйте его в KeeneticOS.</p><a class="btn" href="/keenetic/awg2-config">Скачать .conf</a><p class="muted">Файл содержит приватный ключ клиента — не публикуйте его.</p></div>
<div class="card"><h3>3. Проверка</h3><a class="btn" href="/api/keenetic/status">Проверить AWG bridge</a><p class="muted">Проверяется только <code>awg-keenetic</code>; основной <code>awg0</code> не трогается.</p></div>
<div class="card"><h3>4. Выборочная маршрутизация</h3><p>Скачайте список IPv4 подсетей сервиса. Для полного покрытия CDN/доменов лучше использовать политики KeeneticOS по доменам, а не только статические IP.</p><form method="post" action="/keenetic/routes"><select name="service">''' + ''.join(f'<option value="{k}">{v[0]}</option>' for k,v in SERVICES.items()) + '''</select> <button class="btn" type="submit">Скачать CIDR</button></form></div>
</div></body></html>''', mimetype='text/html')

    @app.route('/keenetic/awg2-installer.sh')
    def keenetic_installer():
        if not core.session.get('logged'):
            return redirect('/login')
        return redirect('https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/keenetic-awg2.sh')

    @app.route('/keenetic/awg2-config')
    def keenetic_config():
        if not core.session.get('logged'):
            return redirect('/login')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = f.read()
        except FileNotFoundError:
            return Response('Keenetic AWG 2.0 bridge is not installed yet. Run keenetic-awg2.sh first.', status=404, mimetype='text/plain')
        except OSError as e:
            return Response(f'Cannot read Keenetic config: {e}', status=500, mimetype='text/plain')
        return Response(data, mimetype='application/octet-stream', headers={
            'Content-Disposition': 'attachment; filename="nova-keenetic-awg2.conf"',
            'Cache-Control': 'no-store',
        })

    @app.route('/keenetic/routes', methods=['POST'])
    def keenetic_routes():
        if not core.session.get('logged'):
            return redirect('/login')
        service = request.form.get('service', 'youtube')
        if service not in SERVICES:
            return Response('Unknown service', status=400)
        targets = {
            'youtube': ['142.250.0.0/15','142.251.0.0/16','172.217.0.0/16','216.58.192.0/19'],
            'telegram': ['91.108.0.0/16','149.154.160.0/20'],
            'discord': ['66.22.0.0/16','162.158.0.0/15'],
            'instagram': ['31.13.24.0/21','157.240.0.0/16'],
            'facebook': ['31.13.64.0/18','157.240.0.0/16'],
            'whatsapp': ['31.13.64.0/18','157.240.0.0/16'],
            'x': ['104.244.40.0/21','192.133.76.0/22'],
            'tiktok': ['23.227.0.0/16','161.117.0.0/16'],
            'chatgpt': ['104.18.0.0/15','172.64.0.0/13'],
        }
        lines = [f'# NOVA Keenetic routes: {service}', '# Static IPv4 CIDR list. CDN/domain changes may require updates.']
        lines.extend(str(ipaddress.ip_network(cidr, strict=False)) for cidr in targets[service])
        lines.append('')
        return Response('\n'.join(lines), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename="nova-{service}-routes.txt"'})

    @app.route('/api/keenetic/status')
    def keenetic_status():
        if not core.session.get('logged'):
            return core.jsonify({'error': 'auth required'}), 401
        iface = 'awg-keenetic'
        try:
            link = subprocess.run(['ip', 'link', 'show', iface], capture_output=True, text=True, timeout=3)
            show = subprocess.run(['awg', 'show', iface], capture_output=True, text=True, timeout=3)
            service = subprocess.run(['systemctl', 'is-active', 'keenetic-awg2.service'], capture_output=True, text=True, timeout=3)
            return core.jsonify({
                'interface': iface,
                'exists': link.returncode == 0,
                'awg_ok': show.returncode == 0,
                'service': service.stdout.strip() or 'inactive',
                'details': show.stdout,
            })
        except Exception as e:
            return core.jsonify({'interface': iface, 'exists': False, 'awg_ok': False, 'service': 'unknown', 'error': str(e)})
