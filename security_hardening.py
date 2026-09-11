#!/usr/bin/env python3
"""Security hardening and NOVA branding for the web control center."""
from collections import defaultdict, deque
from pathlib import Path
import sqlite3
import time
from flask import request, Response
BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'; WINDOW=600; MAX_FAILURES=8; _BUCKETS=defaultdict(deque)
NOVA_MARK='''<svg class="nova-mark" viewBox="0 0 64 64" aria-label="NOVA" role="img"><defs><linearGradient id="novaG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#20e0ff"/><stop offset="1" stop-color="#1455ff"/></linearGradient></defs><rect width="64" height="64" rx="16" fill="#06152b"/><path d="M18 45V19h7l14 18V19h7v26h-7L25 27v18z" fill="url(#novaG)"/></svg>'''
NOVA_CSS='''<style id="nova-branding">
.brand .logo{background:#06152b url('/nova-mark.svg') center/cover no-repeat!important;font-size:0!important}
.nova-mark{width:34px;height:34px;display:block;filter:drop-shadow(0 0 10px #18cfff66)}
.nova-brand-lockup{display:flex;align-items:center;gap:10px}.nova-brand-lockup b{font-size:17px;letter-spacing:.14em}.nova-brand-lockup small{display:block;color:#8ea5bf;font-size:9px;letter-spacing:.12em;margin-top:2px}.nova-badge{font-size:10px;letter-spacing:.16em;color:#1ed8ff}
.nova-login{min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(900px 520px at 50% 0%,rgba(35,177,255,.16),transparent 65%),radial-gradient(700px 420px at 100% 100%,rgba(96,75,255,.12),transparent 65%),#030914;position:relative;overflow:hidden;color:#eef7ff;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.nova-login:before{content:"";position:absolute;inset:0;opacity:.22;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.02) 1px,transparent 1px);background-size:36px 36px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.8),transparent)}
.nova-login-orb{position:absolute;width:420px;height:420px;border-radius:50%;border:1px solid rgba(72,191,255,.12);box-shadow:0 0 90px rgba(31,174,255,.08),inset 0 0 70px rgba(31,174,255,.04)}
.nova-login-card{position:relative;z-index:2;width:min(440px,100%);padding:32px;border:1px solid rgba(118,190,235,.17);border-radius:24px;background:linear-gradient(145deg,rgba(12,27,44,.94),rgba(5,14,25,.96));box-shadow:0 30px 90px rgba(0,0,0,.55),0 0 55px rgba(40,180,255,.07);backdrop-filter:blur(22px)}
.nova-login-logo{width:82px;height:82px;margin:0 auto 18px;padding:9px;border-radius:23px;background:linear-gradient(145deg,rgba(72,191,255,.20),rgba(20,62,145,.20));border:1px solid rgba(72,191,255,.28);box-shadow:0 0 38px rgba(36,188,255,.16)}.nova-login-logo img{width:100%;height:100%;display:block;border-radius:17px}
.nova-login-title{text-align:center;font-size:31px;font-weight:850;letter-spacing:-.045em;margin:0;background:linear-gradient(100deg,#fff,#bfeaff 62%,#a49aff);-webkit-background-clip:text;background-clip:text;color:transparent}.nova-login-sub{text-align:center;color:#8097ae;font-size:11px;letter-spacing:.20em;text-transform:uppercase;margin:8px 0 26px}.nova-login-label{display:block;color:#a9bacb;font-size:12px;font-weight:700;margin:14px 0 6px}.nova-login input{width:100%;padding:13px 14px;border-radius:11px;background:#061321!important;color:#f1f8ff!important;border:1px solid rgba(125,175,210,.20)!important;outline:none;font-size:14px}.nova-login input:focus{border-color:rgba(65,197,255,.58)!important;box-shadow:0 0 0 4px rgba(50,187,255,.09)}.nova-login button{width:100%;margin-top:18px;padding:13px;border-radius:11px;border:1px solid rgba(74,207,255,.35);background:linear-gradient(100deg,#087ec9,#2654e8)!important;color:#fff!important;font-size:14px;font-weight:800;letter-spacing:.02em;cursor:pointer;box-shadow:0 10px 28px rgba(21,125,225,.22)}.nova-login button:hover{filter:brightness(1.08);transform:translateY(-1px)}.nova-login-status{display:flex;justify-content:center;gap:8px;align-items:center;margin-top:22px;color:#718aa1;font-size:11px}.nova-login-status i{width:7px;height:7px;border-radius:50%;background:#43d39e;box-shadow:0 0 12px #43d39e;display:block}.nova-login-footer{text-align:center;color:#536a80;font-size:10px;letter-spacing:.08em;margin-top:24px}.nova-login-error{margin:0 0 12px;padding:10px 12px;border-radius:10px;background:rgba(255,76,105,.08);border:1px solid rgba(255,76,105,.18);color:#ff9eae;font-size:12px;text-align:center}
@media(max-width:520px){.nova-login{padding:16px}.nova-login-card{padding:25px 20px;border-radius:20px}.nova-login-logo{width:70px;height:70px}.nova-login-title{font-size:27px}}
</style>'''
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
   if request.path=='/login':
    html='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA Network Control Center</title>'''+NOVA_CSS+'''</head><body><main class="nova-login"><div class="nova-login-orb"></div><section class="nova-login-card"><div class="nova-login-logo"><img src="/nova-mark.svg" alt="NOVA"></div><h1 class="nova-login-title">NOVA</h1><div class="nova-login-sub">NETWORK CONTROL CENTER</div>'''+('''<div class="nova-login-error">Неверный логин или пароль</div>''' if request.method=='POST' else '')+'''<form method="post" autocomplete="on"><label class="nova-login-label" for="login">Логин</label><input id="login" name="login" autocomplete="username" autofocus required><label class="nova-login-label" for="password">Пароль</label><input id="password" name="password" type="password" autocomplete="current-password" required><button type="submit">Войти в NOVA</button></form><div class="nova-login-status"><i></i><span>Network Control Center · Secure Session</span></div><div class="nova-login-footer">AmneziaWG 3.1 · Strong Mobile</div></section></main></body></html>'''
   else:
    for old in ('AWG Panel 9.3','AWG Panel 9.2','AWG Panel 9.0','AWG Panel 8.1'):html=html.replace(old,'NOVA Network Control Center')
    html=html.replace('AWG Panel','NOVA'); html=html.replace('</head>',NOVA_CSS+'</head>',1)
   response.set_data(html)
  except Exception:pass
  return response
 @app.route('/nova-mark.svg')
 def nova_mark():return Response(NOVA_MARK,mimetype='image/svg+xml',headers={'Cache-Control':'public, max-age=86400'})
 app._security_hardening_93=True
