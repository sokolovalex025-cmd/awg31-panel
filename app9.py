#!/usr/bin/env python3
import app as core
import time, subprocess, re
from flask import request

core.VERSION='10.1'
core.BG_VERSION='NOVA'

try:
    import balancer
except Exception:
    balancer=None
try:
    import balancer_provision
except Exception:
    balancer_provision=None

# Left-side scrollbar for the fixed NOVA navigation panel.
core.CSS = core.CSS.replace(
    '.sidebar{position:fixed;',
    '.sidebar{position:fixed;overflow-y:auto;direction:rtl;padding-bottom:120px;scrollbar-width:thin;scrollbar-color:#33445c transparent;'
)
core.CSS = core.CSS.replace(
    '.brand{display:flex;',
    '.sidebar>*{direction:ltr}.brand{display:flex;'
)
core.CSS += '''<style>
.sidebar::-webkit-scrollbar{width:7px}
.sidebar::-webkit-scrollbar-track{background:transparent}
.sidebar::-webkit-scrollbar-thumb{background:#33445c;border-radius:10px;border:2px solid transparent;background-clip:padding-box}
.sidebar::-webkit-scrollbar-thumb:hover{background:#4f8cff;background-clip:padding-box}
.nova-status{display:flex;gap:10px;align-items:center;padding:13px 15px;margin:0 0 14px;border:1px solid #1c5548;border-radius:12px;background:#0b241e}
.nova-status .pulse{width:9px;height:9px;border-radius:50%;background:#37d6a3;box-shadow:0 0 14px #37d6a399}
.nova-status.bad{border-color:#60303b;background:#26131a}.nova-status.bad .pulse{background:#ff647c;box-shadow:0 0 14px #ff647c88}
.nova-status b{font-size:13px}.nova-status small{display:block;color:#8290a3;margin-top:3px}
.diag-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:12px}.diag-item{padding:13px;border:1px solid #202c3b;border-radius:11px;background:#101925}.diag-item b{display:block;margin-bottom:4px}.diag-item span{font-size:12px;color:#8290a3}
@media(max-width:760px){.diag-grid{grid-template-columns:1fr}}
</style>'''

# Strong Mobile status is read from the live configuration, so the panel does
# not show a green badge merely because a UI setting was saved.
def _strong_mobile_status():
    try:
        c = core.cfg()
        required = ['Jc','Jmin','Jmax','S1','S2','S3','S4','H1','H2','H3','H4']
        present = all(c.get(k) for k in required)
        live = core.cmd('awg','show','awg0').stdout or ''
        live_ok = all(x in live for x in ('jc:', 'jmin:', 'jmax:', 's1:', 's2:', 's3:', 's4:'))
        return {
            'active': bool(core.online() and present and live_ok),
            'mtu': c.get('MTU','—'), 'jc': c.get('Jc','—'),
            'jmin': c.get('Jmin','—'), 'jmax': c.get('Jmax','—'),
            's1': c.get('S1','—'), 's2': c.get('S2','—'),
            's3': c.get('S3','—'), 's4': c.get('S4','—'),
            'h1': c.get('H1','—'), 'h2': c.get('H2','—'),
            'h3': c.get('H3','—'), 'h4': c.get('H4','—'),
        }
    except Exception:
        return {'active':False}

@core.app.route('/api/nova/strong-mobile')
def nova_strong_mobile_api():
    return core.jsonify({'ok':True, **_strong_mobile_status()})

@core.app.route('/api/nova/diagnostics')
def nova_diagnostics_api():
    sm = _strong_mobile_status()
    awg_ok = core.online()
    c = core.cfg()
    port = c.get('ListenPort','1234')
    udp_ok = core.cmd('ss','-lun').returncode == 0 and any((':'+str(port)+' ') in x or ('0.0.0.0:'+str(port)) in x for x in core.cmd('ss','-lun').stdout.splitlines())
    ps = core.peers()
    handshakes = sum(1 for x in ps.values() if x.get('handshake') and int(time.time())-x['handshake'] <= 180)
    return core.jsonify({'ok':True,'awg':awg_ok,'strong_mobile':sm['active'],'udp_listen':udp_ok,'port':port,'online_peers':handshakes,'peer_count':len(ps)})

# Replace the existing pages while keeping the rest of the application intact.
def _find_endpoint(path):
    for rule in core.app.url_map.iter_rules():
        if rule.rule == path:
            return rule.endpoint
    return None

def _enhanced_obfuscation():
    s = _strong_mobile_status()
    state = 'ACTIVE' if s.get('active') else 'INACTIVE'
    cls = '' if s.get('active') else 'bad'
    body = f'''<div class="hero"><div><div class="eyebrow">SECURITY PROFILE</div><h1>Strong Mobile</h1><p>Live AmneziaWG obfuscation profile for mobile networks.</p></div></div>
<div class="nova-status {cls}"><div class="pulse"></div><div><b>Strong Mobile: {state}</b><small>Проверено по работающему awg0 и текущему конфигу</small></div></div>
<div class="card"><div class="toolbar"><h2>Параметры профиля</h2><span class="badge {'on' if s.get('active') else 'off'}">{state}</span></div>
<div class="kv"><div><span>MTU</span><b>{s.get('mtu','—')}</b></div><div><span>Jc</span><b>{s.get('jc','—')}</b></div><div><span>Jmin / Jmax</span><b>{s.get('jmin','—')} / {s.get('jmax','—')}</b></div><div><span>S1 / S2</span><b>{s.get('s1','—')} / {s.get('s2','—')}</b></div><div><span>S3 / S4</span><b>{s.get('s3','—')} / {s.get('s4','—')}</b></div><div><span>H1 / H2 / H3 / H4</span><b>{s.get('h1','—')} / {s.get('h2','—')} / {s.get('h3','—')} / {s.get('h4','—')}</b></div></div></div>
<div class="card" style="margin-top:14px"><div class="toolbar"><h2>Быстрая диагностика</h2><a class="btn secondary" href="/diagnostics">Открыть диагностику</a></div><div class="diag-grid"><div class="diag-item"><b>AWG интерфейс</b><span>{'Работает' if core.online() else 'Не работает'}</span></div><div class="diag-item"><b>UDP {s.get('mtu','—') and core.cfg().get('ListenPort','1234')}</b><span>Проверяется через слушающий сокет</span></div><div class="diag-item"><b>Junk / S-параметры</b><span>{'Применены' if s.get('active') else 'Требуют проверки'}</span></div><div class="diag-item"><b>Header Protection</b><span>{'H1–H4 заданы' if all(s.get(k) not in (None,'—','') for k in ('h1','h2','h3','h4')) else 'Не задано'}</span></div></div></div>'''
    return core.layout('Strong Mobile', body, '/obfuscation')

def _enhanced_diagnostics():
    s = _strong_mobile_status(); now=int(time.time()); ps=core.peers(); recent=sum(1 for x in ps.values() if x.get('handshake') and now-x['handshake']<=180)
    port=core.cfg().get('ListenPort','1234'); udp=core.cmd('ss','-lun').stdout
    udp_ok=any((':'+str(port)+' ') in x or ('0.0.0.0:'+str(port)) in x for x in udp.splitlines())
    checks=[('AWG service',core.online(),'awg-quick@awg0 active'),('Strong Mobile',s.get('active',False),'live obfuscation parameters'),('UDP listener',udp_ok,f'UDP {port} listening'),('Recent handshakes',recent>0 if ps else True,f'{recent} peer(s) active')]
    items=''.join(f'<div class="diag-item"><b>{"✓" if ok else "✕"} {name}</b><span>{detail}</span></div>' for name,ok,detail in checks)
    body=f'''<div class="hero"><div><div class="eyebrow">SYSTEM CHECK</div><h1>Диагностика</h1><p>Проверка VPN от сервиса до подключённых клиентов.</p></div><a class="btn" href="/diagnostics">↻ Обновить</a></div><div class="card"><div class="toolbar"><h2>Состояние системы</h2><span class="badge {'on' if all(x[1] for x in checks) else 'warn'}">{'ВСЁ OK' if all(x[1] for x in checks) else 'ТРЕБУЕТ ВНИМАНИЯ'}</span></div><div class="diag-grid">{items}</div></div><div class="card" style="margin-top:14px"><h2 style="margin-top:0">Активные соединения</h2><p class="muted">Последний handshake считается активным в течение 180 секунд.</p><div class="kv"><div><span>Peers</span><b>{len(ps)}</b></div><div><span>Online</span><b class="ok">{recent}</b></div><div><span>UDP</span><b>{port}</b></div><div><span>Strong Mobile</span><b class="{'ok' if s.get('active') else 'bad'}">{'ACTIVE' if s.get('active') else 'INACTIVE'}</b></div></div></div>'''
    return core.layout('Диагностика', body, '/diagnostics')

ob_ep=_find_endpoint('/obfuscation')
if ob_ep: core.app.view_functions[ob_ep]=_enhanced_obfuscation
diag_ep=_find_endpoint('/diagnostics')
if diag_ep: core.app.view_functions[diag_ep]=_enhanced_diagnostics

@core.app.route('/api/traffic92')
def traffic92_compat():
    clients = core.client_stats()
    return core.jsonify({'ok': True,'panel_version': core.VERSION,'awg_online': core.online(),'clients': clients,'online_clients': sum(1 for x in clients if x['online']),'rx': sum(x['rx'] for x in clients),'tx': sum(x['tx'] for x in clients)})

if __name__=='__main__':
    core.app.run(host='0.0.0.0',port=8080)
