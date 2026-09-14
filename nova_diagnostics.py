#!/usr/bin/env python3
"""NOVA comprehensive server/client diagnostics for AmneziaWG 3.1."""
import re
import time
import subprocess
from pathlib import Path
from flask import jsonify, render_template_string
import nova11

app = nova11.core.app
BASE = Path('/opt/awg31-panel')


def run(*args, timeout=8):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def check(name, ok, detail='OK', hint=''):
    return {'name': name, 'ok': bool(ok), 'detail': detail or 'OK', 'hint': hint}


def service(name):
    rc, out = run('systemctl', 'is-active', name, timeout=3)
    return rc == 0 and out.strip() == 'active', out.strip() or 'unknown'


def wan_interface():
    rc, out = run('ip', '-4', 'route', 'show', 'default')
    if rc:
        return ''
    m = re.search(r'\bdev\s+(\S+)', out)
    return m.group(1) if m else ''


def config_text():
    candidates = [Path('/etc/amnezia/amneziawg/awg0.conf'), Path('/etc/wireguard/awg0.conf')]
    for p in candidates:
        if p.exists():
            try:
                return p, p.read_text(errors='replace')
            except Exception:
                return p, ''
    return candidates[0], ''


def diagnose():
    results = []
    awg_ok, awg_state = service('awg-quick@awg0.service')
    results.append(check('AWG service', awg_ok, awg_state, 'systemctl restart awg-quick@awg0'))

    rc, out = run('ip', 'link', 'show', 'awg0')
    up = rc == 0 and ('state UP' in out or '<BROADCAST' in out and 'UP' in out)
    results.append(check('AWG interface', up, 'awg0 is UP' if up else out, 'Проверь awg0 и конфигурацию.'))

    rc, out = run('awg', 'show', 'awg0')
    results.append(check('AmneziaWG control', rc == 0, 'awg0 readable' if rc == 0 else out, 'Проверь установку AmneziaWG 3.1.'))

    cfg = nova11.core.cfg()
    port = str(cfg.get('ListenPort', ''))
    mtu = str(cfg.get('MTU', ''))
    results.append(check('ListenPort', bool(port and port.isdigit() and 1 <= int(port) <= 65535), port or 'не задан', 'Задай корректный UDP ListenPort.'))
    results.append(check('MTU', bool(mtu.isdigit() and 576 <= int(mtu) <= 1500), mtu or 'не задан', 'Для мобильного профиля NOVA рекомендуется MTU 1280.'))

    required = {'Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4'}
    missing = [k for k in required if not cfg.get(k)]
    wrong = [k for k,v in required.items() if cfg.get(k) and str(cfg.get(k)) != v]
    results.append(check('AWG 3.1 obfuscation', not missing and not wrong,
                         'J/S/H parameters OK' if not missing and not wrong else 'missing: '+','.join(missing)+' wrong: '+','.join(wrong),
                         'Запусти nova_awg31_fix.py для миграции профиля.'))
    hp = bool(cfg.get('HeaderProtectionKey'))
    results.append(check('Header Protection', hp, 'HeaderProtectionKey задан' if hp else 'HeaderProtectionKey отсутствует', 'Запусти nova_awg31_fix.py.'))

    rc, out = run('sysctl', '-n', 'net.ipv4.ip_forward')
    results.append(check('IPv4 forwarding', rc == 0 and out.strip() == '1', out or 'unknown', 'Включи IPv4 forwarding через nova-network-fix.sh.'))

    wan = wan_interface()
    results.append(check('WAN route', bool(wan), wan or 'Default route не найден', 'Проверь ip route и сетевой интерфейс VPS.'))

    if wan:
        rc, _ = run('iptables', '-t', 'nat', '-C', 'POSTROUTING', '-s', '10.66.66.0/24', '-o', wan, '-j', 'MASQUERADE')
        results.append(check('NAT', rc == 0, 'MASQUERADE 10.66.66.0/24 → '+wan if rc == 0 else 'NAT rule не найдена', 'Запусти nova-network-fix.sh.'))
        rc, _ = run('iptables', '-C', 'FORWARD', '-i', 'awg0', '-o', wan, '-s', '10.66.66.0/24', '-j', 'ACCEPT')
        results.append(check('AWG → WAN forwarding', rc == 0, 'FORWARD rule present' if rc == 0 else 'FORWARD rule не найдена', 'Проверь firewall/forwarding.'))
        rc, _ = run('iptables', '-C', 'FORWARD', '-o', 'awg0', '-i', wan, '-d', '10.66.66.0/24', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT')
        results.append(check('WAN → AWG return traffic', rc == 0, 'return rule present' if rc == 0 else 'return rule не найдена', 'Проверь firewall/forwarding.'))

    rc, out = run('ss', '-lun')
    listening = bool(port and any((':'+port+' ') in line or ('0.0.0.0:'+port) in line or ('[::]:'+port) in line for line in out.splitlines()))
    results.append(check('UDP listener', listening, 'UDP '+port+' listening' if listening else 'UDP '+(port or '?')+' не слушается', 'Проверь ListenPort и awg-quick.'))

    rc, out = run('getent', 'hosts', 'example.com')
    results.append(check('Server DNS', rc == 0, out if rc == 0 else 'DNS resolution failed', 'Проверь /etc/resolv.conf и DNS VPS.'))

    rc, out = run('ping', '-4', '-M', 'do', '-c', '1', '-W', '2', '-s', '1200', '1.1.1.1', timeout=4)
    results.append(check('Path MTU 1200', rc == 0, '1200-byte DF ping OK' if rc == 0 else out[-240:], 'Проверь MTU/маршрутизацию, если мобильные клиенты не подключаются.'))

    rc, out = run('ip', '-4', 'addr', 'show', 'dev', 'awg0')
    subnet_ok = rc == 0 and '10.66.66.1/24' in out
    results.append(check('AWG subnet', subnet_ok, '10.66.66.1/24' if subnet_ok else (out or 'subnet не найден'), 'Проверь Address awg0.'))

    peer_count = 0
    online = 0
    peers = []
    rc, out = run('awg', 'show', 'awg0', 'dump')
    now = int(time.time())
    if rc == 0:
        for line in out.splitlines()[1:]:
            p = line.split('\t')
            if len(p) < 8:
                continue
            peer_count += 1
            try: hs = int(p[4] or 0)
            except Exception: hs = 0
            try: rx = int(p[5] or 0); tx = int(p[6] or 0)
            except Exception: rx = tx = 0
            active = bool(hs and now - hs <= 180)
            if active: online += 1
            peers.append({'endpoint': p[2] or '—', 'online': active, 'handshake': hs, 'rx': rx, 'tx': tx})
    results.append(check('Client handshake', online > 0 if peer_count else True,
                         f'{online} из {peer_count} клиентов с handshake ≤ 180 сек.' if peer_count else 'Peers не найдены',
                         'Если клиент не подключается — проверь Endpoint, UDP-порт, MTU и мобильную сеть.'))

    score = round(sum(x['ok'] for x in results) * 100 / len(results)) if results else 0
    return {'ok': all(x['ok'] for x in results), 'score': score, 'wan': wan, 'port': port, 'mtu': mtu,
            'peer_count': peer_count, 'online_peers': online, 'results': results, 'peers': peers,
            'timestamp': now}


TEMPLATE = '''
<div class="hero"><div><div class="eyebrow">NOVA SYSTEM HEALTH</div><h1>Диагностика</h1><p>Полная проверка AWG 3.1, сети, firewall, DNS, MTU и клиентов.</p></div><a class="btn" href="/diagnostics">↻ Проверить снова</a></div>
<div class="grid4">
 <div class="card metric"><div class="label">Health Score</div><div class="value {{'ok' if d.score >= 90 else 'warn' if d.score >= 70 else 'bad'}}">{{d.score}}%</div><div class="sub">{{'Система готова' if d.ok else 'Есть проблемы'}}</div></div>
 <div class="card metric"><div class="label">AWG</div><div class="value {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class="sub">awg0 · UDP {{d.port or '—'}}</div></div>
 <div class="card metric"><div class="label">Клиенты</div><div class="value">{{d.online_peers}} / {{d.peer_count}}</div><div class="sub">активные handshake</div></div>
 <div class="card metric"><div class="label">WAN / MTU</div><div class="value">{{d.wan or '—'}}</div><div class="sub">MTU {{d.mtu or '—'}}</div></div>
</div>
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Проверки</h2><span class="badge {{'on' if d.ok else 'warn'}}">{{'ВСЁ OK' if d.ok else 'ТРЕБУЕТ ВНИМАНИЯ'}}</span></div>{% for x in d.results %}<div class="notice {{'good' if x.ok else 'badbox'}}"><b>{{'✓' if x.ok else '✕'}} {{x.name}}</b><div style="margin-top:5px">{{x.detail}}</div>{% if not x.ok %}<div class="muted" style="margin-top:5px">💡 {{x.hint}}</div>{% endif %}</div>{% endfor %}</div>
<div class="card" style="margin-top:14px"><div class="toolbar"><div><h2>Клиенты</h2><div class="muted">Handshake активен не более 180 секунд.</div></div><a class="btn secondary" href="/active">Открыть клиентов</a></div><div class="table-wrap"><table><tr><th>Endpoint</th><th>Статус</th><th>Последний handshake</th><th>RX</th><th>TX</th></tr>{% for p in d.peers %}<tr><td>{{p.endpoint}}</td><td><span class="badge {{'on' if p.online else 'off'}}">{{'ONLINE' if p.online else 'OFFLINE'}}</span></td><td>{{timefmt(p.handshake)}}</td><td>{{bytes(p.rx)}}</td><td>{{bytes(p.tx)}}</td></tr>{% else %}<tr><td colspan="5" class="muted">Peers не найдены.</td></tr>{% endfor %}</table></div></div>
<script>setTimeout(()=>location.reload(),15000)</script>
'''


def bytes_fmt(n):
    n = float(n or 0)
    for u in ('B','KB','MB','GB','TB'):
        if n < 1024: return f'{n:.0f} {u}'
        n /= 1024
    return f'{n:.1f} PB'


def time_fmt(ts):
    return time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(ts)) if ts else 'Нет handshake'


def page():
    d = diagnose()
    awg = nova11.core.online()
    body = render_template_string(TEMPLATE, d=d, awg=awg, bytes=bytes_fmt, timefmt=time_fmt)
    return nova11.core.layout('Диагностика', body, '/diagnostics')


def apply(nova):
    # Replace the legacy diagnostics view instead of registering a second /diagnostics route.
    app.view_functions['diagnostics'] = page
    app.view_functions['nova_diagnostics'] = page

    @app.get('/api/nova/diagnostics/full')
    def nova_diagnostics_full():
        return jsonify(diagnose())
    return True
