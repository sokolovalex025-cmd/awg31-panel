#!/usr/bin/env python3
"""NOVA MAX resilience and recovery layer.

Defensive reliability layer around the existing AWG service. It never edits
awg0 configuration, keys, or cryptographic parameters. It only observes,
creates backups, validates services and exposes operator diagnostics.
"""
import os, json, time, socket, subprocess, shutil, hashlib
from pathlib import Path
from flask import jsonify, request

BASE=Path('/opt/awg31-panel')
BACKUP=BASE/'backups'
BACKUP.mkdir(parents=True, exist_ok=True)
TARGETS=[('Cloudflare','1.1.1.1',443),('Google DNS','8.8.8.8',443),('GitHub','github.com',443),('Telegram','telegram.org',443)]
WATCH=['awg-quick@awg0.service','awgpanel.service','nginx.service']


def cmd(*args, timeout=8):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
        return p.returncode,(p.stdout+p.stderr).strip()[-4000:]
    except Exception as e: return 99,str(e)

def service_state(name):
    rc,out=cmd('systemctl','is-active',name,timeout=3)
    return 'active' if rc==0 and out=='active' else out or 'unknown'

def tcp(host,port,timeout=3):
    t=time.monotonic()
    try:
        s=socket.create_connection((host,port),timeout=timeout); s.close()
        return {'ok':True,'ms':round((time.monotonic()-t)*1000,1)}
    except Exception as e:
        return {'ok':False,'error':str(e),'ms':None}

def iface():
    rc,out=cmd('awg','show','awg0')
    if rc!=0: return {'ok':False,'error':out}
    return {'ok':True,'raw':out[-5000:]}

def status():
    endpoints=[]
    for name,host,port in TARGETS:
        dns=tcp(host,port)
        endpoints.append({'name':name,'host':host,'port':port,'tcp':dns})
    mtu=[]
    for size in (1000,1100,1200):
        rc,out=cmd('ping','-4','-M','do','-c','1','-W','2','-s',str(size),'1.1.1.1',timeout=4)
        mtu.append({'size':size,'ok':rc==0,'detail':out[-300:]})
    services={x:service_state(x) for x in WATCH}
    score=0
    score += 25 if iface().get('ok') else 0
    score += 25 if services.get('awgpanel.service')=='active' else 0
    score += 20 if services.get('nginx.service')=='active' else 0
    score += 15 if any(x['tcp'].get('ok') for x in endpoints) else 0
    score += 15 if all(x['ok'] for x in mtu) else 0
    return {'version':'NOVA MAX 12','timestamp':int(time.time()),'score':score,'services':services,'endpoints':endpoints,'mtu':mtu,'awg0':iface()}

def make_backup():
    ts=time.strftime('%Y%m%d-%H%M%S')
    root=BACKUP/f'nova-{ts}'
    root.mkdir(parents=True,exist_ok=True)
    files=['panel.db','app.py','nova11.py','panel_bootstrap.py','nova12_theme.py','nova13_theme.py','nova14_theme.py','antiblock.py','domain_manager.py','keenetic.py','balancer.py','nova_mobile_diagnostics.py','nova_shield.py','nova_resilience.py']
    copied=[]
    for f in files:
        src=BASE/f
        if src.exists(): shutil.copy2(src,root/f); copied.append(f)
    # Keep system configuration backup separate and read-only from this layer.
    for src,dst in [('/etc/awg31-panel/panel-secret','panel-secret'),('/etc/nginx/sites-available/awg31-panel','nginx-awg31-panel')]:
        p=Path(src)
        if p.exists(): shutil.copy2(p,root/dst); copied.append(str(dst))
    manifest={'created':ts,'files':copied,'note':'AWG interface/config is intentionally not copied into a restorable write path by the resilience API.'}
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    digest=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
    (root/'SHA256').write_text(digest+'  manifest.json\n')
    return {'ok':True,'path':str(root),'files':copied,'sha256':digest}

def apply(app):
    @app.get('/resilience')
    def resilience_page():
        s=status()
        rows=''.join(f"<tr><td>{x['name']}</td><td>{x['host']}:{x['port']}</td><td>{'ONLINE' if x['tcp']['ok'] else 'FAIL'}</td><td>{x['tcp'].get('ms','—')}</td></tr>" for x in s['endpoints'])
        services=''.join(f"<div class='card'><b>{k}</b><div class='muted'>{v}</div></div>" for k,v in s['services'].items())
        return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA MAX</title><style>body{{margin:0;background:#070a10;color:#eef3f8;font:14px system-ui;padding:28px}}.wrap{{max-width:1100px;margin:auto}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.card,table{{background:#111925;border:1px solid #253246;border-radius:14px;padding:16px}}table{{width:100%;margin-top:16px;border-collapse:separate;border-spacing:0}}td,th{{padding:11px;border-bottom:1px solid #253246;text-align:left}}.ok{{color:#5de3bf}}.bad{{color:#ff7186}}button{{padding:10px 14px;border:0;border-radius:9px;background:#657cff;color:#fff;font-weight:700}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><div class="wrap"><h1>NOVA MAX · Resilience</h1><p>Слой отказоустойчивости вокруг AWG. Основной awg0 не изменяется.</p><div class="grid"><div class="card"><b>Health Score</b><h2>{s['score']} / 100</h2></div>{services}<div class="card"><b>MTU probes</b><div>{' · '.join(str(x['size'])+('✓' if x['ok'] else '✗') for x in s['mtu'])}</div></div></div><table><tr><th>Endpoint</th><th>Address</th><th>Status</th><th>TCP ms</th></tr>{rows}</table><p style="margin-top:18px"><form method="post" action="/api/resilience/backup"><button>Создать резервную копию</button></form></p></div></body></html>'''

    @app.get('/api/resilience/status')
    def resilience_status(): return jsonify(status())

    @app.post('/api/resilience/backup')
    def resilience_backup(): return jsonify(make_backup())
