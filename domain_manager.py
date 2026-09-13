#!/usr/bin/env python3
"""NOVA existing-domain manager: DNS check + Nginx + Let's Encrypt.

No registrar/payment integration. The domain stays with the user's registrar (e.g. LLHOST).
"""
from pathlib import Path
import re, socket, subprocess
from flask import request, jsonify, render_template_string

PANEL_IP='95.85.241.45'
DOMAIN_RE=re.compile(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$', re.I)

def _dns(domain):
    out={}
    try:
        out['A']=sorted(set(socket.gethostbyname_ex(domain)[2]))
    except Exception: out['A']=[]
    try:
        import subprocess as sp
        txt=sp.check_output(['bash','-lc',f"command -v dig >/dev/null 2>&1 && dig +short AAAA {domain} || true"],text=True,timeout=8)
        out['AAAA']=[x.strip() for x in txt.splitlines() if x.strip()]
    except Exception: out['AAAA']=[]
    return out

def _nginx_config(host):
    p=Path('/etc/nginx/sites-available/awg31-panel')
    p.write_text(f'''server {{
    listen 80;
    listen [::]:80;
    server_name {host};
    client_max_body_size 20m;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
    location / {{
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
''')
    link=Path('/etc/nginx/sites-enabled/awg31-panel')
    link.unlink(missing_ok=True); link.symlink_to(p)
    subprocess.run(['nginx','-t'],check=True)
    subprocess.run(['systemctl','reload','nginx'],check=True)

def _https(host, email=''):
    subprocess.run(['apt-get','update'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    subprocess.run(['apt-get','install','-y','certbot','python3-certbot-nginx'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    cmd=['certbot','--nginx','-d',host,'--non-interactive','--agree-tos','--redirect']
    if email:
        cmd += ['-m',email]
    else:
        cmd += ['--register-unsafely-without-email']
    subprocess.run(cmd,check=True)

def apply(app):
    @app.get('/domains')
    def domains_page():
        return render_template_string(PAGE,panel_ip=PANEL_IP)

    @app.post('/api/domains/check')
    def domain_check():
        try:
            d=request.get_json(silent=True) or {}
            domain=(d.get('domain') or '').strip().lower().rstrip('.')
            if not DOMAIN_RE.fullmatch(domain):
                return jsonify({'ok':False,'error':'Некорректное доменное имя'}),400
            dns=_dns(domain)
            return jsonify({'ok':True,'domain':domain,'expected_ip':PANEL_IP,'dns':dns,
                            'points_to_panel':PANEL_IP in dns.get('A',[]),
                            'message':'DNS готов' if PANEL_IP in dns.get('A',[]) else 'Создайте A-запись на 95.85.241.45'})
        except Exception as e:
            return jsonify({'ok':False,'error':str(e)}),500

    @app.post('/api/domains/setup')
    def domain_setup():
        try:
            d=request.get_json(silent=True) or {}
            domain=(d.get('domain') or '').strip().lower().rstrip('.')
            email=(d.get('email') or '').strip()
            if not DOMAIN_RE.fullmatch(domain): return jsonify({'ok':False,'error':'Некорректное доменное имя'}),400
            dns=_dns(domain)
            if PANEL_IP not in dns.get('A',[]):
                return jsonify({'ok':False,'error':'DNS ещё не указывает на VPS','expected_ip':PANEL_IP,'dns':dns}),400
            _nginx_config(domain)
            try:
                _https(domain,email)
                return jsonify({'ok':True,'domain':domain,'url':'https://'+domain,'dns':dns,'https':True})
            except Exception as e:
                return jsonify({'ok':True,'domain':domain,'url':'http://'+domain,'dns':dns,'https':False,'ssl_error':str(e)})
        except Exception as e:
            return jsonify({'ok':False,'error':str(e)}),500

    @app.get('/api/domains/status')
    def domain_status():
        return jsonify({'ok':True,'panel_ip':PANEL_IP})

PAGE='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA • Домены</title><style>
body{margin:0;background:#080c13;color:#eaf0f8;font:16px system-ui}main{max-width:900px;margin:40px auto;padding:24px}.card{background:#111827;border:1px solid #263247;border-radius:18px;padding:24px;margin-bottom:18px}input,button{padding:13px 15px;border-radius:10px;border:1px solid #34435c;background:#0b1220;color:#fff;box-sizing:border-box}input{width:100%;margin:7px 0 12px}button{cursor:pointer;background:#2563eb;border:0;margin-right:8px}.ok{color:#66e3a3}.warn{color:#ffd166}.bad{color:#ff7b7b}pre{white-space:pre-wrap;overflow:auto;background:#0a101b;padding:14px;border-radius:10px}@media(max-width:700px){main{margin:10px auto;padding:14px}}
</style></head><body><main><h1>🌐 Домены NOVA</h1><p>Подключение уже зарегистрированного домена. Регистратор остаётся LLHOST или другой ваш регистратор.</p>
<div class="card"><h2>Подключить домен</h2><label>Домен<input id="domain" value="surpris.kvnrkn.qpon" placeholder="surpris.kvnrkn.qpon"></label><label>Email для Let's Encrypt<input id="email" type="email" placeholder="admin@example.com"></label><button onclick="check()">🔎 Проверить DNS</button><button id="setup" style="display:none" onclick="setup()">🔒 Настроить HTTPS</button><div id="result"></div></div>
<div class="card"><h3>DNS для LLHOST</h3><p>Создайте запись:</p><pre>A    surpris    95.85.241.45    TTL 10 минут</pre><p>После сохранения нажмите «Проверить DNS».</p></div></main><script>
let ready=false;async function check(){let r=await fetch('/api/domains/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:domain.value})});let j=await r.json();ready=j.points_to_panel===true;setup.style.display=ready?'inline-block':'none';result.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>'}async function setup(){if(!ready)return;let r=await fetch('/api/domains/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:domain.value,email:email.value})});let j=await r.json();result.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>'}
</script></body></html>'''
