#!/usr/bin/env python3
from flask import Flask,request,redirect,session,render_template_string,send_file,jsonify,Response
from pathlib import Path
import sqlite3,subprocess,time,os,re,io,qrcode,sys
BASE=Path('/opt/awg31-panel');DB=BASE/'panel.db';CONF=Path('/etc/amnezia/amneziawg/awg0.conf')
if not CONF.exists(): CONF=Path('/etc/wireguard/awg0.conf')
BG=BASE/'background.svg';app=Flask(__name__);app.secret_key=os.getenv('AWGPANEL_SECRET','change-this-secret')
sys.modules.setdefault('app',sys.modules[__name__])
VERSION='8.1';BG_VERSION='82'
CSS='''<style>:root{--p:#061426dd;--b:#4bb1f033;--t:#edf5ff;--m:#91a8bd;--g:#2ee59d}*{box-sizing:border-box}html,body{margin:0;min-height:100%;font:15px Segoe UI,Arial;color:var(--t);background:#06101d url('/background.svg?v=82') center/cover fixed no-repeat}body:after{content:"";position:fixed;inset:0;background:linear-gradient(110deg,#020811f7,#030d1bd1,#020913eb);z-index:-1}a{color:inherit}.shell{min-height:100vh;display:grid;grid-template-columns:285px 1fr}.side{position:fixed;inset:0 auto 0 0;width:285px;padding:22px 18px;background:#030d1ceb;border-right:1px solid var(--b)}.brand{display:flex;gap:12px;align-items:center;margin:0 4px 28px}.logo{width:48px;height:48px;border-radius:14px;background:linear-gradient(145deg,#13b69a,#178ef5);display:grid;place-items:center;font-weight:900}.brand h2{margin:0;font-size:20px}.brand span{color:#17e6a0}.brand small,.muted{color:var(--m)}.menu{display:grid;gap:7px}.menu a{padding:14px;border-radius:10px;text-decoration:none;color:#bcd0e5;font-weight:650}.menu a:hover,.menu a.active{background:#187fe066;border:1px solid #2baaff47;color:#fff}.sidebox,.card{background:var(--p);border:1px solid var(--b);border-radius:16px;padding:20px}.sidebox{margin-top:24px;padding:15px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--g);box-shadow:0 0 12px #2ee59daa;margin-right:8px}.main{grid-column:2;padding:0 36px 40px}.top{height:78px;margin:0 -36px 25px;padding:0 36px;display:flex;align-items:center;justify-content:space-between;background:#030d1ed1;border-bottom:1px solid var(--b);position:sticky;top:0;z-index:4}.right{display:flex;gap:12px;align-items:center}.pill{padding:9px 13px;border:1px solid #30beff40;border-radius:999px;background:#09253b8c}.wrap{max-width:1400px;margin:auto}.hero{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:15px 0 25px}.eyebrow{color:#aeb6ff;letter-spacing:.15em;font-size:13px}.hero h1{font-size:42px;margin:7px 0}.hero p{font-size:18px;color:#b5c8dc;margin:0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.klabel{color:#8fa5ba;font-size:13px;text-transform:uppercase}.kvalue{font-size:30px;font-weight:850;margin-top:8px}.ok{color:var(--g)}.bad{color:#ff7b72}.actions{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.action{padding:18px;border-radius:13px;text-decoration:none;border:1px solid var(--b);min-height:112px}.action strong{display:block;font-size:18px;margin:8px 0}.two{display:grid;grid-template-columns:1.35fr 1fr;gap:16px;margin-top:16px}.btn,button{display:inline-block;border:0;border-radius:10px;padding:10px 14px;background:linear-gradient(135deg,#0cae92,#168ff2);color:#fff;text-decoration:none;font-weight:750;cursor:pointer}.btn.alt{background:#26394b}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:11px 8px;border-bottom:1px solid #82aacd22}th{color:#8fa5ba;font-size:12px;text-transform:uppercase}input{width:100%;padding:11px;background:#071522;color:#fff;border:1px solid #294257;border-radius:9px;margin:6px 0 12px}label{display:block;color:#c8d7e5;margin-top:7px}pre{background:#030b13;border-radius:10px;padding:14px;white-space:pre-wrap;overflow:auto}.notice{padding:13px;border-radius:10px;background:#1c5a852e;border:1px solid #34a8e83b;margin:12px 0}.footer{color:#72899f;font-size:12px;margin-top:28px;text-align:center}@media(max-width:1100px){.grid,.actions{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}@media(max-width:760px){.shell{display:block}.side{position:relative;width:100%;height:auto}.main{padding:0 15px 30px}.top{margin:0 -15px 18px;padding:0 15px}.grid,.actions{grid-template-columns:1fr}.hero h1{font-size:31px}}</style>'''
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def setting(k,d):
 c=db()
 for q in ('SELECT v FROM settings WHERE k=?','SELECT value FROM settings WHERE key=?'):
  try:
   r=c.execute(q,(k,)).fetchone()
   if r:c.close();return list(r)[0]
  except sqlite3.Error:pass
 c.close();return d
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
 c=db();r=c.execute('SELECT * FROM clients ORDER BY id').fetchall();c.close();return r
def nav(p):
 its=[('⌂','Главная','/'),('♣','Клиенты','/clients'),('▤','Конфигурация','/config'),('◇','Обфускация 3.1','/obfuscation'),('⌘','Сеть и порты','/network'),('▣','Резервные копии','/backups'),('☷','Логи','/logs'),('⚙','Настройки','/settings'),('ⓘ','О панели','/about')]
 return ''.join(f'<a class="{"active" if p==u else ""}" href="{u}">{i}&nbsp;&nbsp;{n}</a>' for i,n,u in its)
def layout(title,body,p):
 it=cfg();return render_template_string(CSS+'''<div class=shell><aside class=side><div class=brand><div class=logo>AW</div><div><h2>AWG Panel <span>{{version}}</span></h2><small>Mobile | AWG 3.1 Strong</small></div></div><nav class=menu>{{nav|safe}}</nav><div class=sidebox><span class=dot></span>Статус сервера<div style="font-size:18px;margin-top:9px">AWG: <b class="{{'ok' if on else 'bad'}}">{{'online' if on else 'offline'}}</b></div><div class=muted style="margin-top:8px">Интерфейс: awg0<br>Порт: {{port}} UDP<br>Клиентов: {{count}}</div></div></aside><main class=main><header class=top><div>{{title}}</div><div class=right><span class=pill><span class=dot></span>{{'Система: OK' if on else 'AWG offline'}}</span><a class=btn href=/logout>↪ Выйти</a></div></header><div class=wrap>{{body|safe}}<div class=footer>AWG Panel {{version}} | AmneziaWG 3.1 | FREE YOUR MIND</div></div></main></div>''',nav=nav(p),title=title,body=body,on=online(),port=it.get('ListenPort','-'),count=len(rows()),version=VERSION)
@app.before_request
def auth():
 if request.path not in ('/login','/background.svg') and not session.get('logged'):return redirect('/login')
@app.route('/background.svg')
def background():return send_file(BG,mimetype='image/svg+xml',max_age=0)
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST' and request.form.get('login')==setting('login','admin') and request.form.get('password')==setting('password','change-me'):session['logged']=1;return redirect('/')
 return render_template_string(CSS+'''<div class=wrap style="max-width:500px;margin:100px auto"><div class=card><div class=brand><div class=logo>AW</div><div><h2>AWG Panel <span>8.1</span></h2><small>Mobile | AWG 3.1 Strong</small></div></div><form method=post><label>Логин</label><input name=login autocomplete=username><label>Пароль</label><input name=password type=password autocomplete=current-password><button>Войти</button></form></div></div>''')
@app.route('/logout')
def logout():session.clear();return redirect('/login')
@app.route('/')
def dashboard():
 it=cfg();body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1</div><h1>Добро пожаловать!</h1><p>AWG Panel 8.1 — мобильная свобода без границ.</p><p style="margin-top:7px">Стабильный, быстрый и защищённый доступ в интернет.</p></div><div class=pill>UDP <b>{{port}}</b> · MTU <b>{{mtu}}</b></div></div><div class=grid><div class=card><div class=klabel>Статус AWG</div><div class="kvalue {{'ok' if on else 'bad'}}">{{'online' if on else 'offline'}}</div><div class=muted>awg0</div></div><div class=card><div class=klabel>Клиенты</div><div class=kvalue>{{count}}</div></div><div class=card><div class=klabel>Порт</div><div class=kvalue>{{port}}</div><div class=muted>UDP · MTU {{mtu}}</div></div><div class=card><div class=klabel>Обфускация</div><div class=kvalue>3.1 Strong</div><div class=muted>Header Protection {{'ON' if hpk else 'OFF'}}</div></div></div><div class=card style="margin-top:16px"><h2>⚡ Быстрые действия</h2><div class=actions><a class=action href=/obfuscation>🚀<strong>Strong Mobile</strong><span class=muted>Проверить профиль</span></a><a class=action href=/clients>♟<strong>Добавить клиента</strong><span class=muted>Создать конфигурацию</span></a><a class=action href=/config>⚙<strong>Конфигурация</strong><span class=muted>Параметры сервера</span></a><a class=action href=/backups>↓<strong>Резервная копия</strong><span class=muted>Сохранить конфигурацию</span></a></div></div><div class=two><div class=card><h2>Информация о сервере</h2><table><tr><td>AWG</td><td>{{'ONLINE' if on else 'OFFLINE'}}</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr><tr><td>MTU</td><td>{{mtu}}</td></tr><tr><td>S1-S4</td><td>16 / 24 / 16 / 32</td></tr><tr><td>RandomTrailers</td><td>ON</td></tr><tr><td>DisableCookies</td><td>ON</td></tr></table></div><div class=card><h2>FREE YOUR MIND</h2><p class=muted>Единый фон без задвоения интерфейса.</p><div class=notice>HeaderProtectionKey: {{'включён' if hpk else 'не найден'}}</div></div></div>''',on=online(),count=len(rows()),port=it.get('ListenPort','-'),mtu=it.get('MTU','-'),hpk=it.get('HeaderProtectionKey',''));return layout('Главная',body,'/')
@app.route('/clients')
def clients_page():
 body=render_template_string('''<div class=hero><div><div class=eyebrow>CLIENTS</div><h1>Клиенты</h1><p>AWG 3.1 конфигурации.</p></div></div><div class=card><h2>Новый клиент</h2><form method=post action=/clients/create><label>Имя</label><input name=name placeholder="Android-02" required><button>+ Создать клиента</button></form></div><div class=card style="margin-top:16px"><table><tr><th>ID</th><th>Имя</th><th>Адрес</th><th>Действия</th></tr>{% for r in rows %}<tr><td>{{r.id}}</td><td>{{r.name}}</td><td>{{r.address}}</td><td><a class=btn href="/clients/{{r.id}}/conf">CONF</a> <a class=btn href="/clients/{{r.id}}/qr">QR</a></td></tr>{% else %}<tr><td colspan=4 class=muted>Клиентов пока нет</td></tr>{% endfor %}</table></div>''',rows=rows());return layout('Клиенты',body,'/clients')
@app.route('/clients/create',methods=['POST'])
def create_client():
 name=request.form.get('name','').strip();c=db()
 if not name:c.close();return 'Имя клиента обязательно',400
 if c.execute('SELECT 1 FROM clients WHERE name=?',(name,)).fetchone():c.close();return Response("<script>alert('Клиент с таким именем уже существует.');location='/clients'</script>",status=409)
 used={int(m.group(1)) for r in c.execute('SELECT address FROM clients') for m in [re.search(r'10\.66\.66\.(\d+)',r['address'] or '')] if m};addr=next((f'10.66.66.{n}/32' for n in range(2,255) if n not in used),None)
 if not addr:c.close();return 'Нет свободных адресов',500
 priv=cmd('awg','genkey').stdout.strip();pub=cmd('bash','-lc',f"printf '%s' '{priv}' | awg pubkey").stdout.strip();psk=cmd('awg','genpsk').stdout.strip()
 if not priv or not pub or not psk:c.close();return 'Не удалось сгенерировать ключи AWG',500
 c.execute('INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)',(name,addr,priv,pub,psk,int(time.time())));c.commit();c.close()
 old=CONF.read_text() if CONF.exists() else '';bak=CONF.with_name(CONF.name+'.bak-client-'+time.strftime('%Y%m%d-%H%M%S'))
 if CONF.exists():bak.write_text(old)
 CONF.write_text(old.rstrip()+f'\n\n[Peer]\nPublicKey = {pub}\nPresharedKey = {psk}\nAllowedIPs = {addr}\n');r=cmd('systemctl','restart','awg-quick@awg0')
 if r.returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'AWG не принял клиента; конфиг восстановлен.',500
 return redirect('/clients')
def server_public():return cmd('awg','show','awg0','public-key').stdout.strip()
def client_config(r):
 it=cfg();ep=setting('endpoint','') or (cmd('hostname','-I').stdout.split() or ['SERVER_IP'])[0];L=['[Interface]',f"PrivateKey = {r['private_key']}",f"Address = {r['address']}",'DNS = 1.1.1.1',f"MTU = {it.get('MTU','1380')}"]+[f'{k} = {it.get(k,v)}' for k,v in [('Jc','4'),('Jmin','40'),('Jmax','120'),('S1','16'),('S2','24'),('S3','16'),('S4','32'),('H1','1'),('H2','2'),('H3','3'),('H4','4')]]
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
 t=CONF.read_text(errors='replace') if CONF.exists() else 'Конфигурация не найдена.';return layout('Конфигурация',render_template_string('''<div class=hero><div><div class=eyebrow>CONFIGURATION</div><h1>Конфигурация</h1></div></div><div class=card><a class=btn href=/config/download>Скачать awg0.conf</a> <a class="btn alt" href=/restart>Перезапустить AWG</a><pre>{{t}}</pre></div>''',t=t),'/config')
@app.route('/config/download')
def config_download():return send_file(CONF,as_attachment=True,download_name='awg0.conf') if CONF.exists() else ('Not found',404)
@app.route('/obfuscation',methods=['GET','POST'])
def obfuscation():
 if request.method=='POST':
  if not CONF.exists():return 'Конфигурация AWG не найдена.',404
  old=CONF.read_text();bak=CONF.with_name(CONF.name+'.bak-strong-'+time.strftime('%Y%m%d-%H%M%S'));bak.write_text(old)
  vals={'ListenPort':'1234','MTU':'1380','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','ContentPaddingAddition':'0-64','RandomTrailers':'on','DisableCookies':'on','RekeyAfterTime':'120-180','RekeyTimeout':'3-8','RejectAfterTime':'150-210','KeepaliveTimeout':'8-15','MaxHandshakeAttempts':'8-15'}
  head,*rest=old.split('[Peer]',1);out=[x for x in head.splitlines() if not any(x.strip().startswith(k+' ') or x.strip().startswith(k+'=') for k in vals)];out += [f'{k} = {v}' for k,v in vals.items()];CONF.write_text('\n'.join(out).rstrip()+'\n'+(('\n[Peer]'+rest[0]) if rest else ''));r=cmd('systemctl','restart','awg-quick@awg0')
  if r.returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'Strong Mobile не применён; конфиг восстановлен.',500
  return redirect('/')
 it=cfg();vals={k:it.get(k,'-') for k in ('ListenPort','MTU','Jc','Jmin','Jmax','S1','S2','S3','S4','H1','H2','H3','H4','HeaderProtectionKey','ContentPaddingAddition','RandomTrailers','DisableCookies','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts')};return layout('Обфускация 3.1',render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1</div><h1>Обфускация 3.1</h1><p>Strong Mobile.</p></div></div><div class=notice>S1–S4: 16 / 24 / 16 / 32.</div><div class=card><table>{% for k,v in vals.items() %}<tr><td>{{k}}</td><td>{{v}}</td></tr>{% endfor %}</table><form method=post style="margin-top:18px"><button>🚀 Применить Strong Mobile</button></form></div>''',vals=vals),'/obfuscation')
@app.route('/network')
def network():
 it=cfg();return layout('Сеть и порты',render_template_string('''<div class=hero><div><div class=eyebrow>NETWORK</div><h1>Сеть и порты</h1></div></div><div class=card><table>{% for k,v in rows %}<tr><td>{{k}}</td><td>{{v}}</td></tr>{% endfor %}</table></div>''',rows=[('Интерфейс','awg0'),('ListenPort',it.get('ListenPort','-')+' UDP'),('MTU',it.get('MTU','-')),('Адрес','10.66.66.1/24'),('Статус','ONLINE' if online() else 'OFFLINE')]),'/network')
@app.route('/backups')
def backups():
 fs=sorted([p.name for p in CONF.parent.glob('awg0.conf.bak*')],reverse=True)[:40] if CONF.parent.exists() else [];return layout('Резервные копии',render_template_string('''<div class=hero><div><div class=eyebrow>BACKUPS</div><h1>Резервные копии</h1></div></div><div class=card><a class=btn href=/backups/create>💾 Создать backup</a><table style="margin-top:15px"><tr><th>Файл</th><th>Размер</th></tr>{% for n in fs %}<tr><td>{{n}}</td><td>{{(base/n).stat().st_size}} bytes</td></tr>{% endfor %}</table></div>''',fs=fs,base=CONF.parent),'/backups')
@app.route('/backups/create')
def backup_create():
 import shutil
 if CONF.exists():shutil.copy2(CONF,CONF.with_name('awg0.conf.bak-'+time.strftime('%Y%m%d-%H%M%S')))
 if DB.exists():shutil.copy2(DB,DB.with_name('panel.db.bak-'+time.strftime('%Y%m%d-%H%M%S')))
 return redirect('/backups')
@app.route('/logs')
def logs():
 r=cmd('journalctl','-u','awg-quick@awg0','-n','150','--no-pager');return layout('Логи',render_template_string('''<div class=hero><div><div class=eyebrow>LOGS</div><h1>Логи</h1></div></div><div class=card><pre>{{t}}</pre></div>''',t=r.stdout+r.stderr),'/logs')
@app.route('/settings',methods=['GET','POST'])
def settings():
 if request.method=='POST':
  c=db();c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('login',?)",(request.form.get('login','admin'),));c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('endpoint',?)",(request.form.get('endpoint',''),));c.commit();c.close();return redirect('/settings')
 return layout('Настройки',render_template_string('''<div class=hero><div><div class=eyebrow>SETTINGS</div><h1>Настройки</h1></div></div><div class=card><form method=post><label>Логин</label><input name=login value="{{login}}"><label>Endpoint IP / домен</label><input name=endpoint value="{{endpoint}}"><button>Сохранить</button></form></div>''',login=setting('login','admin'),endpoint=setting('endpoint','')),'/settings')
@app.route('/about')
def about():
 it=cfg();return layout('О панели',render_template_string('''<div class=hero><div><div class=eyebrow>FREE YOUR MIND</div><h1>О панели</h1><p>AWG Panel 8.1 — AmneziaWG 3.1.</p></div></div><div class=two><div class=card><h2>AWG Panel 8.1</h2><table><tr><td>Версия панели</td><td>8.1</td></tr><tr><td>AmneziaWG</td><td>3.1</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr><tr><td>Статус</td><td>{{'ONLINE' if on else 'OFFLINE'}}</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr></table></div><div class=card><h2>FREE YOUR MIND</h2><p class=muted>Единый технологичный фон без задвоения интерфейса.</p><div class=notice>Background: SVG v82</div></div></div>''',on=online(),port=it.get('ListenPort','-')),'/about')
@app.route('/restart')
def restart():cmd('systemctl','restart','awg-quick@awg0');return redirect('/')
@app.route('/api/metrics')
def metrics():return jsonify({'panel_version':VERSION,'awg_version':'3.1','awg_online':online(),'clients':len(rows()),'port':cfg().get('ListenPort'),'mtu':cfg().get('MTU')})
if __name__=='__main__':app.run(host='0.0.0.0',port=8080)
