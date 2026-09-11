#!/usr/bin/env python3
"""Security hardening and NOVA branding for the web control center."""
from collections import defaultdict, deque
from pathlib import Path
import sqlite3, time, re
from flask import request, Response
BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'; WINDOW=600; MAX_FAILURES=8; _BUCKETS=defaultdict(deque)
NOVA_MARK='''<svg class="nova-mark" viewBox="0 0 64 64" aria-label="NOVA" role="img"><defs><linearGradient id="novaG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#20e0ff"/><stop offset="1" stop-color="#1455ff"/></linearGradient></defs><rect width="64" height="64" rx="16" fill="#06152b"/><path d="M18 45V19h7l14 18V19h7v26h-7L25 27v18z" fill="url(#novaG)"/></svg>'''
NOVA_CSS='''<style id="nova-branding">.brand .logo{background:#06152b url('/nova-mark.svg') center/cover no-repeat!important;font-size:0!important}.nova-brand-lockup{display:flex;align-items:center;gap:10px}.nova-brand-lockup b{font-size:17px;letter-spacing:.14em}.nova-brand-lockup small{display:block;color:#8ea5bf;font-size:9px;letter-spacing:.12em;margin-top:2px}.nova-badge{font-size:10px;letter-spacing:.16em;color:#20dfff}@media(max-width:760px){.nova-brand-lockup{gap:8px}.nova-brand-lockup b{font-size:15px}}</style>'''
def _db():
 c=sqlite3.connect(DB); c.execute('''CREATE TABLE IF NOT EXISTS security_audit (id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER NOT NULL,ip TEXT NOT NULL,event TEXT NOT NULL,detail TEXT DEFAULT '')'''); c.commit(); return c
def _audit(ip,event,detail=''):
 try:
  c=_db(); c.execute('INSERT INTO security_audit(ts,ip,event,detail) VALUES(?,?,?,?)',(int(time.time()),ip[:80],event[:80],detail[:500])); c.commit(); c.close()
 except Exception: pass
def _ip(req): return req.remote_addr or 'unknown'
def register(app):
 if getattr(app,'_security_hardening_93',False): return
 import app as core
 app.config.setdefault('SESSION_COOKIE_HTTPONLY',True); app.config.setdefault('SESSION_COOKIE_SAMESITE','Lax'); app.config.setdefault('SESSION_COOKIE_SECURE',False); app.config.setdefault('PERMANENT_SESSION_LIFETIME',3600)
 try:_db().close()
 except Exception:pass
 @app.before_request
 def _security_before():
  if request.path=='/login' and request.method=='POST':
   ip=_ip(request); now=time.time(); q=_BUCKETS[ip]
   while q and now-q[0]>WINDOW:q.popleft()
   if len(q)>=MAX_FAILURES:
    _audit(ip,'login_blocked','rate limit'); from flask import abort; abort(429,description='Слишком много попыток входа. Повторите позже.')
 @app.after_request
 def _security_headers(response):
  response.headers.setdefault('X-Content-Type-Options','nosniff'); response.headers.setdefault('X-Frame-Options','SAMEORIGIN'); response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin'); response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
  if request.path!='/login':response.headers.setdefault('Cache-Control','no-store')
  if request.is_secure:response.headers.setdefault('Strict-Transport-Security','max-age=31536000; includeSubDomains')
  return response
 original_login=app.view_functions.get('login')
 if original_login:
  def secure_login(*args,**kwargs):
   from flask import session
   ip=_ip(request)
   if request.method=='POST':
    now=time.time(); q=_BUCKETS[ip]
    while q and now-q[0]>WINDOW:q.popleft()
    result=original_login(*args,**kwargs)
    if session.get('logged'):q.clear(); _audit(ip,'login_success')
    else:q.append(now); _audit(ip,'login_failed')
    return result
   return original_login(*args,**kwargs)
  app.view_functions['login']=secure_login
 original_logout=app.view_functions.get('logout')
 if original_logout:
  def secure_logout(*args,**kwargs):_audit(_ip(request),'logout'); return original_logout(*args,**kwargs)
  app.view_functions['logout']=secure_logout
 @app.route('/api/security/status')
 def security_status():
  from flask import jsonify
  c=_db(); rows=c.execute('SELECT event,COUNT(*) FROM security_audit GROUP BY event').fetchall(); c.close(); counts={r[0]:r[1] for r in rows}
  return jsonify(ok=True,login_throttle=True,max_failures=MAX_FAILURES,window_seconds=WINDOW,audit=True,counts=counts)
 @app.route('/security/audit')
 def security_audit():
  from flask import render_template_string
  c=_db(); rows=c.execute('SELECT ts,ip,event,detail FROM security_audit ORDER BY id DESC LIMIT 100').fetchall(); c.close()
  body=render_template_string('''<div class=hero><div><div class=eyebrow>SECURITY AUDIT</div><h1>Журнал безопасности</h1><p>Последние события авторизации панели.</p></div></div><div class=card><table><tr><th>Время</th><th>IP</th><th>Событие</th><th>Детали</th></tr>{% for r in rows %}<tr><td>{{r[0]|int}}</td><td>{{r[1]}}</td><td>{{r[2]}}</td><td class=muted>{{r[3]}}</td></tr>{% else %}<tr><td colspan=4 class=muted>Событий пока нет</td></tr>{% endfor %}</table></div>''',rows=rows)
  return core.layout('Security Audit',body,'/security/audit')
 @app.after_request
 def _nova_branding(response):
  if 'text/html' not in response.headers.get('Content-Type',''):return response
  try:
   html=response.get_data(as_text=True)
   for old in ('AWG Panel 9.3','AWG Panel 9.2','AWG Panel 9.0','AWG Panel 8.1'):html=html.replace(old,'NOVA Network Control Center')
   html=html.replace('AWG Panel','NOVA')
   brand=re.compile(r'<div class=brand><div class=logo>.*?</div><div><h2>.*?</h2><small>.*?</small></div></div>',re.S)
   nova_brand='<div class="brand"><div class="logo" aria-label="NOVA"></div><div><h2>NOVA <span>Network</span></h2><small>Network Control Center</small></div></div>'
   html=brand.sub(nova_brand,html)
   html=html.replace('<title>','<link rel="icon" href="/nova-mark.svg" type="image/svg+xml"><meta name="theme-color" content="#050b14"><title>',1)
   html=html.replace('</head>',NOVA_CSS+'</head>',1)
   response.set_data(html)
  except Exception:pass
  return response
 @app.route('/nova-mark.svg')
 def nova_mark():return Response(NOVA_MARK,mimetype='image/svg+xml',headers={'Cache-Control':'public, max-age=86400'})
 app._security_hardening_93=True
