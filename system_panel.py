#!/usr/bin/env python3
"""AWG Panel VPS monitoring and health-check module."""
from flask import render_template_string, jsonify
import platform, shutil, subprocess

def _cmd(*args):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=5)
    except Exception as e:return subprocess.CompletedProcess(args,1,'',str(e))

def _mem():
    d={}
    try:
        for line in open('/proc/meminfo'):
            k,v=line.split(':',1);d[k]=int(v.strip().split()[0])*1024
    except Exception:pass
    total=d.get('MemTotal',0); used=max(0,total-d.get('MemAvailable',d.get('MemFree',0)));return total,used

def _cpu():
    try:
        for line in open('/proc/stat'):
            if line.startswith('cpu '):
                v=list(map(int,line.split()[1:]));idle=v[3]+(v[4] if len(v)>4 else 0);t=sum(v);return round((1-idle/t)*100,1) if t else 0
    except Exception:pass
    return 0

def _net():
    rx=tx=0
    try:
        for line in open('/proc/net/dev'):
            if ':' not in line:continue
            name,data=line.split(':',1)
            if name.strip()=='lo':continue
            p=data.split();rx+=int(p[0]);tx+=int(p[8])
    except Exception:pass
    return rx,tx

def _fmt(n):
    for u in ('B','KB','MB','GB','TB'):
        if n<1024:return f'{n:.1f} {u}'
        n/=1024
    return f'{n:.1f} PB'

def _uptime():
    try:
        s=float(open('/proc/uptime').read().split()[0]);return f'{int(s//86400)}д {int(s%86400//3600)}ч {int(s%3600//60)}м'
    except Exception:return '-'

def _services():
    return [(s,_cmd('systemctl','is-active',s).stdout.strip() or 'unknown') for s in ('awg-quick@awg0','awgpanel','awgpanel-telegram','naiveproxy')]

def register(app):
    @app.route('/system')
    def system_page():
        total,used=_mem();rx,tx=_net();du=shutil.disk_usage('/')
        body=render_template_string('''<div class="hero"><div><div class="eyebrow">SYSTEM</div><h1>Система</h1><p>Мониторинг VPS и сервисов.</p></div><div class="pill">{{host}}</div></div><div class="grid"><div class="card"><div class="klabel">CPU</div><div class="kvalue">{{cpu}}%</div></div><div class="card"><div class="klabel">RAM</div><div class="kvalue">{{ram}}%</div><div class="muted">{{used}} / {{total}}</div></div><div class="card"><div class="klabel">DISK</div><div class="kvalue">{{disk}}%</div><div class="muted">{{du}} / {{dt}}</div></div><div class="card"><div class="klabel">UPTIME</div><div class="kvalue">{{uptime}}</div></div></div><div class="two"><div class="card"><h2>Сервисы</h2><table>{% for n,s in services %}<tr><td>{{n}}</td><td class="{{'ok' if s=='active' else 'bad'}}">{{s}}</td></tr>{% endfor %}</table></div><div class="card"><h2>Сеть</h2><p>↓ Получено: <b>{{rx}}</b></p><p>↑ Передано: <b>{{tx}}</b></p></div></div><div class="card"><h2>Система</h2><table><tr><td>OS</td><td>{{os}}</td></tr><tr><td>Kernel</td><td>{{kernel}}</td></tr><tr><td>Python</td><td>{{python}}</td></tr><tr><td>Архитектура</td><td>{{arch}}</td></tr></table></div>''',host=platform.node(),cpu=_cpu(),ram=round(used/total*100,1) if total else 0,used=_fmt(used),total=_fmt(total),disk=round(du.used/du.total*100,1),du=_fmt(du.used),dt=_fmt(du.total),uptime=_uptime(),services=_services(),rx=_fmt(rx),tx=_fmt(tx),os=platform.platform(),kernel=platform.release(),python=platform.python_version(),arch=platform.machine())
        from app import layout
        return layout('Система',body,'/system')
    @app.route('/diagnostics')
    def diagnostics():
        checks=[]
        def add(n,ok,d=''):checks.append((n,bool(ok),d))
        add('AmneziaWG binary',_cmd('sh','-c','command -v awg').returncode==0)
        add('AWG service',_cmd('systemctl','is-active','--quiet','awg-quick@awg0').returncode==0)
        add('Panel service',_cmd('systemctl','is-active','--quiet','awgpanel').returncode==0)
        add('IP forwarding',open('/proc/sys/net/ipv4/ip_forward').read().strip()=='1' if __import__('os').path.exists('/proc/sys/net/ipv4/ip_forward') else False)
        add('DNS',_cmd('getent','hosts','example.com').returncode==0)
        add('NaïveProxy',_cmd('systemctl','is-active','--quiet','naiveproxy').returncode==0)
        ok=sum(v for _,v,_ in checks)
        body=render_template_string('''<div class="hero"><div><div class="eyebrow">HEALTH CHECK</div><h1>Диагностика</h1><p>Проверка ключевых компонентов.</p></div><div class="pill">{{ok}} / {{total}} OK</div></div><div class="card"><table>{% for n,v,d in checks %}<tr><td style="font-size:20px">{{'✓' if v else '✕'}}</td><td><b>{{n}}</b><div class="muted">{{d}}</div></td><td class="{{'ok' if v else 'bad'}}">{{'OK' if v else 'ПРОБЛЕМА'}}</td></tr>{% endfor %}</table></div>''',checks=checks,ok=ok,total=len(checks))
        return layout('Диагностика',body,'/diagnostics')
    @app.route('/api/system')
    def api_system():
        total,used=_mem();rx,tx=_net();d=shutil.disk_usage('/')
        return jsonify(cpu=_cpu(),ram=round(used/total*100,1) if total else 0,disk=round(d.used/d.total*100,1),rx=rx,tx=tx,uptime=_uptime(),host=platform.node())
    # Extend the existing sidebar without replacing the original navigation logic.
    try:
        import app as main
        old_nav=main.nav
        if not getattr(main,'_system_nav_patched',False):
            def nav(p):
                x=old_nav(p)
                return x+f'<a class="{"active" if p=="/system" else ""}" href="/system">◉&nbsp;&nbsp;Система</a><a class="{"active" if p=="/diagnostics" else ""}" href="/diagnostics">✓&nbsp;&nbsp;Диагностика</a>'
            main.nav=nav;main._system_nav_patched=True
    except Exception:pass
    return app
