#!/usr/bin/env python3
"""NOVA domain manager: Cloudflare Registrar + DNS + Nginx/Certbot helpers."""
from pathlib import Path
import json, os, re, subprocess, urllib.request, urllib.error
from flask import request, jsonify, render_template_string

BASE=Path('/opt/awg31-panel')
CF_ENV=Path('/etc/awg31-panel/cloudflare.env')
DOMAIN_RE=re.compile(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$', re.I)

def _load_env():
    out={}
    if CF_ENV.exists():
        for line in CF_ENV.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); out[k.strip()]=v.strip().strip('"').strip("'")
    return out

def _save_env(account, token):
    CF_ENV.parent.mkdir(parents=True, exist_ok=True)
    CF_ENV.write_text(f'CLOUDFLARE_ACCOUNT_ID={account}\nCLOUDFLARE_API_TOKEN={token}\n')
    os.chmod(CF_ENV,0o600)

def _cf(path, method='GET', body=None):
    env=_load_env(); account=env.get('CLOUDFLARE_ACCOUNT_ID'); token=env.get('CLOUDFLARE_API_TOKEN')
    if not account or not token: raise RuntimeError('Cloudflare не настроен: укажите Account ID и API Token.')
    url='https://api.cloudflare.com/client/v4'+path.replace('{account_id}',account)
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url,data=data,method=method,headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw=e.read().decode(errors='replace')
        try: detail=json.loads(raw)
        except Exception: detail={'errors':[{'message':raw}]}
        raise RuntimeError(json.dumps(detail,ensure_ascii=False))

def _public_ip():
    try:
        return subprocess.check_output(['bash','-lc',"ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i==\"src\"){print $(i+1); exit}}'"],text=True).strip()
    except Exception: return ''

def _zone(domain):
    r=_cf('/zones?name='+urllib.parse.quote(domain)+'&status=active')
    return (r.get('result') or [None])[0]

def _ensure_zone(domain):
    z=_zone(domain)
    if z: return z
    root='.'.join(domain.split('.')[-2:])
    r=_cf('/zones','POST',{'name':root,'account':{'id':_load_env()['CLOUDFLARE_ACCOUNT_ID']},'jump_start':False})
    if not r.get('success'): raise RuntimeError(json.dumps(r,ensure_ascii=False))
    return r['result']

def _ensure_dns(domain, ip):
    zone=_ensure_zone(domain); zid=zone['id']; name='panel.'+domain
    q=_cf(f'/zones/{zid}/dns_records?type=A&name={urllib.parse.quote(name)}')
    payload={'type':'A','name':name,'content':ip,'ttl':120,'proxied':False}
    records=q.get('result') or []
    if records:
        rid=records[0]['id']; return _cf(f'/zones/{zid}/dns_records/{rid}','PUT',payload)
    return _cf(f'/zones/{zid}/dns_records','POST',payload)

def _nginx_ssl(host):
    conf=f'''server {{\n    listen 80;\n    listen [::]:80;\n    server_name {host};\n    location / {{\n        proxy_pass http://127.0.0.1:8080;\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection "upgrade";\n    }}\n}}\n'''
    p=Path('/etc/nginx/sites-available/awg31-panel'); p.write_text(conf)
    Path('/etc/nginx/sites-enabled/awg31-panel').unlink(missing_ok=True); Path('/etc/nginx/sites-enabled/awg31-panel').symlink_to(p)
    subprocess.run(['nginx','-t'],check=True); subprocess.run(['systemctl','reload','nginx'],check=True)
    subprocess.run(['certbot','certonly','--nginx','--non-interactive','--agree-tos','--register-unsafely-without-email','-d',host],check=True)
    sslconf=f'''server {{\n    listen 80; listen [::]:80; server_name {host};\n    return 301 https://$host$request_uri;\n}}\nserver {{\n    listen 443 ssl; listen [::]:443 ssl; server_name {host};\n    ssl_certificate /etc/letsencrypt/live/{host}/fullchain.pem;\n    ssl_certificate_key /etc/letsencrypt/live/{host}/privkey.pem;\n    client_max_body_size 20m; proxy_read_timeout 120s;\n    location / {{\n        proxy_pass http://127.0.0.1:8080; proxy_http_version 1.1;\n        proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";\n    }}\n}}\n'''
    p.write_text(sslconf); subprocess.run(['nginx','-t'],check=True); subprocess.run(['systemctl','reload','nginx'],check=True)

def apply(app):
    @app.get('/domains')
    def domains_page():
        env=_load_env()
        return render_template_string(PAGE,configured=bool(env.get('CLOUDFLARE_ACCOUNT_ID') and env.get('CLOUDFLARE_API_TOKEN')))

    @app.post('/api/domains/config')
    def domain_config():
        d=request.get_json(silent=True) or request.form
        account=(d.get('account_id') or '').strip(); token=(d.get('api_token') or '').strip()
        if not account or not token: return jsonify({'ok':False,'error':'Укажите Account ID и API Token'}),400
        _save_env(account,token); return jsonify({'ok':True})

    @app.post('/api/domains/check')
    def domain_check():
        domain=(request.get_json(silent=True) or {}).get('domain','').strip().lower()
        if not DOMAIN_RE.fullmatch(domain): return jsonify({'ok':False,'error':'Некорректное доменное имя'}),400
        r=_cf('/accounts/{account_id}/registrar/domain-check','POST',{'domains':[domain]})
        return jsonify(r)

    @app.post('/api/domains/register')
    def domain_register():
        d=request.get_json(silent=True) or {}; domain=(d.get('domain') or '').strip().lower()
        if not DOMAIN_RE.fullmatch(domain): return jsonify({'ok':False,'error':'Некорректное доменное имя'}),400
        if d.get('confirm') is not True: return jsonify({'ok':False,'error':'Нужно подтвердить регистрацию и оплату'}),400
        check=_cf('/accounts/{account_id}/registrar/domain-check','POST',{'domains':[domain]})
        result=(check.get('result') or {})
        item=result[0] if isinstance(result,list) and result else result.get(domain,{}) if isinstance(result,dict) else {}
        if item.get('registrable') is False or item.get('tier')=='premium': return jsonify({'ok':False,'error':'Домен недоступен или premium','check':check}),400
        reg=_cf('/accounts/{account_id}/registrar/registrations','POST',{'domain_name':domain,'auto_renew':True,'privacy_mode':'redaction'})
        host='panel.'+domain; ip=_public_ip(); dns=None
        try: dns=_ensure_dns(domain,ip) if ip else None
        except Exception as e: dns={'error':str(e)}
        try:
            subprocess.run(['apt-get','update'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            subprocess.run(['apt-get','install','-y','certbot','python3-certbot-nginx'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            _nginx_ssl(host)
        except Exception as e: return jsonify({'ok':True,'registration':reg,'dns':dns,'ssl_error':str(e),'url':'http://'+host})
        return jsonify({'ok':True,'registration':reg,'dns':dns,'url':'https://'+host})

    @app.get('/api/domains/status')
    def domain_status():
        env=_load_env(); return jsonify({'ok':True,'configured':bool(env.get('CLOUDFLARE_ACCOUNT_ID') and env.get('CLOUDFLARE_API_TOKEN'))})

PAGE='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA • Домены</title><style>body{margin:0;background:#080c13;color:#eaf0f8;font:16px system-ui}main{max-width:900px;margin:40px auto;padding:24px}.card{background:#111827;border:1px solid #263247;border-radius:18px;padding:24px;margin-bottom:18px}input,button{padding:13px 15px;border-radius:10px;border:1px solid #34435c;background:#0b1220;color:#fff}input{width:100%;box-sizing:border-box;margin:7px 0 12px}button{cursor:pointer;background:#2563eb;border:0}button.secondary{background:#263247}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.ok{color:#66e3a3}.warn{color:#ffd166}@media(max-width:700px){.row{grid-template-columns:1fr}}</style></head><body><main><h1>🌐 Домены NOVA</h1><p>Автоматическая регистрация через Cloudflare Registrar, DNS и HTTPS.</p><div class="card"><h2>1. Cloudflare</h2><p class="warn">API-токен хранится только на VPS с правами 600. Регистрация домена является платной операцией.</p><div class="row"><label>Account ID<input id="account"></label><label>API Token<input id="token" type="password"></label></div><button class="secondary" onclick="save()">Сохранить Cloudflare</button><span id="cfg"></span></div><div class="card"><h2>2. Регистрация</h2><input id="domain" placeholder="например: my-nova.com"><button onclick="check()">Проверить доступность и цену</button><div id="result"></div><button id="buy" style="display:none;margin-top:12px" onclick="registerDomain()">Зарегистрировать и настроить HTTPS</button></div><script>let checked=false;async function save(){let r=await fetch('/api/domains/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_id:account.value,api_token:token.value})});cfg.innerHTML=r.ok?' <b class=ok>✓ сохранено</b>':' <b>Ошибка</b>'}async function check(){let d=domain.value.trim().toLowerCase();let r=await fetch('/api/domains/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:d})});let j=await r.json();result.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>';checked=r.ok;if(r.ok)buy.style.display='inline-block'}async function registerDomain(){if(!checked)return; if(!confirm('Регистрация домена платная. Продолжить?'))return;let r=await fetch('/api/domains/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({domain:domain.value.trim().toLowerCase(),confirm:true})});let j=await r.json();result.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>'}</script></main></body></html>'''
