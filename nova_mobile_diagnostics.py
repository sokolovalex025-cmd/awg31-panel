#!/usr/bin/env python3
import subprocess, time, sqlite3
from flask import jsonify, render_template_string
import nova11

app = nova11.core.app
BASE = '/opt/awg31-panel'

def run(*args):
    try:
        r = subprocess.run(args, text=True, capture_output=True, timeout=8)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)

def item(name, ok, detail, hint=''):
    return {'name':name, 'ok':bool(ok), 'detail':detail or 'OK', 'hint':hint}

def diagnose():
    tests=[]
    rc,out=run('systemctl','is-active','--quiet','awg-quick@awg0')
    tests.append(item('AWG service',rc==0,'awg-quick@awg0 active' if rc==0 else out,'Запусти AWG.'))
    rc,out=run('ip','link','show','awg0')
    tests.append(item('AWG interface',rc==0 and 'UP' in out,'awg0 UP' if rc==0 and 'UP' in out else out,'Проверь awg0.'))
    rc,out=run('sysctl','-n','net.ipv4.ip_forward')
    tests.append(item('IPv4 forwarding',rc==0 and out.strip()=='1','net.ipv4.ip_forward = '+out.strip(),'Включи IPv4 forwarding.'))
    _,route=run('ip','-4','route','show','default')
    parts=route.split(); wan=parts[parts.index('dev')+1] if 'dev' in parts else ''
    tests.append(item('WAN interface',bool(wan),wan or 'Default route not found','Не найден WAN.'))
    if wan:
        rc,out=run('iptables','-t','nat','-C','POSTROUTING','-s','10.66.66.0/24','-o',wan,'-j','MASQUERADE')
        tests.append(item('AWG client NAT',rc==0,'MASQUERADE 10.66.66.0/24 -> '+wan if rc==0 else out,'Запусти awg31-network.service.'))
        rc,out=run('iptables','-C','FORWARD','-i','awg0','-o',wan,'-s','10.66.66.0/24','-j','ACCEPT')
        tests.append(item('AWG -> WAN forwarding',rc==0,'FORWARD rule present' if rc==0 else out,'Проверь FORWARD.'))
    rc,out=run('systemctl','is-active','--quiet','awg31-network')
    tests.append(item('Persistent network service',rc==0,'awg31-network active' if rc==0 else out,'Включи awg31-network.'))
    rc,out=run('getent','hosts','example.com')
    tests.append(item('Server DNS',rc==0,out or 'DNS failed','Проверь DNS VPS.'))
    rc,out=run('ip','-4','addr','show','dev','awg0')
    tests.append(item('AWG subnet',rc==0 and '10.66.66.1/24' in out,out or 'missing','Ожидается 10.66.66.1/24.'))
    dns='unknown'
    try:
        con=sqlite3.connect(BASE+'/panel.db'); row=con.execute("SELECT v FROM settings WHERE k='dns'").fetchone(); con.close(); dns=row[0] if row else 'not configured'
    except Exception as e: dns='DB error: '+str(e)
    tests.append(item('Client DNS',dns not in ('unknown','not configured','','10.66.66.1'),dns,'Рекомендуется 1.1.1.1,8.8.8.8.'))
    rc,out=run('awg','show','awg0','dump'); peers=[]; now=int(time.time())
    if rc==0:
        for line in out.splitlines()[1:]:
            p=line.split('\t')
            if len(p)>=8:
                try: hs=int(p[4])
                except: hs=0
                try: rx=int(p[5]); tx=int(p[6])
                except: rx=tx=0
                peers.append({'endpoint':p[2],'hs':hs,'rx':rx,'tx':tx,'online':bool(hs and now-hs<=180)})
    online=sum(1 for p in peers if p['online'])
    tests.append(item('AWG handshake',online>0,f'{online} client(s) with recent handshake' if online else 'Нет handshake за 180 секунд','Подключи клиент и проверь конфиг.'))
    return {'ok':all(x['ok'] for x in tests),'results':tests,'peers':peers,'wan':wan,'timestamp':int(time.time())}

@app.route('/mobile-diagnostics')
def mobile_diagnostics():
    data=diagnose()
    return nova11.layout('Мобильная диагностика',render_template_string('''<div class=hero><div><div class=eyebrow>NOVA MOBILE HEALTH</div><h1>Мобильная диагностика</h1><p>AWG, handshake, NAT, forwarding и DNS в одной проверке.</p></div><a class=btn href=/mobile-diagnostics>↻ Проверить снова</a></div><div class=card><div class="notice {{'good' if data.ok else 'badbox'}}"><b>{{'✓ Всё готово' if data.ok else '⚠ Требуется внимание'}}</b><div class=muted style="margin-top:6px">WAN: {{data.wan or 'не найден'}} · {{data.results|length}} проверок</div></div>{% for x in data.results %}<div class="notice {{'good' if x.ok else 'badbox'}}"><b>{{'✓' if x.ok else '✕'}} {{x.name}}</b><div style="margin-top:6px">{{x.detail}}</div>{% if not x.ok %}<div class=muted style="margin-top:5px">{{x.hint}}</div>{% endif %}</div>{% endfor %}</div><div class=card style="margin-top:14px"><h2>Последние клиенты</h2><div class=table-wrap><table><tr><th>Endpoint</th><th>Статус</th><th>RX</th><th>TX</th></tr>{% for p in data.peers %}<tr><td>{{p.endpoint or '—'}}</td><td><span class="badge {{'on' if p.online else 'off'}}">{{'ONLINE' if p.online else 'OFFLINE'}}</span></td><td>{{p.rx}}</td><td>{{p.tx}}</td></tr>{% else %}<tr><td colspan=4 class=muted>Клиенты не найдены.</td></tr>{% endfor %}</table></div></div>''',data=data),'/mobile-diagnostics')

@app.route('/api/mobile-diagnostics')
def mobile_diagnostics_api():
    return jsonify(diagnose())
