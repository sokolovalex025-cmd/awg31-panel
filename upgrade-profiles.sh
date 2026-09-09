#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
BACKUP="$BASE/backups/app-before-profiles-$(date +%Y%m%d-%H%M%S).py"
mkdir -p "$BASE/backups"
cp -a "$APP" "$BACKUP"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
if 'AWG PROFILE MANAGER V1' in s:
    print('Profiles already installed.')
    raise SystemExit(0)
s=s.replace("VERSION='8.1';BG_VERSION='82'", "VERSION='8.2';BG_VERSION='82'")
s=s.replace("('♣','Клиенты','/clients'),('▤','Конфигурация','/config')", "('♣','Клиенты','/clients'),('◈','Профили подключения','/profiles'),('▤','Конфигурация','/config')")
old='<a class=btn href="/clients/{{r.id}}/conf">CONF</a> <a class=btn href="/clients/{{r.id}}/qr">QR</a>'
new='<a class=btn href="/clients/{{r.id}}/conf">CONF</a> <a class=btn href="/clients/{{r.id}}/qr" target="_blank" rel="noopener">QR</a> <form method="post" action="/clients/{{r.id}}/delete" style="display:inline" onsubmit="return confirm(\'Удалить клиента {{r.name}}?\')"><button class="btn" style="background:#7b2634">Удалить</button></form>'
s=s.replace(old,new)
marker="if __name__=='__main__':app.run(host='0.0.0.0',port=8080)"
code=r'''
# === AWG PROFILE MANAGER V1 ===
def _profile_db_init():
    c=db(); c.execute("CREATE TABLE IF NOT EXISTS awg_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT NOT NULL DEFAULT '', jc TEXT NOT NULL, jmin TEXT NOT NULL, jmax TEXT NOT NULL, s1 TEXT NOT NULL, s2 TEXT NOT NULL, s3 TEXT NOT NULL, s4 TEXT NOT NULL, h1 TEXT NOT NULL, h2 TEXT NOT NULL, h3 TEXT NOT NULL, h4 TEXT NOT NULL, random_trailers TEXT NOT NULL, disable_cookies TEXT NOT NULL, mtu TEXT NOT NULL DEFAULT '1280')")
    defaults=[
      ('Универсальный','Сбалансированный профиль','4','40','120','16','24','16','32','1','2','3','4','on','on','1280'),
      ('Мобильный LTE/5G','Для мобильных сетей','4','40','120','16','24','16','32','1','2','3','4','on','on','1280'),
      ('Строгая блокировка','Более агрессивная маскировка; применять после тестирования','8','32','160','16','16','16','16','1','2','3','4','on','on','1280'),
      ('Совместимость','Минимальная обфускация для проблемных клиентов','2','32','96','12','12','12','12','1','2','3','4','on','on','1280')]
    for row in defaults:
        try:c.execute("INSERT INTO awg_profiles(name,description,jc,jmin,jmax,s1,s2,s3,s4,h1,h2,h3,h4,random_trailers,disable_cookies,mtu) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",row)
        except sqlite3.IntegrityError:pass
    c.commit();c.close()
_profile_db_init()

def _profile_cfg():
    c=db(); rows=c.execute('SELECT * FROM awg_profiles ORDER BY id').fetchall(); c.close(); return rows

def _profile_apply(pid):
    c=db(); r=c.execute('SELECT * FROM awg_profiles WHERE id=?',(pid,)).fetchone(); c.close()
    if not r: raise RuntimeError('Профиль не найден')
    old=CONF.read_text() if CONF.exists() else ''
    bak=CONF.with_name(CONF.name+'.bak-profile-'+time.strftime('%Y%m%d-%H%M%S'))
    if CONF.exists(): bak.write_text(old); bak.chmod(0o600)
    vals={'Jc':r['jc'],'Jmin':r['jmin'],'Jmax':r['jmax'],'S1':r['s1'],'S2':r['s2'],'S3':r['s3'],'S4':r['s4'],'H1':r['h1'],'H2':r['h2'],'H3':r['h3'],'H4':r['h4'],'RandomTrailers':r['random_trailers'],'DisableCookies':r['disable_cookies'],'MTU':r['mtu']}
    head,*rest=old.split('[Peer]',1)
    lines=[x for x in head.splitlines() if not any(x.strip().startswith(k+' ') or x.strip().startswith(k+'=') for k in vals)]
    lines += [f'{k} = {v}' for k,v in vals.items()]
    out='\n'.join(lines).rstrip()+'\n'+(('\n[Peer]'+rest[0]) if rest else '')
    CONF.write_text(out); CONF.chmod(0o600)
    if cmd('awg-quick','strip','awg0').returncode!=0:
        CONF.write_text(old); CONF.chmod(0o600); raise RuntimeError('Профиль не прошёл проверку awg-quick; конфигурация восстановлена.')
    rr=cmd('systemctl','restart','awg-quick@awg0')
    if rr.returncode:
        CONF.write_text(old); CONF.chmod(0o600); cmd('systemctl','restart','awg-quick@awg0'); raise RuntimeError('AWG не запустился; конфигурация восстановлена.')
    return r

@app.route('/profiles')
def profiles_page():
    current=cfg();
    body=render_template_string('''<div class=hero><div><div class=eyebrow>AWG 3.1 PROFILES</div><h1>Профили подключения</h1><p>Готовые профили для разных типов сетей и условий блокировки.</p></div></div><div class=notice>Важно: параметры J/S/H, RandomTrailers и DisableCookies относятся к серверному AWG-профилю. При применении профиль меняет настройки awg0; существующим клиентам может потребоваться новый конфиг.</div><div class=card><table><tr><th>Профиль</th><th>Описание</th><th>J</th><th>S1-S4</th><th>Действие</th></tr>{% for p in profiles %}<tr><td><b>{{p.name}}</b></td><td class=muted>{{p.description}}</td><td>{{p.jc}} / {{p.jmin}}-{{p.jmax}}</td><td>{{p.s1}} / {{p.s2}} / {{p.s3}} / {{p.s4}}</td><td><form method=post action=/profiles/apply onsubmit="return confirm('Применить профиль {{p.name}}? AWG будет перезапущен.')"><input type=hidden name=id value="{{p.id}}"><button>Применить</button></form></td></tr>{% endfor %}</table></div><div class=card style="margin-top:16px"><h2>Текущий сервер</h2><table><tr><td>Jc</td><td>{{cur.get('Jc','-')}}</td></tr><tr><td>Jmin / Jmax</td><td>{{cur.get('Jmin','-')}} / {{cur.get('Jmax','-')}}</td></tr><tr><td>S1-S4</td><td>{{cur.get('S1','-')}} / {{cur.get('S2','-')}} / {{cur.get('S3','-')}} / {{cur.get('S4','-')}}</td></tr><tr><td>H1-H4</td><td>{{cur.get('H1','-')}} / {{cur.get('H2','-')}} / {{cur.get('H3','-'))}} / {{cur.get('H4','-')}}</td></tr><tr><td>RandomTrailers</td><td>{{cur.get('RandomTrailers','-')}}</td></tr><tr><td>DisableCookies</td><td>{{cur.get('DisableCookies','-')}}</td></tr></table></div>''',profiles=_profile_cfg(),cur=current)
    return layout('Профили подключения',body,'/profiles')

@app.route('/profiles/apply',methods=['POST'])
def profiles_apply():
    try:
        _profile_apply(int(request.form.get('id','0')))
        return redirect('/profiles')
    except Exception as e:
        return Response("<script>alert(%r);location='/profiles'</script>" % str(e)),500
# === END AWG PROFILE MANAGER V1 ===
'''
if marker not in s: raise SystemExit('main marker not found')
s=s.replace(marker, code+'\n'+marker)
p.write_text(s)
PY
/opt/awg31-panel/venv/bin/python -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
echo '=== AWG PROFILE MANAGER V1 INSTALLED ==='
echo "Backup: $BACKUP"
