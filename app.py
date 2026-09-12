#!/usr/bin/env python3
from flask import Flask, request, redirect, session, render_template_string, send_file, jsonify, Response
from pathlib import Path
import sqlite3, subprocess, time, os, re, io, qrcode, sys, shutil

BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'; CONF=Path('/etc/amnezia/amneziawg/awg0.conf')
if not CONF.exists(): CONF=Path('/etc/wireguard/awg0.conf')
BG=BASE/'background.svg'
app=Flask(__name__)
app.secret_key=os.getenv('AWGPANEL_SECRET','change-this-secret')
sys.modules.setdefault('app',sys.modules[__name__])
VERSION='10.0'; BG_VERSION='NOVA'

CSS='''<style>
:root{--bg:#070b12;--panel:#0d131d;--panel2:#111925;--line:#202c3b;--text:#f4f7fb;--muted:#8290a3;--accent:#4f8cff;--accent2:#37d6a3;--danger:#ff647c;--warn:#f5b84b;--shadow:0 18px 60px #0008}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font:14px Inter,Segoe UI,Arial,sans-serif;color:var(--text);background:var(--bg)}body:before{content:"";position:fixed;inset:0;background:radial-gradient(circle at 15% 10%,#164b8b28,transparent 35%),radial-gradient(circle at 85% 85%,#08785a18,transparent 32%),linear-gradient(#070b12ee,#070b12f8),url('/background.svg?v=NOVA');background-size:auto,auto,auto,cover;background-position:center;z-index:-2}a{color:inherit}.app{min-height:100vh;display:flex}.sidebar{position:fixed;z-index:20;left:0;top:0;bottom:0;width:255px;padding:22px 14px;background:#090f18eF;border-right:1px solid var(--line);backdrop-filter:blur(18px)}.brand{display:flex;gap:12px;align-items:center;padding:4px 9px 26px}.logo{width:43px;height:43px;border-radius:13px;background:linear-gradient(145deg,#4f8cff,#37d6a3);display:grid;place-items:center;font-weight:900;letter-spacing:-2px;box-shadow:0 8px 30px #1687ff40}.brand b{font-size:18px}.brand b span{color:#5ee0ba}.brand small{display:block;color:var(--muted);margin-top:3px}.section{margin:15px 8px 7px;color:#536173;font-size:10px;font-weight:800;letter-spacing:.13em;text-transform:uppercase}.nav{display:grid;gap:4px}.nav a{display:flex;align-items:center;gap:11px;padding:11px 12px;border:1px solid transparent;border-radius:11px;text-decoration:none;color:#9eabbb;font-weight:650}.nav a:hover{background:#151e2b;color:#fff}.nav a.active{background:#17263b;border-color:#28476b;color:#fff;box-shadow:inset 3px 0 var(--accent)}.nav i{font-style:normal;width:19px;text-align:center;font-size:16px}.server{position:absolute;left:14px;right:14px;bottom:17px;padding:13px;border:1px solid var(--line);border-radius:13px;background:#0d141e}.statusdot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;background:var(--accent2);box-shadow:0 0 12px #37d6a399}.off{background:var(--danger);box-shadow:0 0 12px #ff647c88}.server strong{font-size:13px}.server small{display:block;color:var(--muted);margin-top:7px}.main{width:calc(100% - 255px);margin-left:255px;padding:0 34px 45px}.topbar{height:70px;margin:0 -34px 26px;padding:0 34px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);background:#090f18d9;backdrop-filter:blur(18px);position:sticky;top:0;z-index:10}.topbar .title{font-weight:700}.top-actions{display:flex;gap:9px;align-items:center}.tag{padding:7px 10px;border:1px solid var(--line);background:#111a26;border-radius:999px;color:#aebaca;font-size:12px}.wrap{max-width:1450px;margin:auto}.hero{display:flex;justify-content:space-between;gap:25px;align-items:flex-end;margin:8px 0 25px}.eyebrow{color:#6d9dff;font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}.hero h1{font-size:34px;letter-spacing:-.035em;margin:7px 0 7px}.hero p{margin:0;color:var(--muted);font-size:15px}.card{background:#0d141eeF;border:1px solid var(--line);border-radius:15px;padding:19px;box-shadow:0 8px 30px #00018}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.metric{min-height:128px}.metric .label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:750}.metric .value{font-size:30px;font-weight:850;letter-spacing:-.04em;margin-top:13px}.metric .sub{color:#657487;font-size:12px;margin-top:5px}.ok{color:var(--accent2)}.bad{color:var(--danger)}.warn{color:var(--warn)}.blue{color:#72a5ff}.dashboard-grid{display:grid;grid-template-columns:1.45fr .75fr;gap:14px;margin-top:14px}.actions{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.action{display:block;padding:15px;border:1px solid var(--line);border-radius:12px;background:#101925;text-decoration:none}.action:hover{border-color:#31527a;transform:translateY(-1px)}.action b{display:block;margin:7px 0 4px}.action span{font-size:12px;color:var(--muted)}.btn,button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:9px;padding:10px 13px;background:linear-gradient(135deg,#4f8cff,#3473df);color:#fff;text-decoration:none;font-weight:750;cursor:pointer}.btn:hover,button:hover{filter:brightness(1.08)}.btn.secondary{background:#1a2431;border:1px solid var(--line)}.btn.danger{background:#4a1723;color:#ff9bab;border:1px solid #743044}.toolbar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:13px}.toolbar h2{margin:0;font-size:17px}.search{max-width:300px}.search input{margin:0}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:650px}th,td{text-align:left;padding:12px 9px;border-bottom:1px solid #1c2633}th{color:#66758a;font-size:10px;text-transform:uppercase;letter-spacing:.08em}td{color:#d9e1ea}.client-name{font-weight:700}.subline{display:block;color:#657487;font-size:11px;margin-top:3px}.badge{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:10px;font-weight:800}.badge.on{background:#0d352b;color:#59e0b8}.badge.off{background:#27151b;color:#ff8193}.badge.warn{background:#33280f;color:#f3c55e}.actions-row{white-space:nowrap;display:flex;gap:5px}.mini{padding:7px 9px;font-size:11px}.input, input, select{width:100%;padding:11px 12px;background:#09111b;color:#fff;border:1px solid #253346;border-radius:9px;outline:none}input:focus,select:focus{border-color:#3d6da8;box-shadow:0 0 0 3px #3d6da81c}label{display:block;color:#aab6c5;font-size:12px;font-weight:650;margin:12px 0 6px}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.notice{padding:12px;border-radius:10px;background:#101d2b;border:1px solid #24364b;color:#aab8c8;margin:12px 0}.notice.good{border-color:#1c5548;background:#0b241e}.notice.badbox{border-color:#60303b;background:#26131a}.kv{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}.kv div{padding:12px;background:#0d141e}.kv span{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}.code{background:#070d14;border:1px solid #182331;border-radius:10px;padding:14px;white-space:pre-wrap;overflow:auto;max-height:520px;font:12px Consolas,monospace;color:#b9c8d9}.footer{text-align:center;color:#526175;font-size:11px;margin-top:30px}.mobile-menu{display:none}.login{max-width:430px;margin:12vh auto;padding:24px}.login .brand{padding:0 0 22px}.muted{color:var(--muted)}
@media(max-width:1050px){.grid4{grid-template-columns:repeat(2,1fr)}.dashboard-grid,.split{grid-template-columns:1fr}}
@media(max-width:760px){.sidebar{transform:translateX(-100%);transition:.2s}.sidebar.open{transform:none}.main{width:100%;margin:0;padding:0 15px 35px}.topbar{margin:0 -15px 18px;padding:0 15px}.mobile-menu{display:inline-flex}.hero{align-items:flex-start;flex-direction:column}.hero h1{font-size:29px}.grid4{grid-template-columns:1fr 1fr}.formgrid{grid-template-columns:1fr}.actions{grid-template-columns:1fr}.server{display:none}}
@media(max-width:460px){.grid4{grid-template-columns:1fr}.tag{display:none}}
</style>'''

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def setting(k,d):
 c=db()
 for q in ('SELECT v FROM settings WHERE k=?','SELECT value FROM settings WHERE key=?'):
  try:
   r=c.execute(q,(k,)).fetchone()
   if r: c.close(); return list(r)[0]
  except sqlite3.Error: pass
 c.close(); return d

def cmd(*a):
 try:return subprocess.run(a,text=True,capture_output=True,timeout=30)
 except Exception as e:return subprocess.CompletedProcess(a,1,'',str(e))

def online():return cmd('systemctl','is-active','--quiet','awg-quick@awg0').returncode==0

def cfg():
 d={}
 if CONF.exists():
  for x in CONF.read_text(errors='replace').split('[Peer]',1)[0].splitlines():
   if '=' in x and not x.lstrip().startswith('#'):
    k,v=x.split('=',1);d[k.strip()]=v.strip()
 return d

def rows():
 c=db(); r=c.execute('SELECT * FROM clients ORDER BY id').fetchall(); c.close(); return r

def peers():
 out=cmd('awg','show','awg0','dump').stdout.strip().splitlines(); result={}
 if len(out)<2:return result
 for line in out[1:]:
  p=line.split('\t')
  if len(p)<8:continue
  pub=p[0]; endpoint=p[2]; hs=int(p[4] or 0) if p[4].isdigit() else 0
  result[pub]={'handshake':hs,'rx':int(p[5] or 0),'tx':int(p[6] or 0),'endpoint':endpoint}
 return result

def client_stats():
 ps=peers(); now=int(time.time()); out=[]
 for r in rows():
  s=ps.get(r['public_key'],{}); hs=s.get('handshake',0); out.append({'id':r['id'],'name':r['name'],'address':r['address'],'public_key':r['public_key'],'online':bool(hs and now-hs<=180),'handshake':hs,'rx':s.get('rx',0),'tx':s.get('tx',0),'endpoint':s.get('endpoint','—')})
 return out

def fmt_bytes(n):
 n=float(n or 0)
 for u in ('B','KB','MB','GB','TB'):
  if n<1024:return f'{n:.0f} {u}'
  n/=1024
 return f'{n:.1f} PB'

def fmt_time(ts):
 if not ts:return 'Нет handshake'
 return time.strftime('%d.%m.%Y %H:%M:%S',time.localtime(ts))

def nav(p):
 groups=[('ОБЗОР',[('⌂','Дашборд','/'),('◉','Активные клиенты','/active')]),('УПРАВЛЕНИЕ',[('♣','Клиенты','/clients'),('◇','Конфигурация','/config'),('◈','Strong Mobile','/obfuscation')]),('СИСТЕМА',[('⌘','Сеть и Firewall','/network'),('◌','Live Traffic','/traffic'),('✓','Диагностика','/diagnostics'),('▣','Резервные копии','/backups'),('☷','Логи','/logs')]),('ПАНЕЛЬ',[('⚙','Настройки','/settings'),('ⓘ','О NOVA','/about')])]
 s=''
 for title,items in groups:
  s+=f'<div class="section">{title}</div>'
  s+=''.join(f'<a class="{"active" if p==u else ""}" href="{u}"><i>{i}</i>{n}</a>' for i,n,u in items)
 return s

def layout(title,body,p):
 it=cfg(); cs=client_stats(); on=online(); active=sum(x['online'] for x in cs)
 return render_template_string(CSS+'''<div class=app><aside class=sidebar id=sidebar><div class=brand><div class=logo>NX</div><div><b>NOVA <span>10</span></b><small>Network Control Center</small></div></div><nav class=nav>{{nav|safe}}</nav><div class=server><span class="statusdot {{'' if on else 'off'}}"></span><strong>{{'AWG ONLINE' if on else 'AWG OFFLINE'}}</strong><small>awg0 · {{port}} UDP<br>{{count}} клиентов · {{active}} онлайн</small></div></aside><main class=main><header class=topbar><div class=top-actions><button class="btn secondary mobile-menu" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button><span class=title>{{title}}</span></div><div class=top-actions><span class=tag><span class="statusdot {{'' if on else 'off'}}"></span>{{'Система OK' if on else 'Требует внимания'}}</span><a class="btn secondary" href=/logout>Выйти</a></div></header><div class=wrap>{{body|safe}}<div class=footer>NOVA Network Control Center · AmneziaWG 3.1 · v{{version}}</div></div></main></div>''',nav=nav(p),title=title,body=body,on=on,port=it.get('ListenPort','-'),count=len(cs),active=active,version=VERSION)

@app.before_request
def auth():
 if request.path not in ('/login','/background.svg') and not session.get('logged'):return redirect('/login')

@app.route('/background.svg')
def background():return send_file(BG,mimetype='image/svg+xml',max_age=0)

@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST' and request.form.get('login')==setting('login','admin') and request.form.get('password')==setting('password','change-me'):
  session['logged']=1; return redirect('/')
 return render_template_string(CSS+'''<div class="card login"><div class=brand><div class=logo>NX</div><div><b>NOVA <span>10</span></b><small>Network Control Center</small></div></div><div class=eyebrow>SECURE ADMIN ACCESS</div><h2>Вход в панель</h2><form method=post><label>Логин</label><input name=login autocomplete=username required><label>Пароль</label><input name=password type=password autocomplete=current-password required><button style="width:100%;margin-top:10px">Войти в NOVA</button></form></div>''')

@app.route('/logout')
def logout():session.clear();return redirect('/login')

@app.route('/')
def dashboard():
 it=cfg(); cs=client_stats(); active=[x for x in cs if x['online']]; rx=sum(x['rx'] for x in cs);tx=sum(x['tx'] for x in cs)
 body=render_template_string('''<div class=hero><div><div class=eyebrow>NOVA NETWORK CONTROL CENTER</div><h1>Контроль сервера</h1><p>Один экран для AWG, клиентов, сети и безопасности.</p></div><a class=btn href=/active>🟢 {{active|length}} активных клиентов</a></div><div class=grid4><div class="card metric"><div class=label>AWG 3.1</div><div class="value {{'ok' if on else 'bad'}}">{{'ONLINE' if on else 'OFFLINE'}}</div><div class=sub>интерфейс awg0</div></div><div class="card metric"><div class=label>Клиенты</div><div class=value>{{clients}}</div><div class=sub>{{active|length}} сейчас онлайн</div></div><div class="card metric"><div class=label>Трафик RX</div><div class=value>{{rx}}</div><div class=sub>получено через AWG</div></div><div class="card metric"><div class=label>Трафик TX</div><div class=value>{{tx}}</div><div class=sub>отправлено через AWG</div></div></div><div class=dashboard-grid><div class=card><div class=toolbar><h2>Быстрый доступ</h2><span class=muted>управление</span></div><div class=actions><a class=action href=/clients>👥<b>Управление клиентами</b><span>Создание, QR, конфигурации и удаление</span></a><a class=action href=/obfuscation>🛡<b>Strong Mobile</b><span>Профиль AmneziaWG 3.1</span></a><a class=action href=/network>🌐<b>Сеть и Firewall</b><span>NAT, DNS, forwarding и порт</span></a><a class=action href=/diagnostics>⚕<b>Диагностика</b><span>AWG, DNS, маршруты и система</span></a></div></div><div class=card><div class=toolbar><h2>Сервер</h2><span class="badge {{'on' if on else 'off'}}">{{'ONLINE' if on else 'OFFLINE'}}</span></div><div class=kv><div><span>Порт</span><b>{{port}} / UDP</b></div><div><span>MTU</span><b>{{mtu}}</b></div><div><span>IPv4</span><b>10.66.66.1/24</b></div><div><span>Обфускация</span><b class=ok>Strong 3.1</b></div></div></div></div><div class=card style="margin-top:14px"><div class=toolbar><h2>Активность клиентов</h2><a class="btn secondary mini" href=/active>Открыть список →</a></div><div class=table-wrap><table><tr><th>Клиент</th><th>IP</th><th>Последний handshake</th><th>RX / TX</th><th>Статус</th></tr>{% for x in active[:6] %}<tr><td><span class=client-name>{{x.name}}</span><span class=subline>{{x.endpoint}}</span></td><td>{{x.address}}</td><td>{{fmt(x.handshake)}}</td><td>{{bytes(x.rx)}} / {{bytes(x.tx)}}</td><td><span class="badge on">ONLINE</span></td></tr>{% else %}<tr><td colspan=5 class=muted>Сейчас активных подключений нет.</td></tr>{% endfor %}</table></div></div>''',on=online(),clients=len(cs),active=active,rx=fmt_bytes(rx),tx=fmt_bytes(tx),port=it.get('ListenPort','-'),mtu=it.get('MTU','-'),fmt=fmt_time,bytes=fmt_bytes)
 return layout('Дашборд',body,'/')

@app.route('/active')
def active_page():
 cs=client_stats(); body=render_template_string('''<div class=hero><div><div class=eyebrow>LIVE CLIENTS</div><h1>Активные клиенты</h1><p>Онлайн = handshake не старше 3 минут. Обновление каждые 10 секунд.</p></div><span class=tag>🟢 {{active}} онлайн / {{total}} всего</span></div><div class=card><div class=table-wrap><table><tr><th>Клиент</th><th>IP</th><th>Статус</th><th>Последний handshake</th><th>RX</th><th>TX</th><th>Endpoint</th></tr>{% for x in clients %}<tr><td><span class=client-name>{{x.name}}</span><span class=subline>{{x.public_key[:18]}}…</span></td><td>{{x.address}}</td><td><span class="badge {{'on' if x.online else 'off'}}">{{'ONLINE' if x.online else 'OFFLINE'}}</span></td><td>{{fmt(x.handshake)}}</td><td>{{bytes(x.rx)}}</td><td>{{bytes(x.tx)}}</td><td>{{x.endpoint}}</td></tr>{% endfor %}</table></div></div><script>setTimeout(()=>location.reload(),10000)</script>''',clients=cs,active=sum(x['online'] for x in cs),total=len(cs),fmt=fmt_time,bytes=fmt_bytes)
 return layout('Активные клиенты',body,'/active')

@app.route('/clients')
def clients_page():
 body=render_template_string('''<div class=hero><div><div class=eyebrow>CLIENT MANAGEMENT</div><h1>Клиенты</h1><p>Управление профилями AmneziaWG 3.1.</p></div><a class=btn href=#new>＋ Новый клиент</a></div><div class=card id=new><div class=toolbar><h2>Создать клиента</h2><span class=muted>ключи генерируются на сервере</span></div><form method=post action=/clients/create><div class=formgrid><div><label>Имя клиента</label><input name=name placeholder="iPhone · Android · Windows" required></div><div style="display:flex;align-items:end"><button style="width:100%">Создать и применить</button></div></div></form></div><div class=card style="margin-top:14px"><div class=toolbar><h2>Все клиенты</h2><span class=tag>{{rows|length}} профилей</span></div><div class=table-wrap><table><tr><th>ID</th><th>Клиент</th><th>Адрес</th><th>Создан</th><th>Действия</th></tr>{% for r in rows %}<tr><td>#{{r.id}}</td><td><span class=client-name>{{r.name}}</span><span class=subline>{{'активен'}}</span></td><td>{{r.address}}</td><td>{{created(r.created)}}</td><td><div class=actions-row><a class="btn mini" href=/clients/{{r.id}}/conf>CONF</a><a class="btn secondary mini" href=/clients/{{r.id}}/qr>QR</a><form method=post action=/clients/{{r.id}}/delete onsubmit="return confirm('Удалить клиента {{r.name}}?')"><button class="btn danger mini">Удалить</button></form></div></td></tr>{% else %}<tr><td colspan=5 class=muted>Клиентов пока нет.</td></tr>{% endfor %}</table></div></div>''',rows=rows(),created=lambda x:time.strftime('%d.%m.%Y',time.localtime(x or 0)))
 return layout('Клиенты',body,'/clients')

@app.route('/clients/create',methods=['POST'])
def create_client():
 name=request.form.get('name','').strip(); c=db()
 if not name:c.close();return 'Имя клиента обязательно',400
 if c.execute('SELECT 1 FROM clients WHERE name=?',(name,)).fetchone():c.close();return Response("<script>alert('Клиент с таким именем уже существует.');location='/clients'</script>",status=409)
 used={int(m.group(1)) for r in c.execute('SELECT address FROM clients') for m in [re.search(r'10\\.66\\.66\\.(\\d+)',r['address'] or '')] if m};addr=next((f'10.66.66.{n}/32' for n in range(2,255) if n not in used),None)
 if not addr:c.close();return 'Нет свободных адресов',500
 priv=cmd('awg','genkey').stdout.strip();pub=cmd('bash','-lc',f"printf '%s' '{priv}' | awg pubkey").stdout.strip();psk=cmd('awg','genpsk').stdout.strip()
 if not priv or not pub or not psk:c.close();return 'Не удалось сгенерировать ключи AWG',500
 c.execute('INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)',(name,addr,priv,pub,psk,int(time.time())));c.commit();c.close()
 old=CONF.read_text() if CONF.exists() else ''; bak=CONF.with_name(CONF.name+'.bak-client-'+time.strftime('%Y%m%d-%H%M%S'))
 if CONF.exists():bak.write_text(old)
 CONF.write_text(old.rstrip()+f'\n\n[Peer]\nPublicKey = {pub}\nPresharedKey = {psk}\nAllowedIPs = {addr}\n')
 r=cmd('systemctl','restart','awg-quick@awg0')
 if r.returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'AWG не принял клиента; конфиг восстановлен.',500
 return redirect('/clients')

@app.route('/clients/<int:cid>/delete',methods=['POST'])
def delete_client(cid):
 c=db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone();c.close()
 if not r:return 'Not found',404
 old=CONF.read_text() if CONF.exists() else '';bak=CONF.with_name(CONF.name+'.bak-delete-'+time.strftime('%Y%m%d-%H%M%S'))
 if CONF.exists():bak.write_text(old)
 if CONF.exists():
  parts=old.split('[Peer]'); head=parts[0]; kept=[x for x in parts[1:] if f"PublicKey = {r['public_key']}" not in x]
  CONF.write_text(head+''.join('[Peer]'+x for x in kept))
  if cmd('systemctl','restart','awg-quick@awg0').returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'Не удалось применить удаление.',500
 c=db();c.execute('DELETE FROM clients WHERE id=?',(cid,));c.commit();c.close();return redirect('/clients')

def server_public():return cmd('awg','show','awg0','public-key').stdout.strip()
def client_config(r):
 it=cfg();ep=setting('endpoint','') or (cmd('hostname','-I').stdout.split() or ['SERVER_IP'])[0]
 dns=setting('dns','10.66.66.1')
 L=['[Interface]',f"PrivateKey = {r['private_key']}",f"Address = {r['address']}",f'DNS = {dns}',f"MTU = {it.get('MTU','1280')}"]+[f'{k} = {it.get(k,v)}' for k,v in [('Jc','4'),('Jmin','40'),('Jmax','120'),('S1','16'),('S2','24'),('S3','16'),('S4','32'),('H1','1'),('H2','2'),('H3','3'),('H4','4')]]
 for k in ('HeaderProtectionKey','ContentPaddingAddition','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts','RandomTrailers','DisableCookies'):
  if it.get(k):L.append(f'{k} = {it[k]}')
 return '\n'.join(L+['','[Peer]',f'PublicKey = {server_public()}',f"PresharedKey = {r['psk']}",'AllowedIPs = 0.0.0.0/0',f'Endpoint = {ep}:{it.get("ListenPort","1234")}','PersistentKeepalive = 25'])+'\n'

@app.route('/clients/<int:cid>/conf')
def conf(cid):
 c=db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone();c.close()
 if not r:return 'Not found',404
 return Response(client_config(r),mimetype='text/plain',headers={'Content-Disposition':f'attachment; filename={r["name"]}.conf'})
@app.route('/clients/<int:cid>/qr')
def qr(cid):
 c=db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone();c.close()
 if not r:return 'Not found',404
 b=io.BytesIO();qrcode.make(client_config(r)).save(b,'PNG');b.seek(0);return send_file(b,mimetype='image/png')

@app.route('/config')
def config():
 t=CONF.read_text(errors='replace') if CONF.exists() else 'Конфигурация не найдена.'
 return layout('Конфигурация',render_template_string('''<div class=hero><div><div class=eyebrow>AWG CONFIG</div><h1>Конфигурация</h1><p>Текущий серверный профиль awg0.</p></div><div><a class=btn href=/config/download>↓ Скачать</a> <a class="btn secondary" href=/restart>↻ Перезапустить AWG</a></div></div><div class=card><pre class=code>{{t}}</pre></div>''',t=t),'/config')
@app.route('/config/download')
def config_download():return send_file(CONF,as_attachment=True,download_name='awg0.conf') if CONF.exists() else ('Not found',404)

@app.route('/obfuscation',methods=['GET','POST'])
def obfuscation():
 if request.method=='POST':
  if not CONF.exists():return 'Конфигурация AWG не найдена.',404
  old=CONF.read_text();bak=CONF.with_name(CONF.name+'.bak-strong-'+time.strftime('%Y%m%d-%H%M%S'));bak.write_text(old)
  vals={'ListenPort':'1234','MTU':'1280','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','ContentPaddingAddition':'0-64','RandomTrailers':'on','DisableCookies':'on','RekeyAfterTime':'120-180','RekeyTimeout':'3-8','RejectAfterTime':'150-210','KeepaliveTimeout':'8-15','MaxHandshakeAttempts':'8-15'}
  head,*rest=old.split('[Peer]',1);out=[x for x in head.splitlines() if not any(x.strip().startswith(k+' ') or x.strip().startswith(k+'=') for k in vals)];out += [f'{k} = {v}' for k,v in vals.items()];CONF.write_text('\n'.join(out).rstrip()+'\n'+(('[Peer]'+rest[0]) if rest else ''));r=cmd('systemctl','restart','awg-quick@awg0')
  if r.returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'Strong Mobile не применён; конфиг восстановлен.',500
  return redirect('/obfuscation')
 it=cfg(); vals={k:it.get(k,'-') for k in ('ListenPort','MTU','Jc','Jmin','Jmax','S1','S2','S3','S4','H1','H2','H3','H4','HeaderProtectionKey','ContentPaddingAddition','RandomTrailers','DisableCookies','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts')}
 return layout('Strong Mobile',render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1</div><h1>Strong Mobile</h1><p>Профиль обфускации NOVA для мобильных клиентов.</p></div><form method=post><button>🚀 Применить профиль</button></form></div><div class="notice good">Профиль: S1/S2/S3/S4 = 16 / 24 / 16 / 32 · MTU 1280 · UDP 1234.</div><div class=card><div class=kv>{% for k,v in vals.items() %}<div><span>{{k}}</span><b>{{v}}</b></div>{% endfor %}</div></div>''',vals=vals),'/obfuscation')

@app.route('/network')
def network():
 it=cfg(); iface=(cmd('ip','route','show','default').stdout.split() or ['-']*5)[4] if cmd('ip','route','show','default').returncode==0 else '-'; ipf=cmd('ip','-4','addr','show','dev',iface).stdout; public=cmd('curl','-4','-s','--max-time','3','https://api.ipify.org').stdout.strip() or 'не определён'
 rowsn=[('Интерфейс','awg0'),('WAN интерфейс',iface),('Публичный IPv4',public),('AWG адрес','10.66.66.1/24'),('ListenPort',it.get('ListenPort','-')+' UDP'),('MTU',it.get('MTU','-')),('IPv4 forwarding','ON' if 'net.ipv4.ip_forward = 1' in cmd('sysctl','net.ipv4.ip_forward').stdout else 'OFF'),('DNS','локальный / 10.66.66.1')]
 return layout('Сеть и Firewall',render_template_string('''<div class=hero><div><div class=eyebrow>NETWORK CENTER</div><h1>Сеть и Firewall</h1><p>NAT, forwarding, DNS и параметры выхода в интернет.</p></div></div><div class=card><div class=kv>{% for k,v in rows %}<div><span>{{k}}</span><b>{{v}}</b></div>{% endfor %}</div><div class=notice>Full Tunnel: <b>0.0.0.0/0</b> · IPv6 forwarding должен быть отключён для защиты от IPv6 leak.</div></div>''',rows=rowsn),'/network')

@app.route('/traffic')
def traffic():
 cs=client_stats(); return layout('Live Traffic',render_template_string('''<div class=hero><div><div class=eyebrow>REAL TIME</div><h1>Live Traffic</h1><p>Счётчики AWG по каждому клиенту.</p></div></div><div class=card><div class=table-wrap><table><tr><th>Клиент</th><th>Статус</th><th>RX</th><th>TX</th><th>Handshake</th></tr>{% for x in clients %}<tr><td><b>{{x.name}}</b><span class=subline>{{x.address}}</span></td><td><span class="badge {{'on' if x.online else 'off'}}">{{'ONLINE' if x.online else 'OFFLINE'}}</span></td><td>{{bytes(x.rx)}}</td><td>{{bytes(x.tx)}}</td><td>{{fmt(x.handshake)}}</td></tr>{% endfor %}</table></div></div><script>setTimeout(()=>location.reload(),5000)</script>''',clients=cs,bytes=fmt_bytes,fmt=fmt_time),'/traffic')

@app.route('/diagnostics')
def diagnostics():
 tests=[]
 for name,args in [('AWG service',['systemctl','is-active','--quiet','awg-quick@awg0']),('AWG interface',['ip','link','show','awg0']),('AWG dump',['awg','show','awg0','dump']),('IPv4 forwarding',['sysctl','net.ipv4.ip_forward'])]:
  r=cmd(*args); tests.append((name,r.returncode==0,(r.stdout+r.stderr).strip()[:600] or 'OK'))
 dns=cmd('getent','hosts','example.com');tests.append(('DNS resolution',dns.returncode==0,dns.stdout.strip() or dns.stderr.strip()))
 return layout('Диагностика',render_template_string('''<div class=hero><div><div class=eyebrow>SYSTEM HEALTH</div><h1>Диагностика</h1><p>Проверка ключевых компонентов NOVA и AWG.</p></div></div><div class=card>{% for n,ok,out in tests %}<div class=notice {{'good' if ok else 'badbox'}}><b>{{'✓' if ok else '✕'}} {{n}}</b><pre class=code style="max-height:130px;margin-top:8px">{{out}}</pre></div>{% endfor %}</div>''',tests=tests),'/diagnostics')

@app.route('/backups')
def backups():
 fs=sorted([p for p in CONF.parent.glob('awg0.conf.bak*')],key=lambda p:p.stat().st_mtime,reverse=True)[:40] if CONF.parent.exists() else []
 return layout('Резервные копии',render_template_string('''<div class=hero><div><div class=eyebrow>RECOVERY</div><h1>Резервные копии</h1><p>Безопасная точка восстановления конфигурации.</p></div><a class=btn href=/backups/create>💾 Создать backup</a></div><div class=card><div class=table-wrap><table><tr><th>Файл</th><th>Размер</th><th>Дата</th></tr>{% for p in fs %}<tr><td>{{p.name}}</td><td>{{bytes(p.stat().st_size)}}</td><td>{{date(p.stat().st_mtime)}}</td></tr>{% else %}<tr><td colspan=3 class=muted>Резервных копий пока нет.</td></tr>{% endfor %}</table></div></div>''',fs=fs,bytes=fmt_bytes,date=lambda x:time.strftime('%d.%m.%Y %H:%M:%S',time.localtime(x))),'/backups')
@app.route('/backups/create')
def backup_create():
 stamp=time.strftime('%Y%m%d-%H%M%S')
 if CONF.exists():shutil.copy2(CONF,CONF.with_name('awg0.conf.bak-'+stamp))
 if DB.exists():shutil.copy2(DB,DB.with_name('panel.db.bak-'+stamp))
 return redirect('/backups')

@app.route('/logs')
def logs():
 r=cmd('journalctl','-u','awg-quick@awg0','-n','180','--no-pager');return layout('Логи',render_template_string('''<div class=hero><div><div class=eyebrow>SYSTEM LOG</div><h1>Логи AWG</h1><p>Последние события сервиса.</p></div></div><div class=card><pre class=code>{{t}}</pre></div>''',t=r.stdout+r.stderr),'/logs')

@app.route('/settings',methods=['GET','POST'])
def settings():
 if request.method=='POST':
  c=db();c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('login',?)",(request.form.get('login','admin'),));c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('endpoint',?)",(request.form.get('endpoint',''),));c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('dns',?)",(request.form.get('dns','10.66.66.1'),));c.commit();c.close();return redirect('/settings')
 return layout('Настройки',render_template_string('''<div class=hero><div><div class=eyebrow>NOVA SETTINGS</div><h1>Настройки</h1><p>Endpoint и DNS для клиентских конфигураций.</p></div></div><div class=card><form method=post><div class=formgrid><div><label>Логин администратора</label><input name=login value="{{login}}"><label>Endpoint (IP или домен)</label><input name=endpoint value="{{endpoint}}" placeholder="freeyourmind.kvnrkn.qpon"></div><div><label>DNS для клиентов</label><input name=dns value="{{dns}}" placeholder="10.66.66.1"><div class=notice>После сохранения новые .conf будут использовать эти значения.</div></div></div><button>Сохранить настройки</button></form></div>''',login=setting('login','admin'),endpoint=setting('endpoint',''),dns=setting('dns','10.66.66.1')),'/settings')

@app.route('/about')
def about():
 return layout('О NOVA',render_template_string('''<div class=hero><div><div class=eyebrow>NOVA NETWORK CONTROL CENTER</div><h1>О панели</h1><p>Новая версия интерфейса и управления AmneziaWG 3.1.</p></div></div><div class=split><div class=card><h2>NOVA 10.0</h2><div class=kv><div><span>Panel</span><b>10.0</b></div><div><span>Protocol</span><b>AmneziaWG 3.1</b></div><div><span>Interface</span><b>awg0</b></div><div><span>Profile</span><b>Strong Mobile</b></div></div></div><div class=card><h2>Что изменилось</h2><p class=muted>Новый адаптивный интерфейс, отдельные активные клиенты, Live Traffic, диагностика, управление клиентами, удаление профилей, сетевой центр и улучшенная навигация.</p></div></div>'''),'/about')

@app.route('/restart')
def restart():cmd('systemctl','restart','awg-quick@awg0');return redirect('/')
@app.route('/api/metrics')
def metrics():
 cs=client_stats();return jsonify({'panel_version':VERSION,'awg_version':'3.1','awg_online':online(),'clients':len(cs),'online_clients':sum(x['online'] for x in cs),'rx':sum(x['rx'] for x in cs),'tx':sum(x['tx'] for x in cs),'port':cfg().get('ListenPort'),'mtu':cfg().get('MTU')})

if __name__=='__main__':app.run(host='0.0.0.0',port=8080)
