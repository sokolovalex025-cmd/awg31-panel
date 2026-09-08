#!/usr/bin/env python3
import os,re,json,subprocess,shutil
from pathlib import Path
from flask import request,redirect,send_file,Response
BASE=Path('/opt/awg31-panel'); NP=Path('/etc/naiveproxy'); CFG=NP/'Caddyfile'; META=NP/'panel.json'; BIN=Path('/usr/local/bin/caddy-naive'); SERVICE='naiveproxy.service'
def run(*args,timeout=30):
 try:return subprocess.run(args,text=True,capture_output=True,timeout=timeout)
 except Exception as e:return subprocess.CompletedProcess(args,1,'',str(e))
def valid_domain(v):return bool(re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',v))
def valid_token(v):return bool(re.fullmatch(r'[A-Za-z0-9._-]{3,64}',v))
def status():return run('systemctl','is-active',SERVICE).stdout.strip()=='active'
def meta():
 try:return json.loads(META.read_text())
 except Exception:return {}
def install(domain,email,user,password,port):
 if not valid_domain(domain):return False,'Некорректный домен.'
 if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):return False,'Некорректный email.'
 if not valid_token(user):return False,'Некорректный логин.'
 if len(password)<8 or any(c.isspace() for c in password):return False,'Пароль должен содержать минимум 8 символов без пробелов.'
 try:port=int(port)
 except:return False,'Некорректный порт.'
 if not 1<=port<=65535:return False,'Некорректный порт.'
 NP.mkdir(parents=True,mode=0o750)
 run('apt-get','update',timeout=300); r=run('apt-get','install','-y','golang-go','git','curl','ca-certificates','libcap2-bin',timeout=600)
 if r.returncode:return False,'Не удалось установить зависимости: '+(r.stderr or r.stdout)[-1200:]
 r=run('bash','-lc','go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest',timeout=1200)
 if r.returncode:return False,'Не удалось установить xcaddy: '+(r.stderr or r.stdout)[-1200:]
 xcaddy=Path('/root/go/bin/xcaddy')
 if not xcaddy.exists():return False,'xcaddy не найден.'
 tmp=Path('/tmp/awg31-caddy-naive');shutil.rmtree(tmp,ignore_errors=True);tmp.mkdir()
 r=run(str(xcaddy),'build','--output',str(tmp/'caddy-naive'),'--with','github.com/caddyserver/forwardproxy@caddy2=github.com/klzgrad/forwardproxy@naive',timeout=1800)
 if r.returncode:return False,'Сборка Caddy/NaïveProxy завершилась ошибкой: '+(r.stderr or r.stdout)[-1800:]
 shutil.copy2(tmp/'caddy-naive',BIN);os.chmod(BIN,0o755);run('setcap','cap_net_bind_service=+ep',str(BIN))
 if run('getent','passwd','caddy').returncode:run('useradd','--system','--home','/var/lib/caddy','--shell','/usr/sbin/nologin','caddy')
 Path('/var/lib/caddy').mkdir(parents=True,exist_ok=True);run('chown','-R','caddy:caddy','/var/lib/caddy')
 web=Path('/var/www/naiveproxy');web.mkdir(parents=True,exist_ok=True);(web/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>AWG Panel</title><style>body{background:#06101d;color:#dcecff;font:18px sans-serif;display:grid;place-items:center;height:100vh}main{padding:40px;border:1px solid #24506e;border-radius:18px;background:#071a2b}</style><main><h1>AWG Panel</h1><p>Service is running.</p></main>')
 CFG.write_text(f'''{{\n    order forward_proxy before file_server\n    email {email}\n}}\n\n:{port}, {domain} {{\n    encode\n    forward_proxy {{\n        basic_auth {user} {password}\n        hide_ip\n        hide_via\n        probe_resistance\n    }}\n    file_server {{\n        root /var/www/naiveproxy\n    }}\n}}\n''');os.chmod(CFG,0o640)
 META.write_text(json.dumps({'domain':domain,'email':email,'user':user,'port':port},ensure_ascii=False,indent=2));os.chmod(META,0o600)
 sec=NP/'password';sec.write_text(password+'\n');os.chmod(sec,0o600)
 Path('/etc/systemd/system/'+SERVICE).write_text('''[Unit]\nDescription=NaiveProxy Caddy server for AWG Panel\nAfter=network-online.target\nWants=network-online.target\n[Service]\nUser=caddy\nGroup=caddy\nExecStart=/usr/local/bin/caddy-naive run --environ --config /etc/naiveproxy/Caddyfile\nExecReload=/usr/local/bin/caddy-naive reload --config /etc/naiveproxy/Caddyfile\nRestart=on-failure\nRestartSec=3\nLimitNOFILE=1048576\nAmbientCapabilities=CAP_NET_BIND_SERVICE\nNoNewPrivileges=true\n[Install]\nWantedBy=multi-user.target\n''')
 run('systemctl','daemon-reload');run('systemctl','enable',SERVICE);r=run('systemctl','restart',SERVICE)
 if r.returncode:return False,'Не удалось запустить NaïveProxy. Проверьте занятые TCP-порты 80/443 и логи.'
 return True,'NaïveProxy установлен и запущен.'
def register(app):
 mod=__import__('app')
 if hasattr(mod,'nav') and not getattr(mod.nav,'_naive_wrapped',False):
  original=mod.nav
  def nav2(p):
   s=original(p); link=f'<a class="{"active" if p=="/naiveproxy" else ""}" href="/naiveproxy">🚀&nbsp;&nbsp;NaïveProxy</a>'
   return s+link
  nav2._naive_wrapped=True;mod.nav=nav2
 @app.route('/naiveproxy/client.json')
 def naiveproxy_client_json():
  m=meta();pw=(NP/'password').read_text().strip() if (NP/'password').exists() else ''
  if not m or not pw:return Response('NaiveProxy is not configured',status=404)
  data={'listen':'socks://127.0.0.1:1080','proxy':f"https://{m.get('user')}:{pw}@{m.get('domain')}:{m.get('port',443)}"}
  return Response(json.dumps(data,ensure_ascii=False,indent=2)+'\n',mimetype='application/json',headers={'Content-Disposition':'attachment; filename=naive-config.json'})
 @app.route('/naiveproxy',methods=['GET','POST'])
 def naiveproxy_page():
  if request.method=='POST':
   a=request.form.get('action','')
   if a=='install':
    ok,msg=install(request.form.get('domain','').strip(),request.form.get('email','').strip(),request.form.get('user','').strip(),request.form.get('password',''),request.form.get('port','443'))
    return redirect('/naiveproxy?msg='+('ok:' if ok else 'err:')+msg.replace(' ','%20'))
   if a in ('start','stop','restart'):run('systemctl',a,SERVICE)
   elif a=='remove':run('systemctl','disable','--now',SERVICE);Path('/etc/systemd/system/'+SERVICE).unlink(missing_ok=True);run('systemctl','daemon-reload')
   return redirect('/naiveproxy')
  m=meta();msg=request.args.get('msg','');notice=(f'<div class="notice">{"✅" if msg.startswith("ok:") else "❌"} {msg[3:]}</div>' if msg else '')
  if m:
   d=m.get('domain','');u=m.get('user','');p=m.get('port',443);cfg={'listen':'socks://127.0.0.1:1080','proxy':f'https://{u}:PASSWORD@{d}:{p}'}
   content=notice+f'''<div class="grid"><div class="card"><div class="klabel">Домен</div><div class="kvalue" style="font-size:20px">{d}</div></div><div class="card"><div class="klabel">Порт</div><div class="kvalue">{p}</div></div><div class="card"><div class="klabel">Пользователь</div><div class="kvalue" style="font-size:20px">{u}</div></div><div class="card"><div class="klabel">Статус</div><div class="kvalue {'ok' if status() else 'bad'}">{'ONLINE' if status() else 'OFFLINE'}</div></div></div><div class="card" style="margin-top:16px"><h2>Управление</h2><form method=post><button name=action value=start>▶ Запустить</button> <button name=action value=restart>🔄 Перезапустить</button> <button class=btn alt name=action value=stop>⏹ Остановить</button> <button class=btn alt name=action value=remove onclick="return confirm('Удалить сервис NaïveProxy?')">🗑 Удалить сервис</button></form></div><div class="card" style="margin-top:16px"><h2>Конфигурация клиента</h2><pre>{json.dumps(cfg,ensure_ascii=False,indent=2)}</pre><p class=muted>URI: <code>naive+https://{u}:PASSWORD@{d}:{p}</code></p><a class=btn href=/naiveproxy/client.json>⬇ Скачать naive-config.json</a></div>'''
  else:
   content=notice+'''<div class="card"><h2>Установка NaïveProxy</h2><p class=muted>Сборка Caddy с NaïveProxy может занять несколько минут. Домен должен указывать на этот VPS.</p><form method=post><input type=hidden name=action value=install><label>Домен</label><input name=domain placeholder="proxy.example.com" required><label>Email для TLS</label><input name=email type=email placeholder="admin@example.com" required><label>Логин</label><input name=user value="naive" required><label>Пароль</label><input name=password type=password minlength=8 required><label>Порт</label><input name=port value="443" inputmode=numeric required><button>🚀 Установить NaïveProxy</button></form></div><div class="card" style="margin-top:16px"><h2>Перед установкой</h2><ul><li>DNS домена должен указывать на VPS.</li><li>TCP выбранного порта должен быть свободен.</li><li>Для ACME обычно нужен доступ к TCP/80 и TCP/443.</li><li>AWG UDP и NaïveProxy TCP могут работать параллельно.</li></ul></div>'''
  return mod.layout('NaïveProxy',content,'/naiveproxy')
