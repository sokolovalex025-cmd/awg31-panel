#!/usr/bin/env python3
"""AWG Panel system monitoring and diagnostics module."""
from flask import render_template_string, jsonify, redirect
import os, platform, shutil, subprocess, time

def _cmd(*args):
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=5)
    except Exception as e:
        return subprocess.CompletedProcess(args, 1, '', str(e))

def _bytes(path):
    try: return int(open(path).read().strip())
    except Exception: return 0

def _mem():
    total=free=0
    try:
        d={}
        for line in open('/proc/meminfo'):
            k,v=line.split(':',1); d[k]=int(v.strip().split()[0])*1024
        total=d.get('MemTotal',0); free=d.get('MemAvailable',d.get('MemFree',0))
    except Exception: pass
    return total, max(0,total-free)

def _cpu():
    try:
        vals=[]
        for line in open('/proc/stat'):
            if line.startswith('cpu '): vals=list(map(int,line.split()[1:])); break
        idle=vals[3]+(vals[4] if len(vals)>4 else 0); total=sum(vals)
        return round((1-idle/total)*100,1) if total else 0
    except Exception: return 0

def _net():
    rx=tx=0
    try:
        for line in open('/proc/net/dev'):
            if ':' not in line: continue
            name,data=line.split(':',1); name=name.strip()
            if name=='lo': continue
            p=data.split(); rx+=int(p[0]); tx+=int(p[8])
    except Exception: pass
    return rx,tx

def _services():
    out=[]
    for s in ('awg-quick@awg0','awgpanel','awgpanel-telegram','naiveproxy'):
        r=_cmd('systemctl','is-active',s)
        out.append((s,r.stdout.strip() or 'unknown'))
    return out

def register(app):
    original_nav=app.view_functions.get('_awgpanel_original_nav')
    if not original_nav:
        try:
            from app import nav as original
            app.view_functions['_awgpanel_original_nav']=original
        except Exception: original=None
    @app.route('/system')
    def system_page():
        total,used=_mem(); rx,tx=_net(); disk=shutil.disk_usage('/')
        body=render_template_string('''<div class="hero"><div><div class="eyebrow">SYSTEM</div><h1>Система</h1><p>Мониторинг VPS и сервисов в реальном времени.</p></div><div class="pill">{{host}}</div></div>
        <div class="grid"><div class="card"><div class="klabel">CPU</div><div class="kvalue">{{cpu}}%</div></div><div class="card"><div class="klabel">RAM</div><div class="kvalue">{{ram}}%</div><div class="muted">{{used}} / {{total}}</div></div><div class="card"><div class="klabel">DISK</div><div class="kvalue">{{disk}}%</div><div class="muted">{{du}} / {{dt}}</div></div><div class="card"><div class="klabel">UPTIME</div><div class="kvalue">{{uptime}}</div></div></div>
        <div class="two"><div class="card"><h2>Сервисы</h2><table>{% for n,s in services %}<tr><td>{{n}}</td><td class="{{'ok' if s=='active' else 'bad'}}">{{s}}</td></tr>{% endfor %}</table></div><div class="card"><h2>Сеть</h2><p>↓ Получено: <b>{{rx}}</b></p><p>↑ Передано: <b>{{tx}}</b></p><p class="muted">Интерфейсные счётчики Linux</p></div></div>
        <div class="card" style="margin-top:16px"><h2>Информация</h2><table><tr><td>OS</td><td>{{os}}</td></tr><tr><td>Kernel</td><td>{{kernel}}</td></tr><tr><td>Python</td><td>{{python}}</td></tr><tr><td>Архитектура</td><td>{{arch}}</td></tr></table></div>''',host=platform.node(),cpu=_cpu(),ram=round(used/total*100,1) if total else 0,used=_fmt(used),total=_fmt(total),disk=round(disk.used/disk.total*100,1),du=_fmt(disk.used),dt=_fmt(disk.total),uptime=_uptime(),services=_services(),rx=_fmt(rx),tx=_fmt(tx),os=platform.platform(),kernel=platform.release(),python=platform.python_version(),arch=platform.machine())
        return _layout(app,'Система',body,'/system')
    @app.route('/diagnostics')
    def diagnostics():
        checks=[]
        def add(name,ok,detail=''): checks.append((name,bool(ok),detail))
        add('AmneziaWG binary',_cmd('sh','-c','command -v awg').returncode==0)
        add('AWG service',_cmd('systemctl','is-active','--quiet','awg-quick@awg0').returncode==0)
        add('Panel service',_cmd('systemctl','is-active','--quiet','awgpanel').returncode==0)
        add('IP forwarding',_bytes('/proc/sys/net/ipv4/ip_forward')==1,str(_bytes('/proc/sys/net/ipv4/ip_forward')))
        add('DNS',_cmd('getent','hosts','example.com').returncode==0)
        add('NaïveProxy',_cmd('systemctl','is-active','--quiet','naiveproxy').returncode==0)
        ok=sum(1 for _,v,_ in checks if v)
        body=render_template_string('''<div class="hero"><div><div class="eyebrow">HEALTH CHECK</div><h1>Диагностика</h1><p>Проверка ключевых компонентов сервера.</p></div><div class="pill">{{ok}} / {{total}} OK</div></div><div class="card"><table>{% for n,v,d in checks %}<tr><td style="font-size:18px">{{'✓' if v else '✕'}}</td><td><b>{{n}}</b><div class="muted">{{d}}</div></td><td class="{{'ok' if v else 'bad'}}">{{'OK' if v else 'ПРОБЛЕМА'}}</td></tr>{% endfor %}</table></div>''',checks=checks,ok=ok,total=len(checks)); return _layout(app,'Диагностика',body,'/diagnostics')
    @app.route('/api/system')
    def api_system():
        total,used=_mem();rx,tx=_net();d=shutil.disk_usage('/')
        return jsonify(cpu=_cpu(),ram=round(used/total*100,1) if total else 0,disk=round(d.used/d.total*100,1),rx=rx,tx=tx,uptime=_uptime(),host=platform.node())
    return app

def _fmt(n):
    for u in ('B','KB','MB','GB','TB'):
        if n<1024: return f'{n:.1f} {u}'
        n/=1024
    return f'{n:.1f} PB'

def _uptime():
    try:
        s=float(open('/proc/uptime').read().split()[0]); d=int(s//86400); h=int(s%86400//3600); m=int(s%3600//60)
        return f'{d}д {h}ч {m}м'
    except Exception:return '-'

def _layout(app,title,body,p):
    from flask import render_template_string
    try:
        from app import nav, cfg, online, rows
        n=nav(p)
        if '/system' not in n: n += '<a class="'+('active' if p=='/system' else '')+'" href="/system">◉&nbsp;&nbsp;Система</a><a class="'+('active' if p=='/diagnostics' else '')+'" href="/diagnostics">✓&nbsp;&nbsp;Диагностика</a>'
        it=cfg()
        return render_template_string('''<style>body{background:#06101d;color:#edf5ff;font:15px Segoe UI,Arial;margin:0}.wrap{max-width:1400px;margin:auto;padding:30px}.card{background:#061426;border:1px solid #4bb1f033;border-radius:16px;padding:20px;margin-bottom:16px}.hero{display:flex;justify-content:space-between;align-items:end;margin-bottom:25px}.eyebrow{color:#aeb6ff;letter-spacing:.15em}.hero h1{font-size:42px;margin:7px 0}.hero p,.muted{color:#91a8bd}.pill{padding:9px 13px;border:1px solid #30beff40;border-radius:999px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.klabel{color:#8fa5ba;text-transform:uppercase;font-size:13px}.kvalue{font-size:30px;font-weight:850;margin-top:8px}.ok{color:#2ee59d}.bad{color:#ff7b72}.two{display:grid;grid-template-columns:1.35fr 1fr;gap:16px}table{width:100%;border-collapse:collapse}td{padding:12px 8px;border-bottom:1px solid #82aacd22}@media(max-width:800px){.grid,.two{grid-template-columns:1fr}.hero{display:block}.wrap{padding:15px}.hero h1{font-size:31px}}</style><div class="wrap"><div class="hero"><div><a href="/">← AWG Panel</a><h2>{{title}}</h2></div></div>{{body|safe}}</div>''',title=title,body=body)
    except Exception:
        return body
