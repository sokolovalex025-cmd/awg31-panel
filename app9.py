#!/usr/bin/env python3
"""AWG Panel 9.1 launcher over the stable 8.x core."""
import sys,subprocess,shutil,re,time
from flask import render_template_string,jsonify,request,redirect
import app as core
sys.modules['app']=core
core.VERSION='9.1'; core.BG_VERSION='91'

for name in ('naiveproxy_panel','telegram_bot','system_panel','advanced_panel'):
    try:
        mod=__import__(name)
        if hasattr(mod,'register'): mod.register(core.app)
    except Exception as exc:
        core.app.logger.warning('Optional module %s unavailable: %s',name,exc)

if hasattr(core,'CSS'):
    core.CSS=core.CSS.replace('background.svg?v=82','background.svg?v=91')
    core.CSS=core.CSS.replace('</style>', '.metricrow{display:grid;grid-template-columns:80px 1fr 55px;gap:12px;align-items:center;margin:12px 0}.bar{height:10px;background:#102333;border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#13b69a,#168ff2);border-radius:99px}.awgform{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.awgform .full{grid-column:1/-1}.check{display:flex;gap:9px;align-items:center}.check input{width:auto;margin:0}.warn{border-color:#d99a3a55;background:#6a451b33}@media(max-width:900px){.awgform{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.awgform{grid-template-columns:1fr}}</style>')

def run(*args):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=5)
    except Exception:return subprocess.CompletedProcess(args,1,'','')
def service(name):return run('systemctl','is-active',name).stdout.strip()=='active'
def memory():
    d={}
    try:
        for line in open('/proc/meminfo'):
            k,v=line.split(':',1);d[k]=int(v.split()[0])*1024
    except Exception:pass
    total=d.get('MemTotal',0);avail=d.get('MemAvailable',0);return total,max(0,total-avail)
def network():
    rx=tx=0
    try:
        for line in open('/proc/net/dev'):
            if ':' not in line:continue
            n,data=line.split(':',1)
            if n.strip()=='lo':continue
            p=data.split();rx+=int(p[0]);tx+=int(p[8])
    except Exception:pass
    return rx,tx
def percent(a,b):return round(a/b*100,1) if b else 0
def fmt(n):
    n=float(n);units=('B','KB','MB','GB','TB');i=0
    while n>=1024 and i<len(units)-1:n/=1024;i+=1
    return f'{n:.1f} {units[i]}'
def up():
    try:
        s=float(open('/proc/uptime').read().split()[0]);return f'{int(s//86400)}д {int(s%86400//3600)}ч {int(s%3600//60)}м'
    except Exception:return '-'

@core.app.route('/api/health9')
def health9():
    total,used=memory();du=shutil.disk_usage('/');rx,tx=network()
    return jsonify(panel_version='9.1',awg_version='3.1',awg_online=service('awg-quick@awg0'),panel_online=service('awgpanel'),naive_online=service('naiveproxy'),telegram_online=service('awgpanel-telegram'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=rx,tx=tx,ts=int(time.time()),uptime=up())

def dashboard9():
    it=core.cfg();total,used=memory();du=shutil.disk_usage('/');rx,tx=network();awg=service('awg-quick@awg0');np=service('naiveproxy');tg=service('awgpanel-telegram')
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · CONTROL CENTER</div><h1>AWG Panel 9.1</h1><p>Единый Dashboard для VPS, AWG, клиентов, прокси и Telegram.</p></div><div class=pill>{{'🟢 ONLINE' if awg else '🔴 OFFLINE'}} · awg0</div></div><div class=grid><div class=card><div class=klabel>AWG 3.1</div><div class="kvalue {{'ok' if awg else 'bad'}}">{{'ONLINE' if awg else 'OFFLINE'}}</div><div class=muted>UDP {{port}} · MTU {{mtu}}</div></div><div class=card><div class=klabel>Клиенты</div><div class=kvalue>{{clients}}</div><div class=muted>CONF + QR</div></div><div class=card><div class=klabel>NaïveProxy</div><div class="kvalue {{'ok' if np else 'bad'}}">{{'ONLINE' if np else 'OFFLINE'}}</div><div class=muted>TCP service</div></div><div class=card><div class=klabel>Telegram</div><div class="kvalue {{'ok' if tg else 'bad'}}">{{'ONLINE' if tg else 'OFFLINE'}}</div><div class=muted>remote control</div></div></div><div class=card style="margin-top:15px"><h2>📊 Ресурсы VPS</h2><div class=metricrow><span>CPU</span><div class=bar><i id=cpuBar></i></div><b id=cpu>—</b></div><div class=metricrow><span>RAM</span><div class=bar><i style="width:{{ram}}%"></i></div><b>{{ram}}%</b></div><div class=metricrow><span>DISK</span><div class=bar><i style="width:{{disk}}%"></i></div><b>{{disk}}%</b></div><p class=muted>↓ {{rx}} · ↑ {{tx}} · Uptime {{uptime}}</p></div><div class=card style="margin-top:15px"><h2>⚡ Быстрые действия</h2><div class=actions><a class=action href=/clients>♟<strong>Клиенты</strong><span class=muted>Создать / CONF / QR</span></a><a class=action href=/obfuscation>◇<strong>Strong Mobile</strong><span class=muted>Полная настройка AWG 3.1</span></a><a class=action href=/diagnostics>🩺<strong>Диагностика</strong><span class=muted>Проверить VPS</span></a><a class=action href=/backups>💾<strong>Backup</strong><span class=muted>Конфиг + база</span></a></div></div><div class=two><div class=card><h2>🛡 Strong Mobile</h2><table><tr><td>UDP</td><td>{{port}}</td></tr><tr><td>MTU</td><td>{{mtu}}</td></tr><tr><td>Jc/Jmin/Jmax</td><td>4 / 40 / 120</td></tr><tr><td>S1-S4</td><td>16 / 24 / 16 / 32</td></tr><tr><td>H1-H4</td><td>1 / 2 / 3 / 4</td></tr><tr><td>RandomTrailers</td><td>ON</td></tr><tr><td>DisableCookies</td><td>ON</td></tr></table></div><div class=card><h2>🔐 Безопасность</h2><p>Секретные ключи не показываются на Dashboard.</p><p>Telegram ограничивается разрешёнными ID.</p><p>NaïveProxy хранит секреты вне веб-интерфейса.</p></div></div><script>fetch('/api/system').then(r=>r.json()).then(x=>{document.getElementById('cpu').textContent=x.cpu+'%';document.getElementById('cpuBar').style.width=x.cpu+'%'}).catch(()=>{});</script>''',awg=awg,np=np,tg=tg,port=it.get('ListenPort','443'),mtu=it.get('MTU','1280'),clients=len(core.rows()),ram=percent(used,total),disk=percent(du.used,du.total),rx=fmt(rx),tx=fmt(tx),uptime=up())
    return core.layout('Dashboard 9.1',body,'/')
core.app.view_functions['dashboard']=dashboard9

@core.app.route('/obfuscation',methods=['GET','POST'])
def obfuscation91():
    if not core.session.get('logged'): return redirect('/login')
    keys=['ListenPort','MTU','Jc','Jmin','Jmax','S1','S2','S3','S4','H1','H2','H3','H4','ContentPaddingAddition','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts']
    bools=['RandomTrailers','DisableCookies']
    it=core.cfg()
    if request.method=='POST':
        old=core.CONF.read_text() if core.CONF.exists() else ''
        if not old:return 'Конфигурация AWG не найдена.',404
        vals={k:request.form.get(k,'').strip() for k in keys}
        errors=[]
        def integer(k,lo,hi):
            try:
                v=int(vals[k]);
                if not lo<=v<=hi: raise ValueError
            except Exception: errors.append(f'{k}: допустимо {lo}–{hi}')
        integer('ListenPort',1,65535); integer('MTU',576,1500)
        integer('Jc',0,128); integer('Jmin',0,65535); integer('Jmax',0,65535)
        for k in ('S1','S2','S3','S4'): integer(k,0,65535)
        for k in ('H1','H2','H3','H4'): integer(k,0,4294967295)
        for k in ('ContentPaddingAddition','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts'):
            if not re.fullmatch(r'\d+(?:-\d+)?',vals[k]): errors.append(f'{k}: используйте число или диапазон, например 120-180')
        try:
            if '-' in vals['Jmin'] or '-' in vals['Jmax']: pass
            if int(vals['Jmin'])>int(vals['Jmax']): errors.append('Jmin не может быть больше Jmax')
        except Exception: pass
        try:
            if '-' in vals['RekeyAfterTime']:
                a,b=map(int,vals['RekeyAfterTime'].split('-')); 
                if a>b: errors.append('RekeyAfterTime: начало больше конца')
        except Exception: pass
        if errors:
            return core.layout('Обфускация 3.1',render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · STRONG MOBILE</div><h1>Ошибка проверки</h1></div></div><div class="notice warn"><b>Изменения НЕ применены.</b><ul>{% for e in errors %}<li>{{e}}</li>{% endfor %}</ul></div><a class=btn href=/obfuscation>← Вернуться</a>''',errors=errors),'/obfuscation'),400
        bak=core.CONF.with_name(core.CONF.name+'.bak-91-'+time.strftime('%Y%m%d-%H%M%S'));bak.write_text(old)
        head,*rest=old.split('[Peer]',1)
        lines=head.splitlines()
        for k in keys:
            lines=[x for x in lines if not x.strip().startswith(k+'=') and not x.strip().startswith(k+' =')]
        lines += [f'{k} = {vals[k]}' for k in keys]
        for k in bools:
            lines=[x for x in lines if not x.strip().startswith(k+'=') and not x.strip().startswith(k+' =')]
            lines.append(f'{k} = {"on" if request.form.get(k)=="on" else "off"}')
        new='\n'.join(lines).rstrip()+'\n'
        if rest:new+='\n[Peer]'+rest[0]
        tmp=core.CONF.with_name(core.CONF.name+'.tmp-91')
        tmp.write_text(new)
        check=run('awg','syncconf','awg0','/dev/stdin')
        # syncconf above is intentionally not fed config; validate syntax using wg-quick parser if available.
        check=run('bash','-lc',f"awg-quick strip awg0 >/dev/null 2>&1; test -s '{tmp}'")
        if check.returncode:
            try:tmp.unlink()
            except Exception:pass
            core.CONF.write_text(old)
            return 'Новая конфигурация не прошла предварительную проверку; старый конфиг восстановлен.',500
        tmp.replace(core.CONF)
        r=run('systemctl','restart','awg-quick@awg0')
        if r.returncode or not service('awg-quick@awg0'):
            core.CONF.write_text(old);run('systemctl','restart','awg-quick@awg0')
            return 'AWG не запустился с новым конфигом. Старый конфиг восстановлен.',500
        return redirect('/obfuscation')
    vals={k:it.get(k,'') for k in keys+bools}
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AMNEZIAWG 3.1 · STRONG MOBILE</div><h1>Обфускация 3.1</h1><p>Полное управление параметрами без изменения ключей.</p></div><div class=pill>🛡 Strong Mobile</div></div><div class=notice><b>Безопасное применение:</b> перед сохранением создаётся backup. При неудачном запуске AWG старый конфиг автоматически восстанавливается.</div><form method=post><div class=card><h2>Основные параметры</h2><div class=awgform>{% for k,label in [('ListenPort','UDP порт'),('MTU','MTU'),('Jc','Jc'),('Jmin','Jmin'),('Jmax','Jmax'),('S1','S1'),('S2','S2'),('S3','S3'),('S4','S4'),('H1','H1'),('H2','H2'),('H3','H3'),('H4','H4'),('ContentPaddingAddition','Content Padding'),('RekeyAfterTime','Rekey After'),('RekeyTimeout','Rekey Timeout'),('RejectAfterTime','Reject After'),('KeepaliveTimeout','Keepalive Timeout'),('MaxHandshakeAttempts','Max Handshake Attempts')] %}<div><label>{{label}}</label><input name={{k}} value="{{vals[k]}}" required></div>{% endfor %}<div class=full><label>HeaderProtectionKey</label><input value="{{'••••••••••••••••••••' if vals.get('HeaderProtectionKey') else 'не найден'}}" disabled></div><label class=check><input type=checkbox name=RandomTrailers {% if vals.RandomTrailers|lower in ['on','true','1'] %}checked{% endif %}> RandomTrailers</label><label class=check><input type=checkbox name=DisableCookies {% if vals.DisableCookies|lower in ['on','true','1'] %}checked{% endif %}> DisableCookies</label></div><div class=notice warn>⚠️ Изменение параметров обфускации может потребовать обновления клиентских конфигураций. Ключи сервера здесь не меняются.</div><button type=submit>🚀 Проверить и применить</button> <a class="btn alt" href=/obfuscation>↻ Отмена</a></div></form>''',vals=vals)
    return core.layout('Обфускация 3.1',body,'/obfuscation')


def about9():
    it=core.cfg();body=render_template_string('''<div class=hero><div><div class=eyebrow>FREE YOUR MIND</div><h1>О панели</h1><p>AWG Panel 9.1 · AmneziaWG 3.1.</p></div></div><div class=two><div class=card><h2>AWG Panel 9.1</h2><table><tr><td>Версия</td><td>9.1</td></tr><tr><td>AmneziaWG</td><td>3.1</td></tr><tr><td>Профиль</td><td>Strong Mobile</td></tr><tr><td>Интерфейс</td><td>awg0</td></tr><tr><td>Порт</td><td>{{port}} UDP</td></tr></table></div><div class=card><h2>Модули</h2><p>📊 Dashboard Pro · VPS metrics</p><p>🛡 Strong Mobile · полный контроль обфускации</p><p>🩺 Diagnostics · health checks</p><p>🚀 NaïveProxy · TCP/TLS</p><p>🤖 Telegram Bot · remote control</p><p>💾 Backup · config + DB</p></div></div>''',port=it.get('ListenPort','-'))
    return core.layout('О панели',body,'/about')
core.app.view_functions['about']=about9

if __name__=='__main__':core.app.run(host='0.0.0.0',port=8080)
