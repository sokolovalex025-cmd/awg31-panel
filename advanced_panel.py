#!/usr/bin/env python3
from flask import render_template_string, jsonify, send_file
from pathlib import Path
import sqlite3, subprocess, time, shutil, tarfile, os
BASE=Path('/opt/awg31-panel');DB=BASE/'panel.db';CONF=Path('/etc/amnezia/amneziawg/awg0.conf')
if not CONF.exists(): CONF=Path('/etc/wireguard/awg0.conf')
def c(*a):
 try:return subprocess.run(a,text=True,capture_output=True,timeout=8)
 except Exception:return subprocess.CompletedProcess(a,1,'','')
def h(n):
 for u in ('B','KB','MB','GB','TB'):
  if n<1024:return f'{n:.1f} {u}'
  n/=1024
 return f'{n:.1f} PB'
def ps():
 r=c('awg','show','awg0','dump');return [x.split('\t') for x in r.stdout.strip().splitlines()[1:] if len(x.split('\t'))>=8] if r.returncode==0 else []
def cs():
 try:
  x=sqlite3.connect(DB);x.row_factory=sqlite3.Row;r=x.execute('select name,address,public_key from clients order by id').fetchall();x.close();return r
 except Exception:return []
def traffic():
 m={p[1]:p for p in ps()};out=[]
 for x in cs():
  p=m.get(x['public_key']);rx=tx=0;hs='нет'
  if p:
   try: hs=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(int(p[5]))) if int(p[5]) else 'нет';rx=int(p[6]);tx=int(p[7])
   except Exception:pass
  out.append({'name':x['name'],'address':x['address'],'handshake':hs,'rx':h(rx),'tx':h(tx)})
 return out
def backup():
 b=BASE/'backups';b.mkdir(exist_ok=True);p=b/f'nova-{time.strftime("%Y%m%d-%H%M%S")}.tar.gz'
 with tarfile.open(p,'w:gz') as t:
  for x in (CONF,DB,Path('/etc/awg31-panel/telegram.env')):
   if x.exists():t.add(x,arcname=x.as_posix().lstrip('/'))
 os.chmod(p,0o600);return p
def register(app):
 @app.route('/dashboard-plus')
 def dashboard_plus():
  from app import cfg,online,layout
  it=cfg();d=shutil.disk_usage('/');total=avail=0
  try:
   for line in open('/proc/meminfo'):
    k,v=line.split(':',1);v=int(v.split()[0])*1024
    if k=='MemTotal':total=v
    elif k=='MemAvailable':avail=v
  except Exception:pass
  data=traffic();body=render_template_string('''<div class="hero"><div><div class="eyebrow">NOVA NETWORK CONTROL CENTER</div><h1>Dashboard Pro</h1><p>VPS, AWG и трафик клиентов.</p></div><div class="pill">{{'🟢 ONLINE' if awg else '🔴 OFFLINE'}}</div></div><div class="grid"><div class="card"><div class="klabel">AWG</div><div class="kvalue {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class="muted">awg0 · UDP {{port}}</div></div><div class="card"><div class="klabel">Клиенты</div><div class="kvalue">{{clients}}</div><div class="muted">peer: {{peers}}</div></div><div class="card"><div class="klabel">RAM</div><div class="kvalue">{{ram}}%</div></div><div class="card"><div class="klabel">DISK</div><div class="kvalue">{{disk}}%</div></div></div><div class="card"><h2>📡 Трафик клиентов</h2><table><tr><th>Клиент</th><th>Адрес</th><th>Handshake</th><th>RX</th><th>TX</th></tr>{% for x in data %}<tr><td><b>{{x.name}}</b></td><td>{{x.address}}</td><td>{{x.handshake}}</td><td>{{x.rx}}</td><td>{{x.tx}}</td></tr>{% else %}<tr><td colspan="5" class="muted">Клиентов нет</td></tr>{% endfor %}</table></div><div class="card"><h2>⚡ Быстрые действия</h2><a class="btn" href="/system">📊 Система</a> <a class="btn" href="/diagnostics">🩺 Диагностика</a> <a class="btn" href="/backup/download">💾 Backup</a></div>''',awg=online(),port=it.get('ListenPort','-'),clients=len(cs()),peers=len(ps()),ram=round((total-avail)/total*100,1) if total else 0,disk=round(d.used/d.total*100,1),data=data)
  return layout('NOVA Dashboard Pro',body,'/dashboard-plus')
 @app.route('/api/peers')
 def api_peers():return jsonify(traffic())
 @app.route('/backup/download')
 def backup_download():
  p=backup();return send_file(p,as_attachment=True,download_name=p.name)
 try:
  import app as main;old=main.nav
  if not getattr(main,'_advanced_nav_patched',False):
   def nav(p):return old(p)+f'<a class="{"active" if p=="/dashboard-plus" else ""}" href="/dashboard-plus">◈&nbsp;&nbsp;NOVA Dashboard Pro</a>'
   main.nav=nav;main._advanced_nav_patched=True
 except Exception:pass
 return app
