from flask import request, Response, redirect
import ipaddress
import socket
import subprocess
import re

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

    @app.route('/keenetic')
    def keenetic_page():
        if not core.session.get('logged'):
            return redirect('/login')
        return Response('''<!doctype html><html><head><meta charset="utf-8"><title>NOVA — Keenetic</title>
<style>body{font-family:Inter,Arial;background:#0b1020;color:#e8edf7;margin:0;padding:32px} .box{max-width:900px;margin:auto;background:#11182b;border:1px solid #26314d;border-radius:18px;padding:28px}h1{margin-top:0}.muted{color:#94a3b8}.btn{display:inline-block;padding:12px 16px;border-radius:10px;background:#2563eb;color:white;text-decoration:none;margin:8px 8px 8px 0}.card{background:#0c1427;border:1px solid #26314d;border-radius:14px;padding:18px;margin:16px 0}code{background:#0a0f1d;padding:3px 6px;border-radius:6px}</style></head><body><div class="box">
<h1>🛜 Keenetic AWG</h1><p class="muted">Профиль для KeeneticOS 5.1+ через отдельный AWG 2.0-compatible интерфейс.</p>
<div class="card"><b>Важно</b><p>Основной NOVA AWG 3.1 <code>awg0:1234/UDP</code> не изменяется. Для Keenetic используется отдельный интерфейс <code>awg-keenetic:51820/UDP</code>.</p></div>
<div class="card"><h3>Установка на VPS</h3><p>Скрипт установки поднимает отдельный туннель и создаёт готовый клиентский конфиг.</p><a class="btn" href="/keenetic/awg2-installer.sh">Скачать установщик AWG 2.0</a></div>
<div class="card"><h3>Готовый конфиг</h3><p>После установки конфиг создаётся как <code>/opt/keenetic-awg2/clients/keenetic-awg2.conf</code>.</p><p>Не публикуйте этот файл: в нём находится приватный ключ клиента.</p></div>
<div class="card"><h3>Выборочная маршрутизация</h3><p>Генерируйте IPv4 route-файл для выбранного сервиса и импортируйте его в KeeneticOS. Это позволяет направлять только нужные IP через VPN.</p><form method="post" action="/keenetic/routes"><select name="service">''' + ''.join(f'<option value="{k}">{v[0]}</option>' for k,v in SERVICES.items()) + '''</select> <button class="btn" type="submit">Скачать BAT routes</button></form></div>
</div></body></html>''', mimetype='text/html')

    @app.route('/keenetic/awg2-installer.sh')
    def keenetic_installer():
        if not core.session.get('logged'):
            return redirect('/login')
        # Keep a direct panel link while allowing the installer to remain versioned in GitHub.
        return redirect('https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/keenetic-awg2.sh')

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
        lines = ['@echo off', 'REM NOVA Keenetic selective routes', 'REM Generated from NOVA panel', '']
        for cidr in targets[service]:
            net = ipaddress.ip_network(cidr, strict=False)
            lines.append(f'route ADD {net.network_address} MASK {net.netmask} 0.0.0.0')
        lines += ['', 'REM Import/use these IPv4 routes with the Keenetic AWG interface.', '']
        return Response('\r\n'.join(lines), mimetype='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="nova-{service}-routes.bat"'})

    @app.route('/api/keenetic/status')
    def keenetic_status():
        if not core.session.get('logged'):
            return core.jsonify({'error':'auth required'}), 401
        iface = 'awg-keenetic'
        try:
            show = subprocess.run(['awg','show',iface], capture_output=True, text=True, timeout=3)
            exists = subprocess.run(['ip','link','show',iface], capture_output=True, text=True, timeout=3).returncode == 0
            return core.jsonify({'interface':iface,'exists':exists,'awg_ok':show.returncode == 0,'details':show.stdout})
        except Exception as e:
            return core.jsonify({'interface':iface,'exists':False,'awg_ok':False,'error':str(e)})
