#!/usr/bin/env python3
"""AWG Panel 9.0 launcher over the stable 8.x core."""
import sys,subprocess,shutil
from flask import render_template_string,jsonify
import app as core
sys.modules['app']=core
core.VERSION='9.0'; core.BG_VERSION='90'

for name in ('naiveproxy_panel','telegram_bot','system_panel','advanced_panel'):
    try:
        mod=__import__(name)
        if hasattr(mod,'register'): mod.register(core.app)
    except Exception as exc:
        core.app.logger.warning('Optional module %s unavailable: %s',name,exc)

if hasattr(core,'CSS'):
    core.CSS=core.CSS.replace('background.svg?v=82','background.svg?v=90')
    core.CSS=core.CSS.replace('</style>', '.metricrow{display:grid;grid-template-columns:80px 1fr 55px;gap:12px;align-items:center;margin:12px 0}.bar{height:10px;background:#102333;border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#13b69a,#168ff2);border-radius:99px}</style>')

def run(*args):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=5)
    except Exception:return subprocess.CompletedProcess(args,1,'','')

def service(name):return run('systemctl','is-active',name).stdout.strip()=='active'
def memory():
    d={}
    try:
        for line in open('/proc/meminfo'):
            k,v=line.split(':',1);d[k]=int(v.split()[0])*1024
    except Exception:pass
    total=d.get('MemTotal',0);avail=d.get('MemAvailable',0);return total,max(0,total-avail)
def network():
    rx=tx=0
    try:
        for line in open('/proc/net/dev'):
            if ':' not in line:continue
            n,data=line.split(':',1)
            if n.strip()=='lo':continue
            p=data.split();rx+=int(p[0]);tx+=int(p[8])
    except Exception:pass
    return rx,tx
def percent(a,b):return round(a/b*100,1) if b else 0
def fmt(n):
    n=float(n)
    units=('B','KB','MB','GB','TB')
    i=0
    while n>=1024 and i<len(units)-1:n/=1024;i+=1
    return f'{n:.1f} {units[i]}'
def up():
    try:
        s=float(open('/proc/uptime').read().split()[0]);return f'{int(s//86400)}д {int(s%86400//3600)}ч {int(s%3600//60)}м'
    except Exception:return '-'

@core.app.route('/api/health9')
def health9():
    total,used=memory();du=shutil.disk_usage('/');rx,tx=network()
    return jsonify(panel_version='9.0',awg_version='3.1',awg_online=service('awg-quick@awg0'),panel_online=service('awgpanel'),naive_online=service('naiveproxy'),telegram_online=service('awgpanel-telegram'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=rx,tx=tx,uptime=up())

def dashboard9():
    it=core.cfg();total,used=memory();du=shutil.disk_usage('/');rx,tx=network();awg=service('awg-quick@awg0');np=service('naiveproxy');tg=service('awgpanel-telegram')
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · CONTROL CENTER</div><h1>AWG Panel 9.0</h1><p>Единый Dashboard для VPS, AWG, клиентов, прокси и Telegram.</p></div><div class=pill>{{'🟢 ONLINE' if awg else '🔴 OFFLINE'}} · awg0</div></div><div class=grid><div class=card><div class=klabel>AWG 3.1</div><div class="kvalue {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class=muted>UDP {{port}} · MTU {{mtu}}</div></div><div class=card><div class=klabel>Клиенты</div><div class=kvalue>{{clients}}</div><div class=muted>CONF + QR</div></div><div class=card><div class=klabel>NaïveProxy</div><div class="kvalue {{'ok' if np else 'bad'}}">{{'ONLINE' if np else 'OFFLINE'}}</div><div class=muted>TCP service</div></div><div class=card><div class=klabel>Telegram</div><div class="kvalue {{'ok' if tg else 'bad'}}">{{'ONLINE' if tg else 'OFFLINE'}}</div><div class=muted>remote control</div></div></div><div class=card style="margin-top:15px"><h2>📊 Ресурсы VPS</h2><div class=metricrow><span>CPU</span><div class=bar><i id=cpuBar style="width:0%"></i></div><b id=cpu>—</b></div><div class=metricrow><span>RAM</span><div class=bar><i style="width:{{ram}}%"></i></div><b>{{ram}}%</b></div><div class=metricrow><span>DISK</span><div class=bar><i style="width:{{disk}}%"></i></div><b>{{disk}}%</b></div><p class=muted>↓ {{rx}} · ↑ {{tx}} · Uptime {{uptime}}</p></div><div class=card style="margin-top:15px"><h2>⚡ Быстрые действия</h2><div class=actions><a class=action href=/clients>♟<strong>Клиенты</strong><span class=muted>Создать / CONF / QR</span></a><a class=action href=/obfuscation>◇<strong>Strong Mobile</strong><span class=muted>443 · 1280 · 4/40/120</span></a><a class=action href=/diagnostics>🩺<strong>Диагностика</strong><span class=muted>Проверить VPS</span></a><a class=action href=/backups>💾<strong>Backup</strong><span class=muted>Конфиг + база</span></a></div></div><div class=two><div class=card><h2>🛡 Strong Mobile</h2><table><tr><td>UDP</td><td>{{port}}</td></tr><tr><td>MTU</td><td>{{mtu}}</td></tr><tr><td>Jc/Jmin/Jmax</td><td>4 / 40 / 120</td></tr><tr><td>S1-S4</td><td>16 / 24 / 16 / 32</td></tr><tr><td>H1-H4</td><td>1 / 2 / 3 / 4</td></tr><tr><td>RandomTrailers</td><td>ON</td></tr><tr><td>DisableCookies</td><td>ON</td></tr></table></div><div class=card><h2>🔐 Безопасность</h2><p>Секретные ключи не показываются на Dashboard.</p><p>Telegram ограничивается разрешёнными ID.</p><p>NaïveProxy хранит секреты вне веб-интерфейса.</p></div></div><script>fetch('/api/system').then(r=>r.json()).then(x=>{cpu.textContent=x.cpu+'%';cpuBar.style.width=x.cpu+'%'}).catch(()=>{});</script>''',awg=awg,np=np,tg=tg,port=it.get('ListenPort','443'),mtu=it.get('MTU','1280'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=fmt(rx),tx=fmt(tx),uptime=up())
    return core.layout('Dashboard 9.0',body,'/')

core.app.view_functions['dashboard']=dashboard9

def about9():
    it=core.cfg();body=render_template_string('''<div class=hero><div><div class=eyebrow>FREE YOUR MIND</div><h1>О панели</h1><p>AWG Panel 9.0 · AmneziaWG 3.1.</p></div></div><div class=two><div class=card><h2>AWG Panel 9.0</h2><table><tr><td>Версия</td><td>9.0</td></tr><tr><td>AmneziaWG</td><td>3.1</td></tr><tr><td>Профиль</td><td>Strong Mobile</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr></table></div><div class=card><h2>Модули</h2><p>📊 Dashboard Pro · VPS metrics</p><p>🩺 Diagnostics · health checks</p><p>🚀 NaïveProxy · TCP/TLS</p><p>🤖 Telegram Bot · remote control</p><p>💾 Backup · config + DB</p></div></div>''',port=it.get('ListenPort','-'))
    return core.layout('О панели',body,'/about')
core.app.view_functions['about']=about9

if __name__=='__main__':core.app.run(host='0.0.0.0',port=8080)
