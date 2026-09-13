#!/usr/bin/env python3
import app as core
import time
from flask import redirect

core.VERSION='11.0'
core.BG_VERSION='NOVA'

try:
    import balancer
except Exception:
    balancer=None
try:
    import balancer_provision
except Exception:
    balancer_provision=None
try:
    import keenetic
    keenetic.register(core)
except Exception:
    keenetic=None

# NOVA 11 visual system: cleaner hierarchy, glass surfaces, compact navigation,
# responsive cards and stronger status presentation. Functional routes remain unchanged.
core.CSS += '''<style>
:root{--bg:#060a12;--panel:#0b1220f2;--panel2:#101a2b;--line:#1b2a40;--text:#f6f8fc;--muted:#8290a5;--accent:#6d8cff;--accent2:#35e0ae;--danger:#ff637d;--warn:#f5c15b;--shadow:0 24px 70px #0009}
html,body{background:#050812!important;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important}
body:before{background:radial-gradient(700px 420px at 8% 0%,#315cff22,transparent 65%),radial-gradient(620px 420px at 92% 92%,#19d9a516,transparent 65%),linear-gradient(#050812f2,#050812fa),url('/background.svg?v=NOVA11')!important;background-size:auto,auto,auto,cover!important}
.sidebar{width:270px!important;background:linear-gradient(180deg,#080e19f5,#070c15f8)!important;border-right:1px solid #1b2940!important;box-shadow:24px 0 70px #0004!important;padding:20px 15px!important}
.brand{padding:5px 10px 25px!important}.logo{width:46px!important;height:46px!important;border-radius:14px!important;background:linear-gradient(145deg,#718cff,#36d8ae)!important;box-shadow:0 12px 35px #496dff45!important}.brand b{font-size:19px!important;letter-spacing:-.02em}.brand small{font-size:10px!important;letter-spacing:.08em;text-transform:uppercase}
.section{margin:18px 9px 7px!important;color:#506078!important;font-size:9px!important;letter-spacing:.16em!important}.nav{gap:5px!important}.nav a{padding:11px 12px!important;border-radius:12px!important;color:#91a0b5!important;transition:.18s ease!important}.nav a:hover{background:#111c2c!important;color:#fff!important;border-color:#1c3049!important;transform:translateX(2px)}.nav a.active{background:linear-gradient(90deg,#172742,#112034)!important;border-color:#2a4770!important;color:#fff!important;box-shadow:inset 3px 0 #718cff,0 8px 25px #0003!important}.nav i{font-size:15px!important}
.server{position:static!important;left:auto!important;right:auto!important;bottom:auto!important;margin:18px 0 0!important;background:linear-gradient(135deg,#0d1928,#0b1421)!important;border-color:#20324b!important;border-radius:14px!important}.statusdot{width:8px!important;height:8px!important}
.main{width:calc(100% - 270px)!important;margin-left:270px!important;padding:0 38px 55px!important}.topbar{margin:0 -38px 30px!important;padding:0 38px!important;height:72px!important;background:#070d17dd!important;border-color:#17253a!important}.topbar .title{font-size:13px!important;color:#aab6c8!important}.tag{background:#0d1726!important;border-color:#1d3048!important;color:#b6c2d2!important}
.wrap{max-width:1480px!important}.hero{margin:8px 0 22px!important}.eyebrow{color:#718cff!important;letter-spacing:.18em!important}.hero h1{font-size:38px!important;line-height:1.04!important;letter-spacing:-.05em!important}.hero p{font-size:14px!important;color:#8997aa!important}
.card{background:linear-gradient(145deg,#0d1624f5,#0a121ef2)!important;border-color:#1b2b42!important;border-radius:17px!important;box-shadow:0 15px 45px #00025!important}.grid4{gap:14px!important}.metric{min-height:136px!important}.metric .label{color:#66758c!important}.metric .value{font-size:32px!important}.dashboard-grid{gap:15px!important}.action{background:#0c1624!important;border-color:#1a2b41!important;border-radius:14px!important;transition:.18s ease!important}.action:hover{background:#101c2d!important;border-color:#31507a!important;transform:translateY(-2px)!important;box-shadow:0 12px 30px #0004!important}
.btn,button{border-radius:10px!important;background:linear-gradient(135deg,#6e89ff,#4d6fe7)!important;box-shadow:0 8px 22px #526fff24!important}.btn.secondary{background:#101a29!important;border-color:#22354d!important;box-shadow:none!important}.btn.danger{background:#3a1823!important;border-color:#693247!important}
input,select,.input{background:#080f1a!important;border-color:#21334b!important;border-radius:10px!important}input:focus,select:focus{border-color:#5e7dff!important;box-shadow:0 0 0 3px #5e7dff18!important}
th{color:#65758d!important}td{border-bottom-color:#172538!important}.badge{border:1px solid transparent!important}.badge.on{background:#0b2b25!important;color:#55e3ba!important;border-color:#185548!important}.badge.off{background:#29151c!important;color:#ff8799!important;border-color:#5b2938!important}.badge.warn{background:#30260f!important;color:#f6c65f!important;border-color:#5c4817!important}
.nova-status{background:linear-gradient(135deg,#0b2924,#0a1e1b)!important;border-color:#1b5a4c!important;border-radius:15px!important;box-shadow:0 10px 30px #0003!important}.nova-status.bad{background:linear-gradient(135deg,#2a151d,#1d1016)!important;border-color:#673243!important}.diag-grid{gap:12px!important}.diag-item{background:#0b1523!important;border-color:#1b2c43!important;border-radius:13px!important;padding:15px!important}
.keenetic-nav{margin-top:10px!important;background:linear-gradient(135deg,#10253a,#0d211e)!important;border-color:#244d67!important}.footer{margin-top:38px!important;color:#46566c!important}
@media(max-width:1050px){.sidebar{width:245px!important}.main{width:calc(100% - 245px)!important;margin-left:245px!important;padding-left:25px!important;padding-right:25px!important}.topbar{margin-left:-25px!important;margin-right:-25px!important;padding-left:25px!important;padding-right:25px!important}}
@media(max-width:760px){.sidebar{width:270px!important;transform:translateX(-100%);box-shadow:20px 0 60px #0008!important}.sidebar.open{transform:none}.main{width:100%!important;margin-left:0!important;padding:0 15px 35px!important}.topbar{margin:0 -15px 18px!important;padding:0 15px!important;height:64px!important}.hero h1{font-size:31px!important}.grid4{grid-template-columns:1fr 1fr!important}.card{border-radius:15px!important}}
@media(max-width:460px){.grid4{grid-template-columns:1fr!important}.hero h1{font-size:28px!important}}
</style>'''

def _strong_mobile_status():
    try:
        c=core.cfg(); required=['Jc','Jmin','Jmax','S1','S2','S3','S4','H1','H2','H3','H4']
        present=all(c.get(k) for k in required); live=core.cmd('awg','show','awg0').stdout or ''
        live_ok=all(x in live for x in ('jc:','jmin:','jmax:','s1:','s2:','s3:','s4:'))
        return {'active':bool(core.online() and present and live_ok),'mtu':c.get('MTU','—'),'jc':c.get('Jc','—'),'jmin':c.get('Jmin','—'),'jmax':c.get('Jmax','—'),'s1':c.get('S1','—'),'s2':c.get('S2','—'),'s3':c.get('S3','—'),'s4':c.get('S4','—'),'h1':c.get('H1','—'),'h2':c.get('H2','—'),'h3':c.get('H3','—'),'h4':c.get('H4','—')}
    except Exception:return {'active':False}

@core.app.route('/api/nova/strong-mobile')
def nova_strong_mobile_api():return core.jsonify({'ok':True,**_strong_mobile_status()})

@core.app.route('/api/nova/diagnostics')
def nova_diagnostics_api():
    sm=_strong_mobile_status(); c=core.cfg(); port=c.get('ListenPort','1234'); ss=core.cmd('ss','-lun').stdout or ''
    udp_ok=any((':'+str(port)+' ') in x or ('0.0.0.0:'+str(port)) in x for x in ss.splitlines()); ps=core.peers(); now=int(time.time())
    handshakes=sum(1 for x in ps.values() if x.get('handshake') and now-x['handshake']<=180)
    return core.jsonify({'ok':True,'awg':core.online(),'strong_mobile':sm['active'],'udp_listen':udp_ok,'port':port,'online_peers':handshakes,'peer_count':len(ps)})

def _find_endpoint(path):
    for rule in core.app.url_map.iter_rules():
        if rule.rule==path:return rule.endpoint
    return None

def _enhanced_obfuscation():
    s=_strong_mobile_status(); state='ACTIVE' if s.get('active') else 'INACTIVE'; cls='' if s.get('active') else 'bad'
    body=f'''<div class="hero"><div><div class="eyebrow">SECURITY PROFILE</div><h1>Strong Mobile</h1><p>Живой профиль маскировки AmneziaWG для мобильных сетей.</p></div></div><div class="nova-status {cls}"><div class="pulse"></div><div><b>Strong Mobile: {state}</b><small>Проверено по работающему awg0 и текущему конфигу</small></div></div><div class="card"><div class="toolbar"><h2>Параметры профиля</h2><span class="badge {'on' if s.get('active') else 'off'}">{state}</span></div><div class="kv"><div><span>MTU</span><b>{s.get('mtu','—')}</b></div><div><span>Jc</span><b>{s.get('jc','—')}</b></div><div><span>Jmin / Jmax</span><b>{s.get('jmin','—')} / {s.get('jmax','—')}</b></div><div><span>S1 / S2</span><b>{s.get('s1','—')} / {s.get('s2','—')}</b></div><div><span>S3 / S4</span><b>{s.get('s3','—')} / {s.get('s4','—')}</b></div><div><span>H1 / H2 / H3 / H4</span><b>{s.get('h1','—')} / {s.get('h2','—')} / {s.get('h3','—')} / {s.get('h4','—')}</b></div></div></div><div class="card" style="margin-top:14px"><div class="toolbar"><h2>Быстрая диагностика</h2><a class="btn secondary" href="/diagnostics">Открыть диагностику</a></div><div class="diag-grid"><div class="diag-item"><b>AWG интерфейс</b><span>{'Работает' if core.online() else 'Не работает'}</span></div><div class="diag-item"><b>UDP {core.cfg().get('ListenPort','1234')}</b><span>Проверяется через слушающий сокет</span></div><div class="diag-item"><b>Junk / S-параметры</b><span>{'Применены' if s.get('active') else 'Требуют проверки'}</span></div><div class="diag-item"><b>Header Protection</b><span>{'H1–H4 заданы' if all(s.get(k) not in (None,'—','') for k in ('h1','h2','h3','h4')) else 'Не задано'}</span></div></div></div>'''
    return core.layout('Strong Mobile',body,'/obfuscation')

def _enhanced_diagnostics():
    s=_strong_mobile_status(); now=int(time.time()); ps=core.peers(); recent=sum(1 for x in ps.values() if x.get('handshake') and now-x['handshake']<=180); port=core.cfg().get('ListenPort','1234'); udp=core.cmd('ss','-lun').stdout or ''; udp_ok=any((':'+str(port)+' ') in x or ('0.0.0.0:'+str(port)) in x for x in udp.splitlines())
    checks=[('AWG service',core.online(),'awg-quick@awg0 active'),('Strong Mobile',s.get('active',False),'live obfuscation parameters'),('UDP listener',udp_ok,f'UDP {port} listening'),('Recent handshakes',recent>0 if ps else True,f'{recent} peer(s) active')]
    items=''.join(f'<div class="diag-item"><b>{"✓" if ok else "✕"} {name}</b><span>{detail}</span></div>' for name,ok,detail in checks)
    body=f'''<div class="hero"><div><div class="eyebrow">SYSTEM CHECK</div><h1>Диагностика</h1><p>Проверка VPN от сервиса до подключённых клиентов.</p></div><a class="btn" href="/diagnostics">↻ Обновить</a></div><div class="card"><div class="toolbar"><h2>Состояние системы</h2><span class="badge {'on' if all(x[1] for x in checks) else 'warn'}">{'ВСЁ OK' if all(x[1] for x in checks) else 'ТРЕБУЕТ ВНИМАНИЯ'}</span></div><div class="diag-grid">{items}</div></div><div class="card" style="margin-top:14px"><h2 style="margin-top:0">Активные соединения</h2><p class="muted">Последний handshake считается активным в течение 180 секунд.</p><div class="kv"><div><span>Peers</span><b>{len(ps)}</b></div><div><span>Online</span><b class="ok">{recent}</b></div><div><span>UDP</span><b>{port}</b></div><div><span>Strong Mobile</span><b class="{'ok' if s.get('active') else 'bad'}">{'ACTIVE' if s.get('active') else 'INACTIVE'}</b></div></div></div>'''
    return core.layout('Диагностика',body,'/diagnostics')

ob_ep=_find_endpoint('/obfuscation')
if ob_ep:core.app.view_functions[ob_ep]=_enhanced_obfuscation
diag_ep=_find_endpoint('/diagnostics')
if diag_ep:core.app.view_functions[diag_ep]=_enhanced_diagnostics

_original_nav = core.nav
def _nova_nav(path):
    html = _original_nav(path)
    active = 'active' if path.startswith('/keenetic') else ''
    link = f'<a class="keenetic-nav {active}" href="/keenetic"><i>🛜</i>Настроить Keenetic</a>'
    if 'href="/keenetic"' not in html:
        html += link
    return html
core.nav = _nova_nav

@core.app.route('/keenetic/setup')
def keenetic_setup_redirect():
    return redirect('/keenetic')

@core.app.route('/api/keenetic/ping')
def keenetic_ping():
    if not core.session.get('logged'):
        return core.jsonify({'error':'auth required'}),401
    try:
        iface='awg-keenetic'; link=core.cmd('ip','link','show',iface); show=core.cmd('awg','show',iface); ready=link.returncode==0 and show.returncode==0
        return core.jsonify({'ok':ready,'interface':iface,'exists':link.returncode==0,'awg':show.returncode==0,'message':'Keenetic bridge ready' if ready else 'Keenetic bridge requires attention'})
    except Exception as e:
        return core.jsonify({'ok':False,'error':str(e)}),500

@core.app.route('/api/traffic92')
def traffic92_compat():
    clients=core.client_stats(); return core.jsonify({'ok':True,'panel_version':core.VERSION,'awg_online':core.online(),'clients':clients,'online_clients':sum(1 for x in clients if x['online']),'rx':sum(x['rx'] for x in clients),'tx':sum(x['tx'] for x in clients)})

if __name__=='__main__':core.app.run(host='0.0.0.0',port=8080)
