from flask import Flask,request,redirect,session,render_template_string,Response,send_file,jsonify
from pathlib import Path
import os,subprocess,sqlite3,secrets,base64,json,struct,zlib,re
app=Flask(__name__); app.secret_key=os.environ.get('AWG_PANEL_SECRET',secrets.token_hex(32))
BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'; CONF=Path('/etc/amnezia/amneziawg/awg0.conf'); CLIENT_DIR=Path('/etc/amnezia/amneziawg/clients'); WG='awg0'
CSS='''<style>*{box-sizing:border-box}html,body{margin:0;background:#020814;color:#eef6ff;font:15px Arial,sans-serif}body{background:#020814 url('/background.jpg') center/cover fixed no-repeat}body:before{content:"";position:fixed;inset:0;background:linear-gradient(90deg,rgba(2,8,20,.96),rgba(2,9,20,.62),rgba(2,8,19,.8));z-index:-1}.app{display:flex;min-height:100vh}.side{width:270px;padding:18px;background:rgba(3,14,32,.94);border-right:1px solid #1b5685}.brand{font-size:24px;font-weight:800;margin-bottom:25px}.brand span,.ok{color:#00e7a0}.nav a{display:block;padding:12px 14px;margin:5px 0;border-radius:9px;color:#bdd0e8;text-decoration:none}.nav a:hover{background:#145da055;color:white}.main{flex:1}.top{height:68px;padding:16px 28px;text-align:right;background:#02091499;border-bottom:1px solid #1b568544}.content{max-width:1200px;margin:auto;padding:28px}.card{background:linear-gradient(145deg,#061832e6,#040f20e8);border:1px solid #2870a866;border-radius:13px;padding:18px;margin:14px 0;box-shadow:0 15px 45px #0007}.hero h1{font-size:42px;margin:0 0 8px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric{padding:18px}.metric b{display:block;font-size:25px;margin-top:8px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}input,select{width:100%;padding:10px;margin:5px 0 12px;background:#030c17;color:white;border:1px solid #294157;border-radius:8px}button,.btn{display:inline-block;padding:10px 15px;border:0;border-radius:8px;background:linear-gradient(135deg,#08ad82,#1597ff);color:white;text-decoration:none;font-weight:700;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #5cb9ff22;text-align:left}.bad{color:#ff7788}pre{white-space:pre-wrap;overflow:auto;background:#02080fcc;padding:14px;border-radius:8px}@media(max-width:800px){.app{display:block}.side{width:100%;height:auto}.nav{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}.nav a{text-align:center;font-size:11px;padding:8px}.grid{grid-template-columns:1fr 1fr}.two{grid-template-columns:1fr}.content{padding:14px}.hero h1{font-size:30px}} </style>'''
def cmd(*a):
 try:
  p=subprocess.run(a,text=True,capture_output=True,timeout=15); return p.stdout.strip(),p.returncode
 except Exception as e:return str(e),1
def cfg():
 d={}
 if CONF.exists():
  for x in CONF.read_text(errors='ignore').splitlines():
   if '=' in x and not x.lstrip().startswith('#'):
    k,v=x.split('=',1); d[k.strip()]=v.strip()
 return d
def iface():return cmd('awg','show',WG)[1]==0 or cmd('ip','link','show',WG)[1]==0
def db():
 BASE.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB); c.execute('CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY,name TEXT UNIQUE,address TEXT,private TEXT,public TEXT)'); c.commit(); return c
def keys():
 priv,_=cmd('awg','genkey'); pub,_=cmd('bash','-lc',f"printf '%s' '{priv}' | awg pubkey"); return priv.strip(),pub.strip()
def sync():
 if not CONF.exists():return
 cmd('awg-quick','strip',WG)
 try:cmd('systemctl','restart',f'awg-quick@{WG}')
 except:pass
def conf_for(c):
 d=cfg(); host=cmd('curl','-4','-fsS','--max-time','5','https://api.ipify.org')[0] or 'SERVER_IP'; sp=d.get('PrivateKey',''); out='[Interface]\nPrivateKey = '+c[3]+'\nAddress = '+c[2]+'/32\nDNS = 1.1.1.1\nMTU = '+d.get('MTU','1380')+'\n\n[Peer]\nPublicKey = '+server_pub()+'\nAllowedIPs = 0.0.0.0/0, ::/0\nEndpoint = '+host+':'+d.get('ListenPort','1234')+'\nPersistentKeepalive = 25\n'; return out
def server_pub():
 p=cfg().get('PrivateKey','');
 if not p:return ''
 return cmd('bash','-lc',f"printf '%s' '{p}' | awg pubkey")[0]
def uri(c):
 d=cfg(); text=conf_for(c); o={'container':'amnezia-awg','awg':{'isThirdPartyConfig':True,'last_config':json.dumps({'config':text,'client_ip':c[2]+'/32','port':int(d.get('ListenPort','1234'))},separators=(',',':'))}}; raw=json.dumps({'containers':[o],'defaultContainer':'amnezia-awg','description':c[1]}).encode(); return 'vpn://'+base64.urlsafe_b64encode(struct.pack('>I',len(raw))+zlib.compress(raw)).decode().rstrip('=')
LAY=CSS+'''<div class=app><aside class=side><div class=brand>▲ AWG Panel <span>6.7.2</span></div><nav class=nav><a href="/">🏠 Главная</a><a href="/clients">👥 Клиенты</a><a href="/obfuscation">🚀 Обфускация 3.1</a><a href="/mobile">📱 Mobile</a><a href="/logs">📋 Логи</a><a href="/about">ℹ️ О панели</a></nav></aside><main class=main><div class=top>AmneziaWG 3.1 · awg0 · <span class=ok>● ONLINE</span></div><div class=content>{% block content %}{% endblock %}</div></main></div>'''
@app.route('/')
def home():
 d=cfg(); c=db(); n=c.execute('select count(*) from clients').fetchone()[0]; c.close(); return render_template_string(LAY.replace('{% block content %}{% endblock %}','<section class=hero><h1>Добро пожаловать!</h1><p>AWG Panel 6.7.2 — мобильная свобода без границ.</p></section><div class=grid><div class="card metric">AWG статус<b class="ok">'+('ONLINE' if iface() else 'OFFLINE')+'</b></div><div class="card metric">Клиенты<b>'+str(n)+'</b></div><div class="card metric">Порт<b>'+d.get('ListenPort','1234')+'</b></div><div class="card metric">MTU<b>'+d.get('MTU','1380')+'</b></div></div><div class=card><h2>Strong Mobile</h2><p>AWG 3.1 · Header Protection · H1-H4 · S1-S4 · Jc/Jmin/Jmax · MTU 1380 · UDP 1234.</p></div>')
@app.route('/clients',methods=['GET','POST'])
def clients():
 c=db()
 if request.method=='POST':
  name=request.form.get('name','client').strip(); exists=c.execute('select id from clients where name=?',(name,)).fetchone()
  if not exists:
   used={x[0] for x in c.execute('select address from clients')}; ip=2
   while f'10.66.66.{ip}' in used:ip+=1
   pr,pu=keys(); c.execute('insert into clients(name,address,private,public) values(?,?,?,?)',(name,f'10.66.66.{ip}',pr,pu)); c.commit()
 c2=c.execute('select * from clients order by id desc').fetchall(); c.close(); rows=''.join(f'<tr><td>{x[1]}</td><td>{x[2]}</td><td><a class=btn href="/clients/{x[0]}/conf">CONF</a> <a class=btn href="/clients/{x[0]}/qr">QR</a> <a class=btn href="/clients/{x[0]}/vpnuri">vpn://</a> <a class=btn href="/clients/{x[0]}/delete">Удалить</a></td></tr>' for x in c2); return render_template_string(LAY.replace('{% block content %}{% endblock %}',f'<div class=card><h2>Создать клиента</h2><form method=post><input name=name placeholder="phone-1" required><button>Создать</button></form></div><div class=card><h2>Клиенты</h2><table><tr><th>Имя</th><th>IP</th><th>Действия</th></tr>{rows}</table></div>'))
@app.route('/clients/<int:i>/conf')
def getconf(i):
 c=db().execute('select * from clients where id=?',(i,)).fetchone();
 if not c:return 'Not found',404
 return Response(conf_for(c),mimetype='text/plain',headers={'Content-Disposition':f'attachment; filename="{c[1]}.conf"'})
@app.route('/clients/<int:i>/vpnuri')
def geturi(i):
 c=db().execute('select * from clients where id=?',(i,)).fetchone(); return Response(uri(c),mimetype='text/plain') if c else ('Not found',404)
@app.route('/clients/<int:i>/qr')
def qr(i):
 c=db().execute('select * from clients where id=?',(i,)).fetchone();
 if not c:return 'Not found',404
 p=subprocess.run(['qrencode','-t','PNG','-o','-'],input=uri(c).encode(),capture_output=True); return Response(p.stdout,mimetype='image/png')
@app.route('/clients/<int:i>/delete')
def delete(i):
 c=db();c.execute('delete from clients where id=?',(i,));c.commit();c.close();return redirect('/clients')
@app.route('/obfuscation',methods=['GET','POST'])
def obf():
 msg=''
 if request.method=='POST' and CONF.exists():
  old=CONF.read_text(); d=cfg(); d.update({'ListenPort':'1234','MTU':'1380','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','ContentPaddingAddition':'0-64','RandomTrailers':'on','DisableCookies':'on','RekeyAfterTime':'120-180','RekeyTimeout':'3-8','RejectAfterTime':'150-210','KeepaliveTimeout':'8-15','MaxHandshakeAttempts':'8-15'}); CONF.with_name('awg0.conf.bak').write_text(old); lines=['[Interface]']+[f'{k} = {v}' for k,v in d.items() if k not in ('PrivateKey','Address') and v]; lines.insert(1,'PrivateKey = '+d.get('PrivateKey','')); lines.insert(2,'Address = '+d.get('Address','10.66.66.1/24')); CONF.write_text('\n'.join(lines)+'\n'); sync(); msg='<div class="card ok">Strong Mobile профиль применён.</div>'
 return render_template_string(LAY.replace('{% block content %}{% endblock %}',f'<div class=card><h2>🚀 Strong Mobile</h2><p>AWG 3.1: Header Protection, H1-H4, S1-S4, padding, RandomTrailers, DisableCookies, Jc/Jmin/Jmax.</p>{msg}<form method=post><button>Применить Strong Mobile</button></form></div><div class=card><pre>'+json.dumps(cfg(),ensure_ascii=False,indent=2)+'</pre></div>'))
@app.route('/mobile')
def mobile():return render_template_string(LAY.replace('{% block content %}{% endblock %}','<div class=card><h2>📱 Mobile 4G/5G</h2><p>Рекомендуется MTU 1380, UDP 1234, PersistentKeepalive 25.</p></div>'))
@app.route('/logs')
def logs():return render_template_string(LAY.replace('{% block content %}{% endblock %}', '<div class=card><h2>Логи</h2><pre>'+cmd('journalctl','-u','awg-quick@awg0','-n','100','--no-pager')[0]+'</pre></div>'))
@app.route('/about')
def about():return render_template_string(LAY.replace('{% block content %}{% endblock %}','<div class=card><h1>О панели</h1><p>AWG Panel 6.7.2 Stable</p><table><tr><td>Платформа</td><td>AmneziaWG 3.1</td></tr><tr><td>Профиль</td><td>Strong Mobile</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr></table></div>'))
if __name__=='__main__':app.run('0.0.0.0',8080)
