#!/usr/bin/env python3
"""AWG Panel 9.3 - responsive mobile control center over the stable 8.x core."""
import sys,subprocess,shutil,time,re,os
from flask import render_template_string,jsonify,request,redirect,session
import app as core
sys.modules['app']=core
core.VERSION='9.3'; core.BG_VERSION='93'

for name in ('naiveproxy_panel','telegram_bot','system_panel','advanced_panel'):
    try:
        mod=__import__(name)
        if hasattr(mod,'register'): mod.register(core.app)
    except Exception as exc:
        core.app.logger.warning('Optional module %s unavailable: %s',name,exc)

if hasattr(core,'CSS'):
    core.CSS=core.CSS.replace('background.svg?v=82','background.svg?v=93')
    core.CSS=core.CSS.replace('</style>', '''
/* AWG Panel 9.3 responsive/mobile skin */
html,body{overflow-x:hidden}.shell{min-height:100vh}.side{overflow-y:auto;overflow-x:hidden;scrollbar-width:thin}.menu{gap:5px}.menu a{padding:10px 12px;border-radius:9px;font-size:14px}.sidebox{margin-top:16px}.main{min-width:0}.top{height:64px}.hero{margin:12px 0 18px}.hero h1{font-size:36px}.hero p{font-size:16px}.card{padding:16px;border-radius:13px}.actions{gap:9px}.action{padding:13px;min-height:88px}.action strong{font-size:15px;margin:5px 0}.btn,button{padding:8px 11px;border-radius:8px;font-size:13px}.progrid{gap:10px}.metricrow{grid-template-columns:62px 1fr 48px;gap:8px;margin:9px 0}.bar{height:7px}.statusrow{padding:9px 0;font-size:13px}
@media(max-width:760px){
 html,body{font-size:14px}
 .shell{display:block;min-height:100vh}
 .side{position:sticky;top:0;z-index:10;width:100%;height:auto;max-height:52vh;padding:9px 10px;background:#030d1cf7;box-shadow:0 5px 20px #0008}
 .brand{margin:0 3px 8px;gap:9px}.logo{width:38px;height:38px;border-radius:10px}.brand h2{font-size:16px}.brand small{font-size:10px}
 .menu{display:block;max-height:31vh;overflow-y:auto;padding-right:2px;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
 .menu a{display:block;margin:3px 0;padding:8px 10px;font-size:13px;line-height:1.25}
 .sidebox{display:none}
 .main{padding:0 10px 20px}.top{margin:0 -10px 12px;padding:0 10px;height:52px}.top .pill{padding:6px 8px;font-size:11px}.top .btn{padding:6px 8px;font-size:11px}
 .hero{align-items:flex-start;gap:8px;flex-direction:column;margin:10px 0 14px}.hero h1{font-size:27px;margin:4px 0}.hero p{font-size:14px}.eyebrow{font-size:10px}
 .progrid,.grid,.actions,.two,.awgform{grid-template-columns:1fr;gap:9px}
 .card{padding:13px;margin-top:0!important}.kvalue{font-size:24px}.action{min-height:0;padding:11px}.action strong{font-size:14px}
 table{font-size:12px;display:block;overflow-x:auto;white-space:nowrap}th,td{padding:8px 6px}.clientform{grid-template-columns:1fr;gap:6px}.clientform button{width:100%}
 input{padding:9px;margin:5px 0 9px}label{font-size:12px}
 .footer{margin-top:18px}
}
@media(max-width:380px){.menu a{padding:7px 9px;font-size:12px}.brand h2{font-size:15px}.main{padding-left:8px;padding-right:8px}.top{margin-left:-8px;margin-right:-8px;padding-left:8px;padding-right:8px}}
''</style>''')

def run(*args,timeout=5):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    except Exception as e:return subprocess.CompletedProcess(args,1,'',str(e))
def service(name): return run('systemctl','is-active',name).stdout.strip()=='active'
def memory():
    d={}
    try:
        for line in open('/proc/meminfo'):
            k,v=line.split(':',1);d[k]=int(v.split()[0])*1024
    except Exception: pass
    total=d.get('MemTotal',0);avail=d.get('MemAvailable',0);return total,max(0,total-avail)
def network(iface=None):
    rx=tx=0
    try:
        for line in open('/proc/net/dev'):
            if ':' not in line: continue
            n,data=line.split(':',1);n=n.strip()
            if n=='lo' or (iface and n!=iface): continue
            p=data.split();rx+=int(p[0]);tx+=int(p[8])
    except Exception: pass
    return rx,tx
def percent(a,b): return round(a/b*100,1) if b else 0
def fmt(n):
    n=float(n);u=('B','KB','MB','GB','TB');i=0
    while n>=1024 and i<len(u)-1:n/=1024;i+=1
    return f'{n:.1f} {u[i]}'
def uptime():
    try:
        s=float(open('/proc/uptime').read().split()[0]);return f'{int(s//86400)}д {int(s%86400//3600)}ч {int(s%3600//60)}м'
    except Exception:return '-'
def ports():
    r=run('ss','-lntup',timeout=5);return [x.strip() for x in r.stdout.splitlines()[1:] if x.strip()]
def ufw():
    r=run('ufw','status');return r.stdout.strip() if r.returncode==0 else 'UFW не установлен или недоступен'
def tls_status():
    domain=core.setting('endpoint','')
    if not domain:return {'configured':False,'domain':'','cert':'не настроен'}
    cert=run('openssl','s_client','-connect',f'{domain}:443','-servername',domain,'-brief',timeout=6)
    return {'configured':True,'domain':domain,'cert':'доступен' if cert.returncode==0 else 'не проверен'}

@core.app.route('/api/health9')
def health9():
    total,used=memory();du=shutil.disk_usage('/');rx,tx=network()
    return jsonify(panel_version='9.3',awg_version='3.1',awg_online=service('awg-quick@awg0'),panel_online=service('awgpanel'),naive_online=service('naiveproxy'),telegram_online=service('awgpanel-telegram'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=rx,tx=tx,ts=int(time.time()),uptime=uptime())

@core.app.route('/api/traffic92')
def traffic92():
    rx,tx=network('awg0');return jsonify(ts=int(time.time()),rx=rx,tx=tx,rx_h=fmt(rx),tx_h=fmt(tx))

@core.app.route('/api/clients92')
def clients92():
    return jsonify(clients=[{'id':r['id'],'name':r['name'],'address':r['address'],'conf':f"/clients/{r['id']}/conf",'qr':f"/clients/{r['id']}/qr"} for r in core.rows()])

@core.app.route('/security')
def security92():
    tls=tls_status();checks=[('AWG service',service('awg-quick@awg0'),'Работает'),('Panel service',service('awgpanel'),'Работает'),('UFW',not ufw().startswith('UFW не'),'Проверка доступна'),('SSH',service('ssh') or service('sshd'),'Сервис SSH активен'),('TLS endpoint',tls['configured'] and tls['cert']=='доступен','HTTPS доступен'),('Panel secret',os.getenv('AWGPANEL_SECRET','change-this-secret')!='change-this-secret','Секрет изменён')]
    body=render_template_string('''<div class=hero><div><div class=eyebrow>SECURITY CENTER</div><h1>Безопасность</h1><p>Безопасная диагностика VPS без изменения сетевой конфигурации.</p></div></div><div class=card>{% for n,ok,d in checks %}<div class=statusrow><span>{{n}}</span><b class="{{'good' if ok else 'bad'}}">{{'🟢 OK' if ok else '🔴 CHECK'}}</b><span class=muted>{{d}}</span></div>{% endfor %}</div><div class="card warn" style="margin-top:16px"><b>HTTPS</b><p>Для автоматической выдачи сертификата нужен домен, направленный на VPS.</p><a class=btn href=/settings>Настроить endpoint</a></div>''',checks=checks)
    return core.layout('Security Center',body,'/security')

@core.app.route('/firewall')
def firewall92():
    body=render_template_string('''<div class=hero><div><div class=eyebrow>FIREWALL CENTER</div><h1>Firewall</h1><p>Только просмотр текущего состояния.</p></div></div><div class=card><h2>UFW</h2><pre>{{ufw}}</pre></div><div class=card style="margin-top:16px"><h2>Слушающие порты</h2><pre>{{ports}}</pre></div>''',ufw=ufw(),ports='\n'.join(ports()) or 'Нет данных')
    return core.layout('Firewall Center',body,'/firewall')

def dashboard92():
    it=core.cfg();total,used=memory();du=shutil.disk_usage('/');rx,tx=network('awg0');awg=service('awg-quick@awg0');np=service('naiveproxy');tg=service('awgpanel-telegram');clients=core.rows()
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · CONTROL CENTER</div><h1>AWG Panel 9.3</h1><p>Мобильный Pro Dashboard.</p></div><div class=pill>{{'🟢 ONLINE' if awg else '🔴 OFFLINE'}} · awg0</div></div><div class=progrid><div class=card><div class=klabel>AWG 3.1</div><div class="kvalue {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class=muted>UDP {{port}} · MTU {{mtu}}</div></div><div class=card><div class=klabel>Клиенты</div><div class=kvalue>{{clients|length}}</div><div class=muted>активные профили</div></div><div class=card><div class=klabel>NaïveProxy</div><div class="kvalue {{'ok' if np else 'bad'}}">{{'ONLINE' if np else 'OFFLINE'}}</div></div><div class=card><div class=klabel>Telegram</div><div class="kvalue {{'ok' if tg else 'bad'}}">{{'ONLINE' if tg else 'OFFLINE'}}</div></div></div><div class=card style="margin-top:16px"><h2>📈 Live Traffic <span class=muted id=rate>ожидание</span></h2><canvas id=traffic width=1000 height=230 style="width:100%;height:180px"></canvas><div class=two><div><b>↓ RX</b> <span id=rx>{{fmt(rx)}}</span></div><div><b>↑ TX</b> <span id=tx>{{fmt(tx)}}</span></div></div></div><div class=two><div class=card><h2>👥 Клиенты</h2><form class=clientform method=post action=/clients/create><div><label>Новый клиент</label><input name=name placeholder="iPhone-Alex" required></div><button>+ Создать</button></form><table style="margin-top:12px"><tr><th>Имя</th><th>IP</th><th>Действия</th></tr>{% for c in clients %}<tr><td>{{c.name}}</td><td>{{c.address}}</td><td><a class=btn href="/clients/{{c.id}}/conf">CONF</a> <a class=btn href="/clients/{{c.id}}/qr">QR</a></td></tr>{% else %}<tr><td colspan=3 class=muted>Клиентов нет</td></tr>{% endfor %}</table></div><div class=card><h2>🩺 VPS</h2><div class=metricrow><span>RAM</span><div class=bar><i style="width:{{ram}}%"></i></div><b>{{ram}}%</b></div><div class=metricrow><span>DISK</span><div class=bar><i style="width:{{disk}}%"></i></div><b>{{disk}}%</b></div><p>Uptime: <b>{{uptime}}</b></p><div class=actions><a class=action href=/security>🔐<strong>Security</strong><span class=muted>VPS</span></a><a class=action href=/firewall>🔥<strong>Firewall</strong><span class=muted>UFW</span></a><a class=action href=/obfuscation>🛡<strong>Obfuscation</strong><span class=muted>Strong Mobile</span></a><a class=action href=/backups>💾<strong>Backup</strong><span class=muted>Конфигурация</span></a></div></div></div><div class=card style="margin-top:16px"><h2>🛡 Strong Mobile</h2><table><tr><td>UDP</td><td>{{port}}</td></tr><tr><td>MTU</td><td>{{mtu}}</td></tr><tr><td>Jc/Jmin/Jmax</td><td>4 / 40 / 120</td></tr><tr><td>S1-S4</td><td>16 / 24 / 16 / 32</td></tr><tr><td>H1-H4</td><td>1 / 2 / 3 / 4</td></tr><tr><td>RandomTrailers</td><td>ON</td></tr><tr><td>DisableCookies</td><td>ON</td></tr></table></div><script>
const c=document.getElementById('traffic'),x=c.getContext('2d'),pts=[];let last=null,lastTs=null;function draw(){x.clearRect(0,0,c.width,c.height);if(pts.length<2)return;let max=Math.max(1,...pts.map(p=>Math.max(p.rx,p.tx)));x.beginPath();pts.forEach((p,i)=>{let px=i*(c.width-20)/Math.max(1,pts.length-1)+10,py=c.height-20-(p.rx/max)*(c.height-40);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke();x.beginPath();pts.forEach((p,i)=>{let px=i*(c.width-20)/Math.max(1,pts.length-1)+10,py=c.height-20-(p.tx/max)*(c.height-40);i?x.lineTo(px,py):x.moveTo(px,py)});x.stroke()}async function tick(){try{let d=await fetch('/api/traffic92',{cache:'no-store'}).then(r=>r.json());let now=Date.now(),rr=0,tt=0;if(last&&lastTs){let sec=Math.max(.1,(now-lastTs)/1000);rr=Math.max(0,d.rx-last.rx)/sec;tt=Math.max(0,d.tx-last.tx)/sec;document.getElementById('rate').textContent='· ↓ '+(rr/1048576).toFixed(2)+' MB/s · ↑ '+(tt/1048576).toFixed(2)+' MB/s'}last=d;lastTs=now;document.getElementById('rx').textContent=d.rx_h;document.getElementById('tx').textContent=d.tx_h;pts.push({rx:rr,tx:tt});if(pts.length>50)pts.shift();draw()}catch(e){}}tick();setInterval(tick,3000);</script>''',awg=awg,np=np,tg=tg,clients=clients,port=it.get('ListenPort','-'),mtu=it.get('MTU','-'),ram=percent(used,total),disk=percent(du.used,du.total),rx=rx,tx=tx,fmt=fmt,uptime=uptime())
    return core.layout('Dashboard 9.3',body,'/')
core.app.view_functions['dashboard']=dashboard92

@core.app.route('/about')
def about92():
    it=core.cfg();body=render_template_string('''<div class=hero><div><div class=eyebrow>FREE YOUR MIND</div><h1>О панели</h1><p>AWG Panel 9.3 · AmneziaWG 3.1.</p></div></div><div class=two><div class=card><h2>AWG Panel 9.3</h2><table><tr><td>Версия</td><td>9.3</td></tr><tr><td>AmneziaWG</td><td>3.1</td></tr><tr><td>Профиль</td><td>Strong Mobile</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr></table></div><div class=card><h2>Pro modules</h2><p>📈 Live Traffic</p><p>👥 Client Manager</p><p>🔐 Security Center</p><p>🔥 Firewall Center</p><p>🛡 Strong Mobile</p></div></div>''',port=it.get('ListenPort','-'))
    return core.layout('О панели',body,'/about')

if __name__=='__main__':core.app.run(host='0.0.0.0',port=8080)
