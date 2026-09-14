#!/usr/bin/env python3
"""NOVA MAX resilience, Doctor, recovery and health telemetry."""
import os, json, time, socket, subprocess, shutil, hashlib
from pathlib import Path
from flask import jsonify, request

BASE=Path('/opt/awg31-panel'); BACKUP=BASE/'backups'; BACKUP.mkdir(parents=True, exist_ok=True)
TARGETS=[('Cloudflare','1.1.1.1',443),('Google DNS','8.8.8.8',443),('GitHub','github.com',443),('Telegram','telegram.org',443)]
WATCH=['awg-quick@awg0.service','awgpanel.service','nginx.service','nginx.service']

def cmd(*args, timeout=8):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
        return p.returncode,(p.stdout+p.stderr).strip()[-4000:]
    except Exception as e:return 99,str(e)

def service_state(name):
    rc,out=cmd('systemctl','is-active',name,timeout=3); return 'active' if rc==0 and out=='active' else out or 'unknown'

def tcp(host,port,timeout=3):
    t=time.monotonic()
    try:
        s=socket.create_connection((host,port),timeout=timeout);s.close();return {'ok':True,'ms':round((time.monotonic()-t)*1000,1)}
    except Exception as e:return {'ok':False,'error':str(e),'ms':None}

def iface():
    rc,out=cmd('awg','show','awg0');return {'ok':rc==0,'raw':out[-5000:]}

def status():
    endpoints=[{'name':n,'host':h,'port':p,'tcp':tcp(h,p)} for n,h,p in TARGETS]
    mtu=[]
    for size in (1000,1100,1200):
        rc,out=cmd('ping','-4','-M','do','-c','1','-W','2','-s',str(size),'1.1.1.1',timeout=4);mtu.append({'size':size,'ok':rc==0,'detail':out[-300:]})
    services={x:service_state(x) for x in dict.fromkeys(WATCH)}
    score=(25 if iface()['ok'] else 0)+(25 if services.get('awgpanel.service')=='active' else 0)+(20 if services.get('nginx.service')=='active' else 0)+(15 if any(x['tcp']['ok'] for x in endpoints) else 0)+(15 if all(x['ok'] for x in mtu) else 0)
    return {'version':'NOVA MAX 12','timestamp':int(time.time()),'score':score,'services':services,'endpoints':endpoints,'mtu':mtu,'awg0':iface()}

def doctor():
    tests=[]
    def add(name,ok,detail,hint=''):tests.append({'name':name,'ok':bool(ok),'detail':detail or 'OK','hint':hint})
    add('AWG command',cmd('awg','show','awg0')[0]==0,'awg available and awg0 readable','Install/repair AmneziaWG 3.1.')
    add('AWG service',service_state('awg-quick@awg0.service')=='active',service_state('awg-quick@awg0.service'),'Restart awg-quick@awg0.')
    add('Panel service',service_state('awgpanel.service')=='active',service_state('awgpanel.service'),'Restart awgpanel.')
    add('Nginx',service_state('nginx.service')=='active',service_state('nginx.service'),'Check nginx -t and restart nginx.')
    rc,out=cmd('sysctl','-n','net.ipv4.ip_forward');add('IPv4 forwarding',rc==0 and out.strip()=='1',out,'Run nova-network-fix.sh.')
    rc,out=cmd('ip','-4','route','show','default');wan='';parts=out.split();wan=parts[parts.index('dev')+1] if 'dev' in parts else '';add('WAN route',bool(wan),wan or out,'Check default route.')
    if wan:
        add('NAT',cmd('iptables','-t','nat','-C','POSTROUTING','-s','10.66.66.0/24','-o',wan,'-j','MASQUERADE')[0]==0,'MASQUERADE present','Run nova-network-fix.sh.')
        add('AWG forwarding',cmd('iptables','-C','FORWARD','-i','awg0','-o',wan,'-s','10.66.66.0/24','-j','ACCEPT')[0]==0,'FORWARD rule present','Run nova-network-fix.sh.')
    conf=Path('/etc/amnezia/amneziawg/awg0.conf') if Path('/etc/amnezia/amneziawg/awg0.conf').exists() else Path('/etc/wireguard/awg0.conf')
    text=conf.read_text(errors='replace') if conf.exists() else ''
    add('HeaderProtectionKey',bool(next((x for x in text.splitlines() if x.strip().startswith('HeaderProtectionKey=')),None) or next((x for x in text.splitlines() if x.strip().startswith('HeaderProtectionKey =')),None)),'present' if text else 'config missing','Run nova_awg31_fix.py.')
    rc,out=cmd('getent','hosts','example.com');add('DNS',rc==0,out,'Check resolver/network.')
    return {'ok':all(x['ok'] for x in tests),'score':round(sum(x['ok'] for x in tests)*100/len(tests)) if tests else 0,'results':tests,'timestamp':int(time.time())}

def make_backup():
    ts=time.strftime('%Y%m%d-%H%M%S');root=BACKUP/f'nova-{ts}';root.mkdir(parents=True,exist_ok=True);files=[]
    for f in ['panel.db','app.py','nova11.py','panel_bootstrap.py','nova12_theme.py','nova13_theme.py','nova14_theme.py','antiblock.py','domain_manager.py','keenetic.py','balancer.py','balancer_provision.py','nova_mobile_diagnostics.py','nova_shield.py','nova_resilience.py']:
        src=BASE/f
        if src.exists():shutil.copy2(src,root/f);files.append(f)
    for src,dst in [('/etc/awg31-panel/panel-secret','panel-secret'),('/etc/nginx/sites-available/awg31-panel','nginx-awg31-panel')]:
        p=Path(src)
        if p.exists():shutil.copy2(p,root/dst);files.append(dst)
    manifest={'created':ts,'files':files,'note':'No private AWG key is exported by the API backup.'};(root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));digest=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest();(root/'SHA256').write_text(digest+'  manifest.json\n');return {'ok':True,'path':str(root),'files':files,'sha256':digest}

def auto_fix():
    steps=[]
    backup=make_backup();steps.append({'step':'backup','ok':backup['ok']})
    for label,args in [('network',['/opt/awg31-panel/nova-network-fix.sh']),('awg31',['/opt/awg31-panel/venv/bin/python','/opt/awg31-panel/nova_awg31_fix.py'])]:
        rc,out=cmd(*args,timeout=45);steps.append({'step':label,'ok':rc==0,'detail':out[-1000:]})
    for svc in ('awg31-network.service','awgpanel.service','nginx.service'):
        rc,out=cmd('systemctl','restart',svc,timeout=20);steps.append({'step':'restart '+svc,'ok':rc==0,'detail':out[-500:]})
    return {'ok':all(x['ok'] for x in steps),'steps':steps,'doctor':doctor()}

def apply(app):
    original_layout=getattr(app,'layout',None)
    @app.get('/doctor')
    def doctor_page():
        d=doctor();rows=''.join(f"<div class='notice {'good' if x['ok'] else 'badbox'}'><b>{'✓' if x['ok'] else '✕'} {x['name']}</b><div style='margin-top:5px'>{x['detail']}</div>{'' if x['ok'] else '<div class=muted>'+x['hint']+'</div>'}</div>" for x in d['results'])
        body=f'''<div class="hero"><div><div class="eyebrow">NOVA DOCTOR</div><h1>NOVA Doctor</h1><p>Полная проверка AWG 3.1, сети, firewall, DNS и сервисов.</p></div><button onclick="fixall()">🛠 Исправить всё</button></div><div class="card"><div class="notice {'good' if d['ok'] else 'badbox'}"><b>{'✓ Сервер здоров' if d['ok'] else '⚠ Требуется внимание'}</b><div class="muted">Health Score: {d['score']}%</div></div>{rows}<pre id="result" class="code" style="display:none"></pre></div><script>async function fixall(){{if(!confirm('Создать backup и применить безопасные исправления?'))return;let r=await fetch('/api/doctor/fix',{{method:'POST'}});document.getElementById('result').style.display='block';document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2);setTimeout(()=>location.reload(),1200)}}</script>'''
        return __import__('app').layout('NOVA Doctor',body,'/doctor')
    @app.get('/api/doctor')
    def doctor_api():return jsonify(doctor())
    @app.post('/api/doctor/fix')
    def doctor_fix():return jsonify(auto_fix())
    @app.get('/api/metrics/history')
    def metrics_history():
        return jsonify({'timestamp':int(time.time()),'current':status()})
    return True
