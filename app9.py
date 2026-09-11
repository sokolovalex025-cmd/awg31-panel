#!/usr/bin/env python3
"""AWG Panel 9.0 - dashboard layer over the stable 8.x core."""
import sys,subprocess,shutil,time,re
from flask import render_template_string,jsonify,request,redirect
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
    core.CSS=core.CSS.replace('</style>', '''.metricrow{display:grid;grid-template-columns:70px 1fr 58px;gap:12px;align-items:center;margin:12px 0}.bar{height:10px;background:#102333;border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#13b69a,#168ff2);border-radius:99px}.traffic{height:180px;width:100%;display:block;background:#061321;border:1px solid #4bb1f033;border-radius:12px}.clientrow{display:grid;grid-template-columns:1fr 130px 190px;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid #82aacd22}.client-actions{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}.danger{background:#8f3040}.mini{padding:7px 10px;font-size:13px}@media(max-width:800px){.clientrow{grid-template-columns:1fr}.client-actions{justify-content:flex-start}}</style>''')

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
    n=float(n);units=('B','KB','MB','GB','TB');i=0
    while n>=1024 and i<len(units)-1:n/=1024;i+=1
    return f'{n:.1f} {units[i]}'
def up():
    try:
        s=float(open('/proc/uptime').read().split()[0]);return f'{int(s//86400)}д {int(s%86400//3600)}ч {int(s%3600//60)}м'
    except Exception:return '-'

def client_safe(r):
    return {'id':r['id'],'name':r['name'],'address':r['address'],'created':r['created']}

@core.app.route('/api/health9')
def health9():
    total,used=memory();du=shutil.disk_usage('/');rx,tx=network()
    return jsonify(panel_version='9.0',awg_version='3.1',timestamp=time.time(),awg_online=service('awg-quick@awg0'),panel_online=service('awgpanel'),naive_online=service('naiveproxy'),telegram_online=service('awgpanel-telegram'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=rx,tx=tx,uptime=up())

@core.app.route('/api/clients9')
def clients9():
    return jsonify(clients=[client_safe(r) for r in core.rows()])

@core.app.route('/clients/<int:cid>/delete',methods=['POST'])
def delete_client9(cid):
    c=core.db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
    if not r:c.close();return 'Клиент не найден',404
    pub=r['public_key'];conf=core.CONF
    old=conf.read_text() if conf.exists() else ''
    if pub and old:
        blocks=old.split('[Peer]')
        head=blocks[0];kept=[]
        for block in blocks[1:]:
            if re.search(r'^\s*PublicKey\s*=\s*'+re.escape(pub)+r'\s*$',block,re.M):continue
            kept.append(block)
        new=head+'[Peer]'.join(kept)
        bak=conf.with_name(conf.name+'.bak-delete-'+time.strftime('%Y%m%d-%H%M%S'))
        bak.write_text(old);conf.write_text(new)
    c.execute('DELETE FROM clients WHERE id=?',(cid,));c.commit();c.close()
    r=run('systemctl','restart','awg-quick@awg0')
    if r.returncode and old and conf.exists():
        conf.write_text(old);run('systemctl','restart','awg-quick@awg0')
        return 'Не удалось применить удаление AWG; конфигурация восстановлена.',500
    return redirect('/')

def dashboard9():
    it=core.cfg();total,used=memory();du=shutil.disk_usage('/');rx,tx=network();awg=service('awg-quick@awg0');np=service('naiveproxy');tg=service('awgpanel-telegram')
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · CONTROL CENTER</div><h1>AWG Panel 9.0</h1><p>Единый Dashboard для VPS, AWG, клиентов, прокси и Telegram.</p></div><div class=pill>{{'🟢 ONLINE' if awg else '🔴 OFFLINE'}} · awg0</div></div><div class=grid><div class=card><div class=klabel>AWG 3.1</div><div class="kvalue {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class=muted>UDP {{port}} · MTU {{mtu}}</div></div><div class=card><div class=klabel>Клиенты</div><div class=kvalue id=clientCount>{{clients}}</div><div class=muted>CONF + QR</div></div><div class=card><div class=klabel>NaïveProxy</div><div class="kvalue {{'ok' if np else 'bad'}}">{{'ONLINE' if np else 'OFFLINE'}}</div><div class=muted>TCP service</div></div><div class=card><div class=klabel>Telegram</div><div class="kvalue {{'ok' if tg else 'bad'}}">{{'ONLINE' if tg else 'OFFLINE'}}</div><div class=muted>remote control</div></div></div><div class=card style="margin-top:15px"><h2>📈 Трафик в реальном времени</h2><canvas id=traffic class=traffic height=180></canvas><p class=muted>Суммарный RX/TX всех интерфейсов VPS. Обновление каждые 3 секунды.</p></div><div class=card style="margin-top:15px"><h2>👥 Управление клиентами</h2><form method=post action=/clients/create style="display:grid;grid-template-columns:1fr auto;gap:10px;margin-bottom:14px"><input name=name placeholder="Имя нового клиента, например iPhone-02" required style="margin:0"><button>＋ Создать клиента</button></form><div id=clientsBox>{% for r in client_rows %}<div class=clientrow><div><b>{{r.name}}</b><div class=muted>{{r.address}}</div></div><div class=muted>ID #{{r.id}}</div><div class=client-actions><a class="btn mini" href="/clients/{{r.id}}/conf">CONF</a><a class="btn mini" href="/clients/{{r.id}}/qr">QR</a><form method=post action="/clients/{{r.id}}/delete" onsubmit="return confirm('Удалить клиента {{r.name}}?')" style="display:inline"><button class="btn mini danger">Удалить</button></form></div></div>{% else %}<p class=muted>Клиентов пока нет.</p>{% endfor %}</div><p style="margin-top:14px"><a class="btn alt" href=/clients>Открыть полный раздел клиентов →</a></p></div><div class=card style="margin-top:15px"><h2>📊 Ресурсы VPS</h2><div class=metricrow><span>CPU</span><div class=bar><i id=cpuBar></i></div><b id=cpu>—</b></div><div class=metricrow><span>RAM</span><div class=bar><i style="width:{{ram}}%"></i></div><b>{{ram}}%</b></div><div class=metricrow><span>DISK</span><div class=bar><i style="width:{{disk}}%"></i></div><b>{{disk}}%</b></div><p class=muted>↓ {{rx}} · ↑ {{tx}} · Uptime {{uptime}}</p></div><div class=card style="margin-top:15px"><h2>⚡ Быстрые действия</h2><div class=actions><a class=action href=/clients>♟<strong>Клиенты</strong><span class=muted>Создать / CONF / QR</span></a><a class=action href=/obfuscation>◇<strong>Strong Mobile</strong><span class=muted>443 · 1280 · 4/40/120</span></a><a class=action href=/diagnostics>🩺<strong>Диагностика</strong><span class=muted>Проверить VPS</span></a><a class=action href=/backups>💾<strong>Backup</strong><span class=muted>Конфиг + база</span></a></div></div><div class=two><div class=card><h2>🛡 Strong Mobile</h2><table><tr><td>UDP</td><td>{{port}}</td></tr><tr><td>MTU</td><td>{{mtu}}</td></tr><tr><td>Jc/Jmin/Jmax</td><td>4 / 40 / 120</td></tr><tr><td>S1-S4</td><td>16 / 24 / 16 / 32</td></tr><tr><td>H1-H4</td><td>1 / 2 / 3 / 4</td></tr><tr><td>RandomTrailers</td><td>ON</td></tr><tr><td>DisableCookies</td><td>ON</td></tr></table></div><div class=card><h2>🔐 Безопасность</h2><p>Секретные ключи не показываются на Dashboard.</p><p>Telegram ограничивается разрешёнными ID.</p><p>NaïveProxy хранит секреты вне веб-интерфейса.</p></div></div><script>
const traffic={rx:[],tx:[],last:null};
function draw(){const c=document.getElementById('traffic'),x=c.getContext('2d'),w=c.width=c.clientWidth*devicePixelRatio,h=c.height=180*devicePixelRatio;x.clearRect(0,0,w,h);const all=traffic.rx.concat(traffic.tx),mx=Math.max(1,...all),n=Math.max(traffic.rx.length,2);x.beginPath();traffic.rx.forEach((v,i)=>{const px=i/(n-1)*w,py=h-12-(v/mx)*(h-24);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#13b69a';x.lineWidth=2*devicePixelRatio;x.stroke();x.beginPath();traffic.tx.forEach((v,i)=>{const px=i/(n-1)*w,py=h-12-(v/mx)*(h-24);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#168ff2';x.stroke();x.font=12*devicePixelRatio+'px Segoe UI';x.fillStyle='#91a8bd';x.fillText('RX',12*devicePixelRatio,20*devicePixelRatio);x.fillText('TX',48*devicePixelRatio,20*devicePixelRatio)}
async function poll(){try{const r=await fetch('/api/health9',{cache:'no-store'}),d=await r.json();if(traffic.last){const dt=Math.max(.5,(d.timestamp-traffic.last.t));traffic.rx.push(Math.max(0,(d.rx-traffic.last.rx)/dt/1024));traffic.tx.push(Math.max(0,(d.tx-traffic.last.tx)/dt/1024));if(traffic.rx.length>40){traffic.rx.shift();traffic.tx.shift()}}traffic.last={t:d.timestamp,rx:d.rx,tx:d.tx};document.getElementById('clientCount').textContent=d.clients;draw()}catch(e){}}window.addEventListener('resize',draw);poll();setInterval(poll,3000);fetch('/api/system').then(r=>r.json()).then(x=>{cpu.textContent=x.cpu+'%';cpuBar.style.width=x.cpu+'%'}).catch(()=>{});</script>''',awg=awg,np=np,tg=tg,port=it.get('ListenPort','443'),mtu=it.get('MTU','1280'),clients=len(core.rows()),client_rows=core.rows(),ram=percent(used,total),disk=percent(du.used,du.total),rx=fmt(rx),tx=fmt(tx),uptime=up())
    return core.layout('Dashboard 9.0',body,'/')

core.app.view_functions['dashboard']=dashboard9

def about9():
    it=core.cfg();body=render_template_string('''<div class=hero><div><div class=eyebrow>FREE YOUR MIND</div><h1>О панели</h1><p>AWG Panel 9.0 · AmneziaWG 3.1.</p></div></div><div class=two><div class=card><h2>AWG Panel 9.0</h2><table><tr><td>Версия</td><td>9.0</td></tr><tr><td>AmneziaWG</td><td>3.1</td></tr><tr><td>Профиль</td><td>Strong Mobile</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr></table></div><div class=card><h2>Модули</h2><p>📊 Dashboard Pro · VPS metrics</p><p>📈 Traffic Graph · realtime</p><p>👥 Client Manager · create/delete/CONF/QR</p><p>🩺 Diagnostics · health checks</p><p>🚀 NaïveProxy · TCP/TLS</p><p>🤖 Telegram Bot · remote control</p><p>💾 Backup · config + DB</p></div></div>''',port=it.get('ListenPort','-'))
    return core.layout('О панели',body,'/about')
core.app.view_functions['about']=about9

if __name__=='__main__':core.app.run(host='0.0.0.0',port=8080)
