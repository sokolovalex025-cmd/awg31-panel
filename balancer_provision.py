#!/usr/bin/env python3
from flask import request, redirect
from pathlib import Path
import subprocess, ipaddress, os, re, html
import balancer

RAW_BASE='https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main'

def _safe_host(host):
    if not host or len(host)>253:return False
    try: ipaddress.ip_address(host); return True
    except ValueError: return all(part and len(part)<=63 for part in host.split('.')) and all(ch.isalnum() or ch in '.-' for ch in host)

def _safe_user(user): return bool(re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',user or ''))

def _safe_key(path):
    p=Path(path).expanduser()
    try:p=p.resolve()
    except Exception:return False
    if not p.is_file() or not os.access(p,os.R_OK):return False
    return any(p==base or base in p.parents for base in (Path('/root/.ssh'),Path('/home')))

def _provision(user,host,port,key,token):
    target=f'{user}@{host}'
    remote=f"curl -fsSL {RAW_BASE}/provision-balancer-node.sh | bash -s -- {token}"
    args=['ssh','-p',str(port),'-i',str(Path(key).expanduser()),'-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','-o','StrictHostKeyChecking=accept-new',target,remote]
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=60)
        log=(p.stdout or '')[-3000:]
        if p.stderr:log+='\n'+p.stderr[-3000:]
        return p.returncode==0,log
    except Exception as e:return False,str(e)

def register(app):
    @app.route('/balancer/provision',methods=['GET','POST'])
    def balancer_provision():
        if request.method=='POST':
            name=request.form.get('name','').strip()[:64];host=request.form.get('host','').strip();user=request.form.get('user','root').strip();key=request.form.get('key_path','/root/.ssh/id_ed25519').strip()
            try:ssh_port=int(request.form.get('ssh_port','22'));api_port=int(request.form.get('api_port','9090'));weight=max(1,min(10000,int(request.form.get('weight','100'))))
            except ValueError:return 'Invalid parameters',400
            if not name or not _safe_host(host) or not _safe_user(user) or not _safe_key(key) or not 1<=ssh_port<=65535 or not 1<=api_port<=65535:return 'Invalid provisioning parameters',400
            c=balancer._db();exists=c.execute('SELECT id FROM balancer_nodes WHERE name=?',(name,)).fetchone();c.close()
            if exists:return 'Node name already exists',409
            token=balancer._ensure_token();ok,log=_provision(user,host,ssh_port,key,token)
            if not ok:return f'<h2>Не удалось подключить VPS</h2><pre>{html.escape(log)}</pre><p><a href="/balancer/provision">Назад</a></p>',502
            c=balancer._db();c.execute('INSERT INTO balancer_nodes(name,host,api_port,weight) VALUES(?,?,?,?)',(name,host,api_port,weight));c.commit();c.close();balancer._health(balancer._nodes()[-1]);return redirect('/balancer')
        body='''<div class="hero"><div><div class="eyebrow">NOVA / CLUSTER</div><h1>Подключить VPS</h1><p>NOVA установит Node Agent по SSH и автоматически добавит сервер в пул.</p></div></div><div class="card"><form method="post"><label>Название</label><input name="name" placeholder="NL-02" required><label>IP / hostname</label><input name="host" placeholder="203.0.113.10" required><div class="formgrid"><div><label>SSH пользователь</label><input name="user" value="root" required></div><div><label>SSH порт</label><input name="ssh_port" type="number" value="22" min="1" max="65535"></div></div><label>Приватный SSH-ключ на панели</label><input name="key_path" value="/root/.ssh/id_ed25519" required><div class="formgrid"><div><label>Health API порт</label><input name="api_port" type="number" value="9090" min="1" max="65535"></div><div><label>Вес</label><input name="weight" type="number" value="100" min="1" max="10000"></div></div><div class="notice">Приватный ключ остаётся на основной панели и не копируется на новый VPS.</div><button>Подключить и проверить</button> <a class="btn secondary" href="/balancer">Отмена</a></form></div>'''
        from app import layout
        return layout('Подключить VPS',body,'/balancer')

try:
    from app import app;register(app)
except (ImportError,RuntimeError):pass
