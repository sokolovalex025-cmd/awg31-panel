#!/usr/bin/env python3
"""NOVA 12 command-center wrapper.

Keeps the existing AWG/client/backend routes but owns the presentation layer,
login page and navigation so the UI does not depend on brittle HTML replacement.
"""
import os
import time
import app as core
from flask import request, session, redirect, render_template_string

core.VERSION = '12.0'
core.BG_VERSION = 'NOVA12'

try:
    import balancer
except Exception:
    balancer = None
try:
    import balancer_provision
except Exception:
    balancer_provision = None
try:
    import keenetic
    keenetic.register(core)
except Exception:
    keenetic = None

NOVA_CSS = r'''<style>
:root{--bg:#070a10;--surface:#0d121b;--surface2:#111925;--surface3:#151e2b;--line:#202b3a;--text:#eef3f8;--muted:#8b98aa;--accent:#7b8cff;--cyan:#43d9c0;--danger:#ff7186;--warn:#f3c45e;--shadow:0 24px 70px rgba(0,0,0,.42)}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font:14px Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:var(--text);background:var(--bg)}
body:before{content:"";position:fixed;inset:0;z-index:-3;background:radial-gradient(650px 430px at 5% -5%,rgba(84,111,255,.20),transparent 65%),radial-gradient(620px 440px at 100% 100%,rgba(44,211,181,.12),transparent 65%),linear-gradient(180deg,#070a10f5,#070a10fb),url('/background.svg?v=NOVA12');background-size:auto,auto,auto,cover;background-position:center}
body:after{content:"";position:fixed;inset:0;z-index:-2;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);background-size:44px 44px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.7),transparent 85%)}
a{color:inherit}.app{min-height:100vh;display:flex}.sidebar{position:fixed;z-index:30;left:0;top:0;bottom:0;width:278px;padding:18px 14px;background:rgba(9,13,21,.84);border-right:1px solid rgba(255,255,255,.07);backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);box-shadow:18px 0 55px rgba(0,0,0,.20);overflow:auto}
.brand{display:flex;align-items:center;gap:12px;padding:7px 10px 22px}.logo{width:45px;height:45px;border-radius:14px;display:grid;place-items:center;background:linear-gradient(145deg,#8090ff,#42d8be);color:#071018;font-weight:950;letter-spacing:-2px;box-shadow:0 12px 35px rgba(87,112,255,.25)}.brand b{font-size:19px;letter-spacing:-.03em}.brand b span{color:#66e0c6}.brand small{display:block;margin-top:3px;color:#748197;font-size:9px;letter-spacing:.15em;text-transform:uppercase}
.nav{display:grid;gap:4px}.section{margin:18px 9px 7px;color:#56647a;font-size:9px;font-weight:850;letter-spacing:.17em;text-transform:uppercase}.nav a{display:flex;align-items:center;gap:11px;padding:10px 11px;border:1px solid transparent;border-radius:12px;text-decoration:none;color:#9ba8b9;font-weight:680;transition:.16s ease}.nav a:hover{background:rgba(255,255,255,.045);color:#fff;transform:translateX(2px)}.nav a.active{color:#fff;background:linear-gradient(90deg,rgba(105,125,255,.18),rgba(47,205,178,.06));border-color:rgba(112,139,255,.24);box-shadow:inset 3px 0 var(--accent)}.nav i{width:20px;text-align:center;font-style:normal;font-size:15px}.keenetic-nav{margin-top:10px!important;background:linear-gradient(135deg,rgba(72,119,164,.20),rgba(39,186,157,.10))!important;border-color:rgba(76,173,195,.25)!important;color:#c9f5ec!important}
.server{position:static!important;margin:18px 2px 0;padding:13px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);border-radius:14px}.statusdot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;background:var(--cyan);box-shadow:0 0 14px rgba(67,217,192,.65)}.off{background:var(--danger);box-shadow:0 0 14px rgba(255,113,134,.55)}.server strong{font-size:12px}.server small{display:block;color:#718095;margin-top:7px;line-height:1.55}
.main{width:calc(100% - 278px);margin-left:278px;padding:0 38px 55px}.topbar{height:70px;margin:0 -38px 28px;padding:0 38px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:20;background:rgba(7,10,16,.76);border-bottom:1px solid rgba(255,255,255,.065);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}.topbar .title{font-size:13px;font-weight:750;color:#b8c3d2}.top-actions{display:flex;gap:9px;align-items:center}.tag{padding:7px 10px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.035);border-radius:999px;color:#aeb9c8;font-size:11px}.wrap{max-width:1500px;margin:auto}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:25px;margin:8px 0 22px}.eyebrow{color:#8494ff;font-size:9px;font-weight:900;letter-spacing:.19em;text-transform:uppercase}.hero h1{font-size:38px;line-height:1.04;letter-spacing:-.055em;margin:7px 0}.hero p{margin:0;color:#8d9aab;font-size:14px}.card{background:linear-gradient(145deg,rgba(18,26,38,.88),rgba(10,15,23,.91));border:1px solid rgba(255,255,255,.075);border-radius:17px;padding:19px;box-shadow:var(--shadow);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.metric{min-height:128px;position:relative;overflow:hidden}.metric:after{content:"";position:absolute;width:100px;height:100px;right:-35px;top:-45px;border-radius:50%;background:rgba(123,140,255,.08);filter:blur(2px)}.metric .label{color:#718096;font-size:10px;font-weight:850;letter-spacing:.09em;text-transform:uppercase}.metric .value{font-size:30px;font-weight:900;letter-spacing:-.045em;margin-top:12px}.metric .sub{color:#69778b;font-size:11px;margin-top:5px}.ok{color:var(--cyan)}.bad{color:var(--danger)}.warn{color:var(--warn)}.blue{color:#8298ff}
.dashboard-grid{display:grid;grid-template-columns:1.45fr .75fr;gap:14px;margin-top:14px}.actions{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.action{display:block;padding:15px;border:1px solid rgba(255,255,255,.065);border-radius:13px;background:rgba(255,255,255,.025);text-decoration:none;transition:.16s ease}.action:hover{transform:translateY(-2px);border-color:rgba(120,145,255,.30);background:rgba(120,145,255,.055)}.action b{display:block;margin:7px 0 4px}.action span{font-size:11px;color:#77869a}
.btn,button{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;padding:10px 13px;background:linear-gradient(135deg,#7589ff,#536ee9);color:#fff;text-decoration:none;font-weight:780;cursor:pointer;box-shadow:0 9px 25px rgba(73,95,220,.20);transition:.15s ease}.btn:hover,button:hover{filter:brightness(1.08);transform:translateY(-1px)}.btn.secondary{background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08);box-shadow:none}.btn.danger{background:#3b1722;color:#ff9baa;border:1px solid #693145}.mini{padding:7px 9px;font-size:11px}
.toolbar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:13px}.toolbar h2{margin:0;font-size:16px}.search{max-width:300px}.search input{margin:0}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:650px}th,td{text-align:left;padding:12px 9px;border-bottom:1px solid rgba(255,255,255,.065)}th{color:#65748a;font-size:9px;text-transform:uppercase;letter-spacing:.1em}td{color:#d8e0e9}.client-name{font-weight:750}.subline{display:block;color:#69788c;font-size:10px;margin-top:3px}.badge{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:9px;font-weight:850;border:1px solid transparent}.badge.on{background:#0b2b25;color:#5de3bf;border-color:#18584b}.badge.off{background:#2b151d;color:#ff879a;border-color:#5c2939}.badge.warn{background:#30260f;color:#f4c760;border-color:#5c4817}.actions-row{white-space:nowrap;display:flex;gap:5px}
input,select,.input{width:100%;padding:11px 12px;background:#080d15;color:#fff;border:1px solid #263448;border-radius:10px;outline:none}input:focus,select:focus{border-color:#6d84ff;box-shadow:0 0 0 3px rgba(109,132,255,.12)}label{display:block;color:#a9b5c5;font-size:11px;font-weight:700;margin:12px 0 6px}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.notice{padding:12px;border-radius:11px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.075);color:#aab7c7;margin:12px 0}.notice.good{border-color:#1c5a4d;background:#0b241f}.notice.badbox{border-color:#62303d;background:#27131a}.kv{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.07);border-radius:11px;overflow:hidden}.kv div{padding:12px;background:#0d141e}.kv span{display:block;color:#738197;font-size:10px;margin-bottom:4px}.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}.code{background:#070c13;border:1px solid #182435;border-radius:10px;padding:14px;white-space:pre-wrap;overflow:auto;max-height:520px;font:12px Consolas,monospace;color:#b9c8d9}.footer{text-align:center;color:#4e5d71;font-size:10px;margin-top:35px}.muted{color:#7e8c9f}.mobile-menu{display:none}
.login-shell{min-height:100vh;display:grid;place-items:center;padding:24px}.login-card{width:min(430px,100%);padding:27px;background:rgba(13,19,29,.88);border:1px solid rgba(255,255,255,.08);border-radius:22px;box-shadow:0 30px 90px rgba(0,0,0,.5);backdrop-filter:blur(20px)}.login-card .brand{padding:0 0 22px}.login-card h1{font-size:24px;margin:4px 0 6px}.login-card p{color:#7f8da0;margin:0 0 18px;font-size:12px}
.nova-float{position:fixed;right:24px;bottom:24px;z-index:25;display:inline-flex;align-items:center;gap:8px;padding:11px 14px;border-radius:13px;background:linear-gradient(135deg,rgba(29,53,75,.95),rgba(16,53,48,.95));border:1px solid rgba(89,196,190,.35);box-shadow:0 15px 40px rgba(0,0,0,.35);text-decoration:none;color:#d5fff8;font-weight:800}.nova-float:hover{transform:translateY(-2px)}
@media(max-width:1050px){.grid4{grid-template-columns:repeat(2,1fr)}.dashboard-grid,.split{grid-template-columns:1fr}.sidebar{width:245px}.main{width:calc(100% - 245px);margin-left:245px;padding-left:25px;padding-right:25px}.topbar{margin-left:-25px;margin-right:-25px;padding-left:25px;padding-right:25px}}
@media(max-width:760px){.sidebar{width:278px;transform:translateX(-100%);transition:.2s}.sidebar.open{transform:none}.main{width:100%;margin:0;padding:0 15px 35px}.topbar{margin:0 -15px 18px;padding:0 15px;height:64px}.mobile-menu{display:inline-flex}.hero{align-items:flex-start;flex-direction:column}.hero h1{font-size:31px}.grid4{grid-template-columns:1fr 1fr}.formgrid,.actions{grid-template-columns:1fr}.server{display:none}.nova-float{right:14px;bottom:14px}.nova-float span{display:none}}
@media(max-width:460px){.grid4{grid-template-columns:1fr}.hero h1{font-size:28px}}
</style>'''

def nova_nav(path):
    groups=[
        ('ОБЗОР',[('⌂','Дашборд','/'),('◉','Активные клиенты','/active')]),
        ('УПРАВЛЕНИЕ',[('♣','Клиенты','/clients'),('◇','Конфигурация','/config'),('◈','Strong Mobile','/obfuscation'),('🛜','Настроить Keenetic','/keenetic')]),
        ('СИСТЕМА',[('⌘','Сеть и Firewall','/network'),('◌','Live Traffic','/traffic'),('✓','Диагностика','/diagnostics'),('▣','Резервные копии','/backups'),('☷','Логи','/logs')]),
        ('ПАНЕЛЬ',[('⚙','Настройки','/settings'),('ⓘ','О NOVA','/about')])]
    out=[]
    for title,items in groups:
        out.append(f'<div class="section">{title}</div>')
        for icon,name,url in items:
            active='active' if (path==url or (url=='/keenetic' and path.startswith('/keenetic'))) else ''
            extra=' keenetic-nav' if url=='/keenetic' else ''
            out.append(f'<a class="{active}{extra}" href="{url}"><i>{icon}</i>{name}</a>')
    return ''.join(out)

core.nav = nova_nav

ORIGINAL_LAYOUT = core.layout

def nova_layout(title, body, path):
    html=ORIGINAL_LAYOUT(title, body, path)
    html=html.replace('NOVA <span>10</span>','NOVA <span>12</span>')
    html=html.replace('NOVA Network Control Center · AmneziaWG 3.1 · v10.0','NOVA Network Control Center · AmneziaWG 3.1 · v12.0')
    html=html.replace("background.svg?v=NOVA'", "background.svg?v=NOVA12'")
    float_link='<a class="nova-float" href="/keenetic">🛜 <span>Keenetic</span></a>'
    if 'class="nova-float"' not in html:
        html=html.replace('</body>',float_link+'</body>')
    return html

core.layout = nova_layout

# Existing route functions imported from app.py resolve layout/nav from their globals.
for rule in list(core.app.url_map.iter_rules()):
    view=core.app.view_functions.get(rule.endpoint)
    if view is not None and getattr(view,'__module__',None)=='app':
        view.__globals__['layout']=nova_layout
        view.__globals__['nav']=nova_nav

# Dedicated login page: the original login route is retained, but its UI is replaced.
@core.app.route('/nova11-login', methods=['GET','POST'])
def nova11_login():
    if request.method=='POST' and request.form.get('login')==core.setting('login','admin') and request.form.get('password')==core.setting('password','change-me'):
        session['logged']=1
        return redirect('/')
    return render_template_string(NOVA_CSS+'''<div class="login-shell"><div class="login-card"><div class="brand"><div class="logo">NX</div><div><b>NOVA <span>12</span></b><small>NETWORK CONTROL CENTER</small></div></div><div class="eyebrow">SECURE ADMIN ACCESS</div><h1>Вход в NOVA</h1><p>Управление AmneziaWG 3.1 · AWG 3.1 · Keenetic</p><form method="post"><label>Логин</label><input name="login" autocomplete="username" required><label>Пароль</label><input name="password" type="password" autocomplete="current-password" required><button style="width:100%;margin-top:14px">Войти в панель</button></form></div></div>''')

# Make the canonical /login use the new page without changing authentication semantics.
core.app.view_functions['login']=nova11_login
